// Parallel Planner with Review: three-phase orchestration loop
//
// This template drives a multi-phase workflow:
//   Phase 1 (Plan):             An agent analyzes explicitly authorised issues
//                               and outputs a validated <plan> JSON payload.
//   Phase 2 (Execute + Review): For each issue, a sandbox is created via
//                               createSandbox(). The implementer runs first
//                               and an independent reviewer gates its commits.
//                               Issue pipelines run concurrently.
//   Phase 3 (Publish):          Reviewed Task branches integrate into their
//                               Feature branch, which is published to one PR.
//
// The agents only ever produce commits. Closing issues, moving labels, and
// commenting are done here, by this file, from the validated plan and from
// verified local ancestry and remote publication receipts. See
// docs/agents/issue-tracker.md.
//
// The outer loop repeats until no authorised work or the configured Task
// budget remains.
//
// Usage:
//   npx tsx .sandcastle/main.mts
// Or add to package.json:
//   "scripts": { "sandcastle": "npx tsx .sandcastle/main.mts" }

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  closeSync,
  existsSync,
  fsyncSync,
  openSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

import * as sandcastle from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// Keep paid AFK work conservative by default. Operators may opt into more
// concurrency, but never beyond the local Docker safety cap.
const HARD_MAX_PARALLEL_ISSUES = 3;
export const DEFAULT_MAX_PARALLEL_ISSUES = 1;
export const DEFAULT_TASK_BUDGET = 5;
export const DEFAULT_TIME_BUDGET_MINUTES = 2 * 60;

export function positiveIntegerSetting(
  name: string,
  fallback: number,
  maximum: number,
): number {
  const raw = localConfiguration(name)?.trim();
  if (!raw) return fallback;
  if (!/^[1-9]\d*$/.test(raw)) {
    throw new Error(`${name} must be a positive integer.`);
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value > maximum) {
    throw new Error(`${name} must not exceed ${maximum}.`);
  }
  return value;
}

const MAX_PARALLEL_ISSUES = positiveIntegerSetting(
  "SANDCASTLE_MAX_PARALLEL_ISSUES",
  DEFAULT_MAX_PARALLEL_ISSUES,
  HARD_MAX_PARALLEL_ISSUES,
);
const TASK_BUDGET = positiveIntegerSetting(
  "SANDCASTLE_TASK_BUDGET",
  DEFAULT_TASK_BUDGET,
  1_000,
);
const TIME_BUDGET_MINUTES = positiveIntegerSetting(
  "SANDCASTLE_TIME_BUDGET_MINUTES",
  DEFAULT_TIME_BUDGET_MINUTES,
  7 * 24 * 60,
);

// Match the course-video-manager AFK workflows: no individual agent may run
// forever merely because it continues producing output. Sandcastle's idle
// timeout remains a second, shorter guard against a hung agent.
const phaseTimeoutMs = {
  planner: 15 * 60 * 1_000,
  implementer: 60 * 60 * 1_000,
  reviewer: 60 * 60 * 1_000,
  merger: 60 * 60 * 1_000,
} as const;

const IDLE_TIMEOUT_SECONDS = 10 * 60;
const COMPLETION_TIMEOUT_SECONDS = 60;
const HOOK_TIMEOUT_MS = 10 * 60 * 1_000;
const HOST_COMMAND_TIMEOUT_MS = 2 * 60 * 1_000;
const PUBLICATION_TIMEOUT_MS = 30 * 60 * 1_000;
const DOCKER_IMAGE = "sandcastle:flash-trips";
const RUN_STATE_PATH = ".sandcastle/run-state.json";
const WHOLE_RUN_TIMEOUT_MS = TIME_BUDGET_MINUTES * 60 * 1_000;
const AUTOPILOT_LABEL = "agent:autopilot";
const GATES_CLEARED_LABEL = "agent:gates-cleared";
export const AUTOPILOT_FEATURE_QUERY = `query($owner:String!,$repo:String!,$endCursor:String){repository(owner:$owner,name:$repo){issues(states:OPEN,first:100,after:$endCursor,labels:["${AUTOPILOT_LABEL}"]){nodes{number labels(first:50){nodes{name} pageInfo{hasNextPage}}} pageInfo{hasNextPage endCursor}}}}`;

const lifecycleTimeouts = {
  copyToWorktreeMs: 10 * 60 * 1_000,
  gitSetupMs: 30 * 1_000,
  commitCollectionMs: 2 * 60 * 1_000,
  mergeToHostMs: 2 * 60 * 1_000,
} as const;

// Planning is constrained by structured output, while implementation and
// conflict resolution benefit from more reasoning. A different model family
// reviews the implementation to reduce correlated mistakes.
const agentModels = {
  planner: "gpt-5.6-sol-medium",
  implementer: "gpt-5.6-sol-medium",
  reviewer: "claude-opus-5-thinking-medium",
  merger: "gpt-5.6-sol-medium",
} as const;

// The planner emits its plan as JSON inside <plan> tags; Output.object extracts
// and validates it against this schema. We use Zod here, but any Standard
// Schema validator works just as well: Valibot, ArkType, etc. See
// https://standardschema.dev.
export const planSchema = z
  .object({
    issues: z
      .array(
        z.object({
          id: z.string().regex(/^[1-9]\d*$/),
          title: z.string().min(1),
          branch: z.string().regex(/^sandcastle\/task-[1-9]\d*$/),
        }),
      )
      .max(HARD_MAX_PARALLEL_ISSUES),
  })
  .superRefine(({ issues }, context) => {
    const ids = new Set<string>();
    const branches = new Set<string>();

    for (const [index, issue] of issues.entries()) {
      if (ids.has(issue.id)) {
        context.addIssue({
          code: "custom",
          message: `Duplicate issue ${issue.id}`,
          path: ["issues", index, "id"],
        });
      }
      if (branches.has(issue.branch)) {
        context.addIssue({
          code: "custom",
          message: `Duplicate branch ${issue.branch}`,
          path: ["issues", index, "branch"],
        });
      }
      ids.add(issue.id);
      branches.add(issue.branch);
      if (issue.branch !== `sandcastle/task-${issue.id}`) {
        context.addIssue({
          code: "custom",
          message: `Issue ${issue.id} must use its own Task branch`,
          path: ["issues", index, "branch"],
        });
      }
    }
  });

type PlannedIssue = z.infer<typeof planSchema>["issues"][number];
type PublicationReceipt = {
  branch: string;
  base: string;
  localCommit: string;
  remoteCommit: string;
  tree: string;
  prNumber: number;
  prUrl: string;
  draft: boolean;
};
const runCheckpointSchema = z.enum([
  "claimed",
  "reviewed",
  "integrated",
  "published",
]);
type RunCheckpoint = z.infer<typeof runCheckpointSchema>;
type ActiveClaim = PlannedIssue & {
  parent: number | null;
  parentTitle: string | null;
  integrationBranch: string;
  checkpoint: RunCheckpoint;
  approvedSha?: string;
  integrationHead?: string;
  expectedRemoteTree?: string;
  publication?: PublicationReceipt;
};
type ClaimedIssue = ActiveClaim & { taskEnvironment: Record<string, string> };
type ApprovedIssue = { issue: ActiveClaim; sha: string };

const publicationReceiptSchema = z.object({
  branch: z.string().min(1),
  base: z.string().min(1),
  localCommit: z.string().regex(/^[0-9a-f]{40}$/),
  remoteCommit: z.string().regex(/^[0-9a-f]{40}$/),
  tree: z.string().regex(/^[0-9a-f]{40}$/),
  prNumber: z.number().int().positive(),
  prUrl: z.string().url(),
  draft: z.boolean(),
});

export const runStateSchema = z.object({
  targetBranch: z.string().min(1),
  targetHead: z.string().regex(/^[0-9a-f]{40}$/),
  issues: z.array(
    z.object({
      id: z.string().regex(/^[1-9]\d*$/),
      title: z.string().min(1),
      branch: z.string().regex(/^sandcastle\/task-[1-9]\d*$/),
      parent: z.number().int().positive().nullable().default(null),
      parentTitle: z.string().nullable().default(null),
      integrationBranch: z
        .string()
        .regex(/^sandcastle\/(?:feature|task)-[1-9]\d*$/)
        .optional(),
      checkpoint: runCheckpointSchema.optional(),
      approvedSha: z
        .string()
        .regex(/^[0-9a-f]{40}$/)
        .optional(),
      integrationHead: z
        .string()
        .regex(/^[0-9a-f]{40}$/)
        .optional(),
      expectedRemoteTree: z
        .string()
        .regex(/^[0-9a-f]{40}$/)
        .optional(),
      publication: publicationReceiptSchema.optional(),
    }),
  ),
})
  .transform((state) => ({
    ...state,
    issues: state.issues.map((issue) => ({
      ...issue,
      integrationBranch:
        issue.integrationBranch ??
        (issue.parent === null
          ? issue.branch
          : `sandcastle/feature-${issue.parent}`),
      checkpoint:
        issue.checkpoint ??
        (issue.publication
          ? "published"
          : issue.integrationHead
            ? "integrated"
            : issue.approvedSha
              ? "reviewed"
              : "claimed"),
    })),
  }))
  .superRefine((state, context) => {
    for (const [index, issue] of state.issues.entries()) {
      if (issue.checkpoint !== "claimed" && !issue.approvedSha) {
        context.addIssue({
          code: "custom",
          message: `${issue.checkpoint} checkpoint requires an approved commit`,
          path: ["issues", index, "approvedSha"],
        });
      }
      if (
        issue.checkpoint === "integrated" &&
        (!issue.integrationHead || !issue.expectedRemoteTree)
      ) {
        context.addIssue({
          code: "custom",
          message:
            "integrated checkpoint requires its source commit and expected remote tree",
          path: ["issues", index, "integrationHead"],
        });
      }
      if (issue.checkpoint === "published" && !issue.publication) {
        context.addIssue({
          code: "custom",
          message: "published checkpoint requires a publication receipt",
          path: ["issues", index, "publication"],
        });
      }
    }
  });

const reviewSchema = z.object({
  verdict: z.enum(["approved", "blocked"]),
  summary: z.string().min(1),
});

const queuedIssueSchema = z.object({
  id: z.number().int().positive(),
  body: z.string(),
  labels: z.array(z.string()),
  blockedBy: z.array(z.number().int().positive()),
  labelsTruncated: z.boolean(),
  blockersTruncated: z.boolean(),
});

const autopilotTaskSchema = z.object({
  id: z.number().int().positive(),
  body: z.string(),
  state: z.enum(["OPEN", "CLOSED"]),
  labels: z.array(z.string()),
  subIssueCount: z.number().int().nonnegative(),
  blockedBy: z.array(z.number().int().positive()),
  labelsTruncated: z.boolean(),
  blockersTruncated: z.boolean(),
});

const autopilotFeatureSchema = z.object({
  id: z.number().int().positive(),
  labels: z.array(z.string()),
  labelsTruncated: z.boolean(),
  tasksTruncated: z.boolean(),
  tasks: z.array(autopilotTaskSchema),
});

const authorizedIssueSchema = z.object({
  number: z.number().int().positive(),
  title: z.string().min(1),
  body: z.string(),
  labels: z.array(z.string()),
  parent: z.number().int().positive().nullable(),
  parentTitle: z.string().nullable(),
  subIssueCount: z.number().int().nonnegative(),
  blockedBy: z.array(z.number().int().positive()),
  labelsTruncated: z.boolean(),
  blockersTruncated: z.boolean(),
  comments: z.array(z.string()),
});

const issuePromptContextSchema = z.object({
  number: z.number().int().positive(),
  title: z.string().min(1),
  body: z.string(),
  comments: z.array(z.string()),
  commentsTruncated: z.boolean(),
  parent: z
    .object({
      number: z.number().int().positive(),
      title: z.string().min(1),
      body: z.string(),
      comments: z.array(z.string()),
      commentsTruncated: z.boolean(),
    })
    .nullable(),
});

export function parseReview(stdout: string): z.infer<typeof reviewSchema> {
  const matches = [...stdout.matchAll(/<review>\s*([\s\S]*?)\s*<\/review>/g)];
  if (matches.length !== 1 || !matches[0]?.[1]) {
    throw new Error("Reviewer must emit exactly one non-empty <review> block");
  }

  let payload: unknown;
  try {
    payload = JSON.parse(matches[0][1]);
  } catch (error) {
    throw new Error(`Reviewer emitted invalid JSON: ${error}`);
  }

  return reviewSchema.parse(payload);
}

// Keep in sync with the `packages` list in pnpm-workspace.yaml.
const workspacePackages = ["apps/web", "contracts/ts"];

// Hooks run inside the sandbox before the agent starts each iteration.
// `just install` restores both halves of the toolchain: uv for the Python
// side and pnpm for the workspace. It is the safety net for platform-specific
// binaries and anything added since the node_modules copy below.
const hooks = {
  sandbox: {
    onSandboxReady: [{ command: "just install", timeoutMs: HOOK_TIMEOUT_MS }],
  },
};

// Copy node_modules from the host into the worktree before each sandbox
// starts, so the install above is a fast no-op instead of a cold resolve.
// pnpm puts the real packages in the root node_modules/.pnpm store and gives
// each workspace package its own node_modules of relative symlinks into it,
// so every one of those directories has to come along or the links dangle.
const copyToWorktree = [
  "node_modules",
  ...workspacePackages.map((dir) => `${dir}/node_modules`),
].filter((dir) => existsSync(dir));

// ---------------------------------------------------------------------------
// Tracker writes
//
// docs/agents/issue-tracker.md draws the line: an agent produces commits, and
// automation does the tracker writes from what the agent produced. The prompts
// are commit-only for that reason, and every close, comment, and label lives
// here instead, running over the validated plan. A misread scope then costs a
// branch rather than a specification.
// ---------------------------------------------------------------------------

function capture(command: string, args: string[]): string {
  return execFileSync(command, args, {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
    timeout: HOST_COMMAND_TIMEOUT_MS,
  }).trim();
}

function repositoryDefaultBranch(): string {
  return capture("gh", [
    "repo",
    "view",
    "--json",
    "defaultBranchRef",
    "--jq",
    ".defaultBranchRef.name",
  ]);
}

function captureWithTimeout(
  command: string,
  args: string[],
  timeout: number,
): string {
  return execFileSync(command, args, {
    encoding: "utf8",
    maxBuffer: 4 * 1024 * 1024,
    timeout,
  }).trim();
}

function describeError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message.replace(/\s+/g, " ").trim().slice(0, 2_000);
}

function localConfiguration(name: string): string | undefined {
  const processValue = process.env[name]?.trim();
  if (processValue) return processValue;
  if (!existsSync(".sandcastle/.env")) return undefined;

  const assignment = new RegExp(
    `^\\s*(?:export\\s+)?${name}\\s*=\\s*(.+)\\s*$`,
  );
  const value = readFileSync(".sandcastle/.env", "utf8")
    .split("\n")
    .map((line) => line.match(assignment)?.[1]?.trim())
    .find((candidate) => candidate !== undefined);
  if (!value || value === '""' || value === "''") return undefined;
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function configured(name: string): boolean {
  return localConfiguration(name) !== undefined;
}

const forbiddenTaskEnvironment = new Set([
  "CURSOR_API_KEY",
  "GH_TOKEN",
  "GITHUB_TOKEN",
]);

export function parseAfkEnvironment(body: string): string[] {
  const heading = /^## AFK environment\s*$/m.exec(body);
  if (!heading) return [];
  const section = body
    .slice(heading.index + heading[0].length)
    .split(/^##\s+/m, 1)[0]!
    .trim();
  if (!section) throw new Error("AFK environment section is empty.");
  const names = section
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = /^-\s+([A-Z][A-Z0-9_]*)$/.exec(line);
      if (!match?.[1]) {
        throw new Error(
          "AFK environment entries must be bullet-listed variable names.",
        );
      }
      return match[1];
    });
  return [...new Set(names)].sort();
}

export function hasExternalPreRunGates(body: string): boolean {
  const heading = /^## External human or evidence gates\s*$/m.exec(body);
  if (!heading) return false;
  return Boolean(
    body
      .slice(heading.index + heading[0].length)
      .split(/^##\s+/m, 1)[0]!
      .trim(),
  );
}

export function resolveTaskEnvironment(body: string): Record<string, string> {
  const requested = parseAfkEnvironment(body);
  if (requested.length === 0) return {};
  const allowed = new Set(
    (localConfiguration("SANDCASTLE_TASK_ENV_ALLOWLIST") ?? "")
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean),
  );
  const resolved: Record<string, string> = {};
  const errors: string[] = [];
  for (const name of requested) {
    if (forbiddenTaskEnvironment.has(name)) {
      errors.push(`${name} is an orchestrator credential`);
      continue;
    }
    if (!allowed.has(name)) {
      errors.push(`${name} is not in SANDCASTLE_TASK_ENV_ALLOWLIST`);
      continue;
    }
    const value = localConfiguration(name);
    if (!value) {
      errors.push(`${name} is not configured`);
      continue;
    }
    resolved[name] = value;
  }
  if (errors.length > 0) throw new Error(errors.join("; "));
  return resolved;
}

function runPreflight(): void {
  const branch = capture("git", ["branch", "--show-current"]);
  if (!branch) {
    throw new Error(
      "Sandcastle requires a named target branch, not detached HEAD.",
    );
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(branch)) {
    throw new Error(
      `Target branch ${JSON.stringify(branch)} contains unsafe shell characters.`,
    );
  }
  capture("git", ["check-ref-format", "--branch", branch]);
  const defaultBranch = repositoryDefaultBranch();
  if (branch !== defaultBranch) {
    throw new Error(
      `Sandcastle must run from the default branch ${defaultBranch}, not ${branch}.`,
    );
  }

  const dirty = capture("git", ["status", "--porcelain"]);
  if (dirty) {
    throw new Error(
      "The target checkout is not clean. Commit or stash all changes before an AFK run.",
    );
  }

  capture("git", ["config", "user.name"]);
  capture("git", ["config", "user.email"]);
  capture("gh", ["auth", "status"]);
  const repositoryPermission = capture("gh", [
    "repo",
    "view",
    "--json",
    "viewerPermission",
    "--jq",
    ".viewerPermission",
  ]);
  if (!["ADMIN", "MAINTAIN", "WRITE"].includes(repositoryPermission)) {
    throw new Error(
      `GitHub authentication has ${repositoryPermission || "unknown"} repository permission; issue writes require WRITE or better.`,
    );
  }
  capture("docker", ["info", "--format", "{{.ServerVersion}}"]);
  capture("docker", ["image", "inspect", DOCKER_IMAGE]);
  capture("docker", [
    "run",
    "--rm",
    "--entrypoint",
    "agent",
    DOCKER_IMAGE,
    "--version",
  ]);

  for (const name of ["CURSOR_API_KEY"]) {
    if (!configured(name)) {
      throw new Error(
        `Missing ${name}. Set it in the environment or .sandcastle/.env.`,
      );
    }
  }

  const labels = new Set(
    capture("gh", [
      "label",
      "list",
      "--limit",
      "200",
      "--json",
      "name",
      "--jq",
      ".[].name",
    ])
      .split("\n")
      .filter(Boolean),
  );
  const requiredLabels = [
    "ready-for-agent",
    AUTOPILOT_LABEL,
    GATES_CLEARED_LABEL,
    ...implementationLabels,
  ];
  const missingLabels = requiredLabels.filter((label) => !labels.has(label));
  if (missingLabels.length > 0) {
    throw new Error(
      `Missing required GitHub labels: ${missingLabels.join(", ")}`,
    );
  }
}

function errorCode(error: unknown): string | undefined {
  if (typeof error !== "object" || error === null) return undefined;
  const code = Reflect.get(error, "code");
  return typeof code === "string" ? code : undefined;
}

function processIsRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return errorCode(error) === "EPERM";
  }
}

function acquireRunLock(): () => void {
  const path = ".sandcastle/run.lock";

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const descriptor = openSync(path, "wx");
      writeFileSync(
        descriptor,
        JSON.stringify({
          pid: process.pid,
          startedAt: new Date().toISOString(),
        }),
      );
      closeSync(descriptor);

      let released = false;
      return () => {
        if (released) return;
        released = true;
        rmSync(path, { force: true });
      };
    } catch (error) {
      if (errorCode(error) !== "EEXIST") throw error;

      let ownerPid: number | undefined;
      try {
        const parsed: unknown = JSON.parse(readFileSync(path, "utf8"));
        if (
          typeof parsed === "object" &&
          parsed !== null &&
          Number.isInteger(Reflect.get(parsed, "pid"))
        ) {
          ownerPid = Number(Reflect.get(parsed, "pid"));
        }
      } catch {
        // A malformed lock cannot belong to a healthy run.
      }

      if (ownerPid !== undefined && processIsRunning(ownerPid)) {
        throw new Error(
          `Another Sandcastle run is active in this checkout (PID ${ownerPid}).`,
        );
      }
      rmSync(path, { force: true });
    }
  }

  throw new Error("Could not acquire the Sandcastle run lock.");
}

// A tracker write must never take the run down with it. An expired token or a
// renamed label is worth a warning; it is not worth losing a merge.
function gh(...args: string[]): boolean {
  try {
    capture("gh", args);
    return true;
  } catch (error) {
    console.warn(`  ! gh ${args.join(" ")} failed: ${error}`);
    return false;
  }
}

function readPaginatedConnection<T>(
  query: string,
  jq: string,
  itemSchema: z.ZodType<T>,
  extraFields: string[] = [],
): T[] {
  const pageSchema = z.object({
    hasNextPage: z.boolean(),
    endCursor: z.string().nullable(),
    items: z.array(itemSchema),
  });
  const items: T[] = [];
  let cursor: string | null = null;
  const seen = new Set<string>();
  do {
    const raw = capture("gh", [
      "api",
      "graphql",
      "-f",
      `query=${query}`,
      "-F",
      "owner=:owner",
      "-F",
      "repo=:repo",
      ...extraFields,
      ...(cursor === null ? [] : ["-F", `endCursor=${cursor}`]),
      "--jq",
      jq,
    ]);
    const page = pageSchema.parse(JSON.parse(raw));
    items.push(...page.items);
    if (!page.hasNextPage) break;
    if (!page.endCursor || seen.has(page.endCursor)) {
      throw new Error("GitHub pagination did not advance.");
    }
    seen.add(page.endCursor);
    cursor = page.endCursor;
  } while (true);
  return items;
}

function readAuthorizedIssues(): string {
  const issues = readPaginatedConnection(
    'query($owner:String!,$repo:String!,$endCursor:String){repository(owner:$owner,name:$repo){issues(states:OPEN,first:100,after:$endCursor,labels:["ready-for-agent","agent:implement"]){nodes{number title body labels(first:50){nodes{name} pageInfo{hasNextPage}} parent{number title} subIssues(first:1){totalCount} blockedBy(first:100){nodes{number state} pageInfo{hasNextPage}} comments(last:5){nodes{body}}} pageInfo{hasNextPage endCursor}}}}',
    '{hasNextPage: .data.repository.issues.pageInfo.hasNextPage, endCursor: .data.repository.issues.pageInfo.endCursor, items: [.data.repository.issues.nodes[] | {number, title, body, labels: [.labels.nodes[].name], parent: (.parent.number // null), parentTitle: (.parent.title // null), subIssueCount: .subIssues.totalCount, blockedBy: [.blockedBy.nodes[] | select(.state == "OPEN") | .number], labelsTruncated: .labels.pageInfo.hasNextPage, blockersTruncated: .blockedBy.pageInfo.hasNextPage, comments: [.comments.nodes[].body]} | select((.labels | index("ready-for-agent")) != null and (.labels | index("agent:implement")) != null)]}',
    authorizedIssueSchema,
  );
  if (
    issues.some((issue) => issue.labelsTruncated || issue.blockersTruncated)
  ) {
    throw new Error(
      "The authorised issue query was truncated. Refusing to give the planner incomplete tracker context.",
    );
  }
  return JSON.stringify(issues, null, 2);
}

function readIssuePromptContext(issue: PlannedIssue): string {
  const raw = capture("gh", [
    "api",
    "graphql",
    "-f",
    "query=query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){issue(number:$number){number title body comments(last:50){nodes{body} pageInfo{hasPreviousPage}} parent{number title body comments(last:50){nodes{body} pageInfo{hasPreviousPage}}}}}}",
    "-F",
    "owner=:owner",
    "-F",
    "repo=:repo",
    "-F",
    `number=${issue.id}`,
    "--jq",
    "{number: .data.repository.issue.number, title: .data.repository.issue.title, body: .data.repository.issue.body, comments: [.data.repository.issue.comments.nodes[].body], commentsTruncated: .data.repository.issue.comments.pageInfo.hasPreviousPage, parent: (if .data.repository.issue.parent == null then null else {number: .data.repository.issue.parent.number, title: .data.repository.issue.parent.title, body: .data.repository.issue.parent.body, comments: [.data.repository.issue.parent.comments.nodes[].body], commentsTruncated: .data.repository.issue.parent.comments.pageInfo.hasPreviousPage} end)}",
  ]);
  const context = issuePromptContextSchema.parse(JSON.parse(raw));
  if (
    context.number !== Number(issue.id) ||
    context.title !== issue.title ||
    context.commentsTruncated ||
    context.parent?.commentsTruncated
  ) {
    throw new Error(
      `Tracker context for #${issue.id} changed or was truncated after planning.`,
    );
  }
  return JSON.stringify(context, null, 2);
}

const implementationLabels = [
  "agent:implement",
  "agent:queued",
  "agent:in-progress",
  "agent:blocked",
] as const;

type ImplementationLabel = (typeof implementationLabels)[number];

// Move a ticket to exactly one pipeline label, or to none. Read the current
// labels first so we only ask to remove what is really there: `gh` treats
// removing an absent label as an error, and this runs on every ticket.
function setPipelineLabel(
  id: string,
  label: ImplementationLabel | null,
): boolean {
  let current: string[] = [];
  try {
    current = capture("gh", [
      "issue",
      "view",
      id,
      "--json",
      "labels",
      "--jq",
      '[.labels[].name] | join("\\n")',
    ])
      .split("\n")
      .filter(Boolean);
  } catch (error) {
    console.warn(`  ! could not read labels on #${id}: ${error}`);
    return false;
  }

  const stale = implementationLabels.filter(
    (candidate) => candidate !== label && current.includes(candidate),
  );
  const add = label && !current.includes(label) ? ["--add-label", label] : [];

  if (stale.length === 0 && add.length === 0) return true;

  return gh(
    "issue",
    "edit",
    id,
    ...stale.flatMap((candidate) => ["--remove-label", candidate]),
    ...add,
  );
}

type AutopilotFeature = z.infer<typeof autopilotFeatureSchema>;

export function selectAutopilotAuthorizations(
  features: AutopilotFeature[],
): { id: string; label: ImplementationLabel; reason?: string }[] {
  const refusedLabels = [
    "roadmap",
    "needs-info",
    "ready-for-human",
    "wontfix",
    "agent:in-progress",
    "agent:blocked",
  ];
  const authorizations: {
    id: string;
    label: ImplementationLabel;
    reason?: string;
  }[] = [];

  for (const feature of [...features].sort((left, right) => left.id - right.id)) {
    if (
      !feature.labels.includes(AUTOPILOT_LABEL) ||
      feature.labelsTruncated ||
      feature.tasksTruncated
    ) {
      continue;
    }

    const tasks = feature.tasks
      .filter((candidate) => candidate.state === "OPEN")
      .sort((left, right) => left.id - right.id);
    for (const task of tasks) {
      if (
        !task.labels.includes("ready-for-agent") ||
        refusedLabels.some((label) => task.labels.includes(label)) ||
        implementationLabels.some((label) => task.labels.includes(label)) ||
        task.subIssueCount > 0 ||
        task.labelsTruncated ||
        task.blockersTruncated
      ) {
        continue;
      }
      if (
        hasExternalPreRunGates(task.body) &&
        !task.labels.includes(GATES_CLEARED_LABEL)
      ) {
        authorizations.push({
          id: String(task.id),
          label: "agent:blocked",
          reason: `Task #${task.id} has external pre-run gates. Apply ${GATES_CLEARED_LABEL} only after its disposable resources and credentials are ready.`,
        });
        continue;
      }
      authorizations.push({
        id: String(task.id),
        label: task.blockedBy.length > 0 ? "agent:queued" : "agent:implement",
      });
    }
  }

  return authorizations;
}

function authorizeAutopilotTasks(): void {
  let features: AutopilotFeature[];
  try {
    features = readPaginatedConnection(
      AUTOPILOT_FEATURE_QUERY,
      '{hasNextPage: .data.repository.issues.pageInfo.hasNextPage, endCursor: .data.repository.issues.pageInfo.endCursor, items: [.data.repository.issues.nodes[] | {id: .number, labels: [.labels.nodes[].name], labelsTruncated: .labels.pageInfo.hasNextPage, tasksTruncated: true, tasks: []}]}',
      autopilotFeatureSchema,
    );
    for (const feature of features) {
      if (!feature.tasksTruncated) continue;
      feature.tasks = readPaginatedConnection(
        "query($owner:String!,$repo:String!,$number:Int!,$endCursor:String){repository(owner:$owner,name:$repo){issue(number:$number){subIssues(first:100,after:$endCursor){nodes{number body state labels(first:50){nodes{name} pageInfo{hasNextPage}} subIssues(first:1){totalCount} blockedBy(first:100){nodes{number state} pageInfo{hasNextPage}}} pageInfo{hasNextPage endCursor}}}}}",
        '{hasNextPage: .data.repository.issue.subIssues.pageInfo.hasNextPage, endCursor: .data.repository.issue.subIssues.pageInfo.endCursor, items: [.data.repository.issue.subIssues.nodes[] | {id: .number, body, state, labels: [.labels.nodes[].name], subIssueCount: .subIssues.totalCount, blockedBy: [.blockedBy.nodes[] | select(.state == "OPEN") | .number], labelsTruncated: .labels.pageInfo.hasNextPage, blockersTruncated: .blockedBy.pageInfo.hasNextPage}]}',
        autopilotTaskSchema,
        ["-F", `number=${feature.id}`],
      );
      feature.tasksTruncated = false;
    }
  } catch (error) {
    console.warn(`  ! could not inspect autopilot Features: ${error}`);
    return;
  }

  if (
    features.some(
      (feature) => feature.labelsTruncated || feature.tasksTruncated,
    )
  ) {
    console.warn(
      "  ! Autopilot Feature data was truncated; refusing automatic authorization.",
    );
    return;
  }

  for (const authorization of selectAutopilotAuthorizations(features)) {
    const task = features
      .flatMap((feature) => feature.tasks)
      .find((candidate) => String(candidate.id) === authorization.id);
    if (authorization.label === "agent:implement" && task) {
      try {
        resolveTaskEnvironment(task.body);
      } catch (error) {
        const reason = `Sandcastle refused Task #${authorization.id} before claim: ${describeError(error)}`;
        gh("issue", "comment", authorization.id, "--body", reason);
        setPipelineLabel(authorization.id, "agent:blocked");
        continue;
      }
    }
    if (authorization.reason) {
      gh("issue", "comment", authorization.id, "--body", authorization.reason);
    }
    if (setPipelineLabel(authorization.id, authorization.label)) {
      console.log(
        `  Authorized autopilot issue #${authorization.id} as ${authorization.label}.`,
      );
    }
  }
}

const claimSchema = z.object({
  state: z.literal("OPEN"),
  title: z.string().min(1),
  body: z.string(),
  labels: z.array(z.string()),
  parent: z.number().int().positive().nullable(),
  parentTitle: z.string().nullable(),
  subIssueCount: z.number().int().nonnegative(),
  blockedBy: z.array(z.number().int().positive()),
  labelsTruncated: z.boolean(),
  blockersTruncated: z.boolean(),
});

const recoveryIssueSchema = z.object({
  state: z.enum(["OPEN", "CLOSED"]),
  labels: z.array(z.string()),
});

function claimIssue(planned: PlannedIssue): ClaimedIssue | undefined {
  let issue: z.infer<typeof claimSchema>;
  try {
    const raw = capture("gh", [
      "api",
      "graphql",
      "-f",
      "query=query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){issue(number:$number){state title body labels(first:50){nodes{name} pageInfo{hasNextPage}} parent{number title} subIssues(first:1){totalCount} blockedBy(first:100){nodes{number state} pageInfo{hasNextPage}}}}}",
      "-F",
      "owner=:owner",
      "-F",
      "repo=:repo",
      "-F",
      `number=${planned.id}`,
      "--jq",
      '{state: .data.repository.issue.state, title: .data.repository.issue.title, body: .data.repository.issue.body, labels: [.data.repository.issue.labels.nodes[].name], parent: (.data.repository.issue.parent.number // null), parentTitle: (.data.repository.issue.parent.title // null), subIssueCount: .data.repository.issue.subIssues.totalCount, blockedBy: [.data.repository.issue.blockedBy.nodes[] | select(.state == "OPEN") | .number], labelsTruncated: .data.repository.issue.labels.pageInfo.hasNextPage, blockersTruncated: .data.repository.issue.blockedBy.pageInfo.hasNextPage}',
    ]);
    issue = claimSchema.parse(JSON.parse(raw));
  } catch (error) {
    console.warn(
      `  ! could not validate claim for #${planned.id}: ${describeError(error)}`,
    );
    return undefined;
  }

  const required = ["ready-for-agent", "agent:implement"];
  const refused = [
    "roadmap",
    "needs-info",
    "ready-for-human",
    "wontfix",
    "agent:in-progress",
    "agent:blocked",
  ];
  if (
    required.some((label) => !issue.labels.includes(label)) ||
    refused.some((label) => issue.labels.includes(label)) ||
    issue.subIssueCount > 0 ||
    issue.blockedBy.length > 0 ||
    issue.labelsTruncated ||
    issue.blockersTruncated ||
    issue.title !== planned.title
  ) {
    console.warn(
      `  ! #${planned.id} is no longer authorised or does not match the plan`,
    );
    return undefined;
  }

  if (
    hasExternalPreRunGates(issue.body) &&
    !issue.labels.includes(GATES_CLEARED_LABEL)
  ) {
    const reason = `Sandcastle refused Task #${planned.id}: external pre-run gates are not cleared. Apply ${GATES_CLEARED_LABEL} after the declared resources and credentials are ready.`;
    console.warn(`  ! ${reason}`);
    gh("issue", "comment", planned.id, "--body", reason);
    setPipelineLabel(planned.id, "agent:blocked");
    runHadBlockedWork = true;
    return undefined;
  }

  let taskEnvironment: Record<string, string>;
  try {
    taskEnvironment = resolveTaskEnvironment(issue.body);
  } catch (error) {
    const reason = `Sandcastle refused Task #${planned.id}: ${describeError(error)}`;
    console.warn(`  ! ${reason}`);
    gh("issue", "comment", planned.id, "--body", reason);
    setPipelineLabel(planned.id, "agent:blocked");
    runHadBlockedWork = true;
    return undefined;
  }

  const expectedBranch = `sandcastle/task-${planned.id}`;
  if (planned.branch !== expectedBranch) {
    console.warn(
      `  ! #${planned.id} planned branch ${planned.branch} does not match ${expectedBranch}`,
    );
    return undefined;
  }

  if (!setPipelineLabel(planned.id, "agent:in-progress")) return undefined;
  return {
    ...planned,
    parent: issue.parent,
    parentTitle: issue.parentTitle,
    integrationBranch:
      issue.parent === null
        ? planned.branch
        : `sandcastle/feature-${issue.parent}`,
    checkpoint: "claimed",
    taskEnvironment,
  };
}

function promoteUnblockedQueuedIssues(): void {
  let queued: z.infer<typeof queuedIssueSchema>[];
  try {
    queued = readPaginatedConnection(
      'query($owner:String!,$repo:String!,$endCursor:String){repository(owner:$owner,name:$repo){issues(states:OPEN,first:100,after:$endCursor,labels:["ready-for-agent","agent:queued"]){nodes{number body labels(first:50){nodes{name} pageInfo{hasNextPage}} blockedBy(first:100){nodes{number state} pageInfo{hasNextPage}}} pageInfo{hasNextPage endCursor}}}}',
      '{hasNextPage: .data.repository.issues.pageInfo.hasNextPage, endCursor: .data.repository.issues.pageInfo.endCursor, items: [.data.repository.issues.nodes[] | {id: .number, body, labels: [.labels.nodes[].name], blockedBy: [.blockedBy.nodes[] | select(.state == "OPEN") | .number], labelsTruncated: .labels.pageInfo.hasNextPage, blockersTruncated: .blockedBy.pageInfo.hasNextPage}]}',
      queuedIssueSchema,
    );
  } catch (error) {
    console.warn(`  ! could not inspect queued issues: ${error}`);
    return;
  }
  const refused = [
    "roadmap",
    "needs-info",
    "ready-for-human",
    "wontfix",
    "agent:implement",
    "agent:in-progress",
    "agent:blocked",
  ];
  for (const issue of queued) {
    const isQueued =
      issue.labels.includes("ready-for-agent") &&
      issue.labels.includes("agent:queued");
    const isRefused = refused.some((label) => issue.labels.includes(label));
    if (
      !isQueued ||
      isRefused ||
      issue.blockedBy.length > 0 ||
      issue.labelsTruncated ||
      issue.blockersTruncated
    ) {
      continue;
    }
    if (
      hasExternalPreRunGates(issue.body) &&
      !issue.labels.includes(GATES_CLEARED_LABEL)
    ) {
      continue;
    }
    try {
      resolveTaskEnvironment(issue.body);
    } catch (error) {
      console.warn(
        `  ! queued Task #${issue.id} environment is not ready: ${describeError(error)}`,
      );
      continue;
    }

    if (setPipelineLabel(String(issue.id), "agent:implement")) {
      console.log(`  Promoted queued issue #${issue.id} for implementation.`);
    }
  }
}

// Whether one pinned commit is genuinely contained in another local ref.
// Publication verification adds the remote fact required before Task closure.
export function branchLanded(branch: string, target = "HEAD"): boolean {
  try {
    capture("git", ["merge-base", "--is-ancestor", branch, target]);
    return true;
  } catch {
    return false;
  }
}

function localBranchHead(branch: string): string | undefined {
  try {
    return capture("git", ["rev-parse", "--verify", `${branch}^{commit}`]);
  } catch {
    return undefined;
  }
}

function prepareIntegrationBase(
  issue: ActiveClaim,
  targetHead: string,
): string {
  if (issue.parent === null) return targetHead;
  const existing = localBranchHead(issue.integrationBranch);
  if (!existing) {
    capture("git", ["branch", issue.integrationBranch, targetHead]);
    return targetHead;
  }
  try {
    capture("git", ["merge-base", existing, targetHead]);
  } catch {
    throw new Error(
      `${issue.integrationBranch} does not share history with the pinned target ${targetHead}.`,
    );
  }
  return existing;
}

function updateIntegrationBranch(
  branch: string,
  expectedHead: string,
  nextHead: string,
): void {
  capture("git", [
    "update-ref",
    `refs/heads/${branch}`,
    nextHead,
    expectedHead,
  ]);
}

function publishIntegrationBranch(
  issue: ActiveClaim,
  sourceHead: string,
  targetBranch: string,
  expectedRemoteTree: string,
  ready: boolean,
): PublicationReceipt {
  const title =
    issue.parent === null
      ? issue.title.replace(/^\[[^\]]+\]\s*/, "")
      : (issue.parentTitle ?? `Feature #${issue.parent}`);
  const body =
    issue.parent === null
      ? `Sandcastle implementation for #${issue.id}.`
      : `Sandcastle Feature branch for #${issue.parent}.\n\nCloses #${issue.parent}`;
  const raw = captureWithTimeout(
    "bash",
    [
      "scripts/publish-via-github-api.sh",
      ready ? "--pr" : "--draft-pr",
      "--source",
      sourceHead,
      "--branch",
      issue.integrationBranch,
      "--base",
      targetBranch,
      "--title",
      title,
      "--body",
      body,
      "--expect-remote-tree",
      expectedRemoteTree,
      "--json",
    ],
    PUBLICATION_TIMEOUT_MS,
  );
  return publicationReceiptSchema.parse(JSON.parse(raw));
}

function remoteBranchCommit(branch: string): string {
  const refs = z
    .array(
      z.object({
        ref: z.string(),
        object: z.object({ sha: z.string().min(1) }),
      }),
    )
    .parse(
      JSON.parse(
        capture("gh", [
          "api",
          `repos/{owner}/{repo}/git/matching-refs/heads/${encodeURIComponent(branch)}`,
        ]),
      ),
    );
  const exact = refs.find((candidate) => candidate.ref === `refs/heads/${branch}`);
  if (!exact) throw new Error(`Remote branch ${branch} does not exist.`);
  return exact.object.sha;
}

function verifyPublicationReceipt(receipt: PublicationReceipt): boolean {
  try {
    const remoteCommit = remoteBranchCommit(receipt.branch);
    const remoteTree = capture("gh", [
      "api",
      `repos/{owner}/{repo}/git/commits/${remoteCommit}`,
      "--jq",
      ".tree.sha",
    ]);
    const pull = JSON.parse(
      capture("gh", [
        "pr",
        "view",
        String(receipt.prNumber),
        "--json",
        "headRefName,baseRefName,url",
      ]),
    ) as { headRefName?: string; baseRefName?: string; url?: string };
    return (
      remoteCommit === receipt.remoteCommit &&
      remoteTree === receipt.tree &&
      pull.headRefName === receipt.branch &&
      pull.baseRefName === receipt.base &&
      pull.url === receipt.prUrl
    );
  } catch {
    return false;
  }
}

function featureHasRemainingAgentTasks(
  parent: number,
  completing: Set<string>,
): boolean {
  const taskSchema = z.object({
    id: z.number().int().positive(),
    state: z.enum(["OPEN", "CLOSED"]),
    labels: z.array(z.string()),
    labelsTruncated: z.boolean(),
  });
  const tasks = readPaginatedConnection(
    "query($owner:String!,$repo:String!,$number:Int!,$endCursor:String){repository(owner:$owner,name:$repo){issue(number:$number){subIssues(first:100,after:$endCursor){nodes{number state labels(first:50){nodes{name} pageInfo{hasNextPage}}} pageInfo{hasNextPage endCursor}}}}}",
    '{hasNextPage: .data.repository.issue.subIssues.pageInfo.hasNextPage, endCursor: .data.repository.issue.subIssues.pageInfo.endCursor, items: [.data.repository.issue.subIssues.nodes[] | {id: .number, state, labels: [.labels.nodes[].name], labelsTruncated: .labels.pageInfo.hasNextPage}]}',
    taskSchema,
    ["-F", `number=${parent}`],
  );
  if (tasks.some((task) => task.labelsTruncated)) {
    throw new Error(
      `Could not determine whether Feature #${parent} has remaining agent Tasks.`,
    );
  }
  return tasks.some(
    (task) =>
      task.state === "OPEN" &&
      !completing.has(String(task.id)) &&
      task.labels.includes("ready-for-agent"),
  );
}

const activeClaims = new Map<string, ActiveClaim>();
const closedPendingCleanup = new Set<string>();
const shutdownController = new AbortController();
const wholeRunSignal = AbortSignal.timeout(WHOLE_RUN_TIMEOUT_MS);
let runStateTargetBranch: string | undefined;
let runStateTargetHead: string | undefined;
let runHadBlockedWork = false;

function phaseSignal(timeoutMs: number): AbortSignal {
  return AbortSignal.any([
    shutdownController.signal,
    wholeRunSignal,
    AbortSignal.timeout(timeoutMs),
  ]);
}

function persistRunState(): void {
  if (activeClaims.size === 0) {
    rmSync(RUN_STATE_PATH, { force: true });
    return;
  }
  if (!runStateTargetBranch || !runStateTargetHead) {
    throw new Error(
      "Cannot persist claims before recording the target branch.",
    );
  }

  const temporaryPath = `${RUN_STATE_PATH}.tmp`;
  const contents = `${JSON.stringify(
    {
      targetBranch: runStateTargetBranch,
      targetHead: runStateTargetHead,
      issues: [...activeClaims.values()],
    },
    null,
    2,
  )}\n`;
  const descriptor = openSync(temporaryPath, "w");
  try {
    writeFileSync(descriptor, contents);
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
  renameSync(temporaryPath, RUN_STATE_PATH);

  const directory = openSync(".sandcastle", "r");
  try {
    fsyncSync(directory);
  } finally {
    closeSync(directory);
  }
}

function blockIssue(issue: PlannedIssue, reason: string): void {
  if (!activeClaims.has(issue.id) || closedPendingCleanup.has(issue.id)) return;
  runHadBlockedWork = true;

  const safeReason = describeError(reason);
  gh(
    "issue",
    "comment",
    issue.id,
    "--body",
    `Sandcastle stopped work on \`${issue.branch}\`. ${safeReason}`,
  );
  if (setPipelineLabel(issue.id, "agent:blocked")) {
    activeClaims.delete(issue.id);
    persistRunState();
  }
}

function stopClaim(issue: ActiveClaim, reason: string): void {
  if (issue.checkpoint === "claimed") {
    blockIssue(issue, reason);
    return;
  }
  console.warn(
    `  ↻ Preserved #${issue.id} at its ${issue.checkpoint} checkpoint for the next run.`,
  );
  persistRunState();
}

function closeLandedIssue(
  issue: ActiveClaim,
  approvedSha: string,
  receipt: PublicationReceipt,
): boolean {
  if (
    !branchLanded(approvedSha, issue.integrationBranch) ||
    !verifyPublicationReceipt(receipt)
  ) {
    return false;
  }

  const closed = gh(
    "issue",
    "close",
    issue.id,
    "--comment",
    `Completed by Sandcastle. The reviewed Task commit is published on \`${receipt.branch}\` in ${receipt.prUrl}. Verified tree: \`${receipt.tree}\`.`,
  );
  if (!closed) {
    blockIssue(
      issue,
      "The branch landed, but Sandcastle could not close the GitHub issue.",
    );
    return true;
  }

  if (!setPipelineLabel(issue.id, null)) {
    closedPendingCleanup.add(issue.id);
    runHadBlockedWork = true;
    console.error(
      `  ! Issue #${issue.id} closed, but its pipeline labels need reconciliation.`,
    );
    return true;
  }

  activeClaims.delete(issue.id);
  persistRunState();
  return true;
}

function recoverInterruptedRun(): ApprovedIssue[] {
  if (!existsSync(RUN_STATE_PATH)) return [];

  const state = runStateSchema.parse(
    JSON.parse(readFileSync(RUN_STATE_PATH, "utf8")),
  );
  if (state.targetBranch !== runStateTargetBranch) {
    throw new Error(
      `The interrupted run targeted ${state.targetBranch}, not ${runStateTargetBranch}.`,
    );
  }
  console.warn(
    `Recovering ${state.issues.length} claim(s) from an interrupted Sandcastle run.`,
  );

  for (const issue of state.issues) activeClaims.set(issue.id, issue);

  let recoveryFailed = false;
  for (const issue of state.issues) {
    let current: z.infer<typeof recoveryIssueSchema>;
    try {
      const raw = capture("gh", [
        "api",
        "graphql",
        "-f",
        "query=query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){issue(number:$number){state labels(first:50){nodes{name}}}}}",
        "-F",
        "owner=:owner",
        "-F",
        "repo=:repo",
        "-F",
        `number=${issue.id}`,
        "--jq",
        "{state: .data.repository.issue.state, labels: [.data.repository.issue.labels.nodes[].name]}",
      ]);
      current = recoveryIssueSchema.parse(JSON.parse(raw));
    } catch (error) {
      console.warn(
        `  ! Could not recover #${issue.id}: ${describeError(error)}`,
      );
      recoveryFailed = true;
      continue;
    }

    if (current.state === "CLOSED") {
      if (!issue.publication || !verifyPublicationReceipt(issue.publication)) {
        console.error(
          `  ! Closed Task #${issue.id} has no valid publication receipt.`,
        );
        recoveryFailed = true;
        continue;
      }
      if (!setPipelineLabel(issue.id, null)) {
        recoveryFailed = true;
      } else {
        activeClaims.delete(issue.id);
      }
      continue;
    }
    if (!current.labels.includes("agent:in-progress")) {
      activeClaims.delete(issue.id);
      continue;
    }

    if (
      issue.approvedSha &&
      issue.publication &&
      closeLandedIssue(issue, issue.approvedSha, issue.publication)
    ) {
      continue;
    }

    if (
      issue.approvedSha &&
      issue.checkpoint !== "claimed" &&
      branchLanded(issue.approvedSha, issue.branch)
    ) {
      if (
        issue.checkpoint === "integrated" ||
        issue.checkpoint === "published"
      ) {
        if (
          !issue.integrationHead ||
          !issue.expectedRemoteTree ||
          !branchLanded(issue.approvedSha, issue.integrationHead)
        ) {
          console.error(
            `  ! The integration checkpoint for #${issue.id} is not locally verifiable.`,
          );
          recoveryFailed = true;
          continue;
        }
      }
      if (issue.checkpoint === "published") {
        activeClaims.set(issue.id, {
          ...issue,
          checkpoint: "integrated",
          publication: undefined,
        });
      }
      console.warn(
        `  ↻ Resuming #${issue.id} from its ${activeClaims.get(issue.id)!.checkpoint} checkpoint.`,
      );
      continue;
    }

    gh(
      "issue",
      "comment",
      issue.id,
      "--body",
      `The previous Sandcastle process stopped while working on \`${issue.branch}\`. The branch and any dirty worktree were preserved for inspection. Requeue the issue after deciding whether to keep that work.`,
    );
    if (!setPipelineLabel(issue.id, "agent:blocked")) {
      recoveryFailed = true;
    } else {
      activeClaims.delete(issue.id);
      runHadBlockedWork = true;
    }
  }

  persistRunState();
  if (recoveryFailed) {
    throw new Error("Could not safely recover every claim from the previous run.");
  }
  return [...activeClaims.values()]
    .filter((issue) => issue.approvedSha !== undefined)
    .map((issue) => ({ issue, sha: issue.approvedSha! }));
}

function assertTargetStable(targetBranch: string, expectedHead: string): void {
  const currentBranch = capture("git", ["branch", "--show-current"]);
  const currentHead = capture("git", ["rev-parse", "HEAD"]);
  const dirty = capture("git", ["status", "--porcelain"]);

  if (currentBranch !== targetBranch || currentHead !== expectedHead || dirty) {
    throw new Error(
      `Target checkout changed during the run. Expected clean ${targetBranch} at ${expectedHead}.`,
    );
  }
}

function assertRemoteBaseMatches(targetBranch: string, targetHead: string): void {
  const remoteCommit = remoteBranchCommit(targetBranch);
  const remoteTree = capture("gh", [
    "api",
    `repos/{owner}/{repo}/git/commits/${remoteCommit}`,
    "--jq",
    ".tree.sha",
  ]);
  const localTree = capture("git", ["rev-parse", `${targetHead}^{tree}`]);
  if (remoteTree !== localTree) {
    throw new Error(
      `Remote PR base ${targetBranch} does not match local ${targetHead}. Publish the base branch before an AFK run.`,
    );
  }
}

async function runIssuePipeline(
  issue: ClaimedIssue,
  baseHead: string,
): Promise<{ commits: { sha: string }[]; reason: string }> {
  const issueContext = readIssuePromptContext(issue);
  const sandbox = await sandcastle.createSandbox({
    branch: issue.branch,
    baseBranch: baseHead,
    sandbox: docker({
      imageName: DOCKER_IMAGE,
      env: { ...issue.taskEnvironment, GH_TOKEN: "" },
    }),
    hooks,
    copyToWorktree,
    timeouts: lifecycleTimeouts,
  });
  let pipelineFailed = false;

  try {
    const initialStatus = await sandbox.exec("git status --porcelain");
    if (initialStatus.exitCode !== 0) {
      throw new Error(
        `Could not inspect the issue worktree: ${initialStatus.stderr}`,
      );
    }
    if (initialStatus.stdout.trim()) {
      throw new Error(
        "The issue worktree contains uncommitted changes from an earlier run.",
      );
    }
    const alignment = await sandbox.exec(
      `git merge --ff-only ${baseHead}`,
    );
    if (alignment.exitCode !== 0) {
      throw new Error(
        `The Task branch has diverged from its integration base ${baseHead}.`,
      );
    }

    const implement = await sandbox.run({
      name: `implementer-${issue.id}`,
      // Cursor CLI runs are complete agent sessions and are not resumable by
      // Sandcastle, so every phase gets exactly one harness iteration.
      maxIterations: 1,
      idleTimeoutSeconds: IDLE_TIMEOUT_SECONDS,
      completionTimeoutSeconds: COMPLETION_TIMEOUT_SECONDS,
      signal: phaseSignal(phaseTimeoutMs.implementer),
      agent: sandcastle.cursor(agentModels.implementer),
      promptFile: "./.sandcastle/implement-prompt.md",
      promptArgs: {
        TASK_ID: issue.id,
        ISSUE_TITLE: issue.title,
        BRANCH: issue.branch,
        ISSUE_CONTEXT: issueContext,
      },
    });

    const ahead = await sandbox.exec(
      `git rev-list --count ${baseHead}..HEAD`,
    );
    const aheadCount = Number(ahead.stdout.trim());
    if (
      ahead.exitCode !== 0 ||
      !Number.isSafeInteger(aheadCount) ||
      aheadCount < 0
    ) {
      throw new Error(
        `Could not inspect issue branch progress: ${ahead.stderr}`,
      );
    }
    if (implement.commits.length === 0 && aheadCount === 0) {
      return {
        commits: [],
        reason: "The implementer produced no commits.",
      };
    }
    if (!implement.completionSignal) {
      return {
        commits: [],
        reason:
          "The implementer committed work but did not signal that the ticket was complete.",
      };
    }

    const existingHead = await sandbox.exec("git rev-parse HEAD");
    const existingHeadSha = existingHead.stdout.trim();
    if (
      existingHead.exitCode !== 0 ||
      !/^[0-9a-f]{40}$/.test(existingHeadSha)
    ) {
      throw new Error(
        `Could not resolve issue branch HEAD: ${existingHead.stderr}`,
      );
    }

    const review = await sandbox.run({
      name: `reviewer-${issue.id}`,
      maxIterations: 1,
      idleTimeoutSeconds: IDLE_TIMEOUT_SECONDS,
      completionTimeoutSeconds: COMPLETION_TIMEOUT_SECONDS,
      signal: phaseSignal(phaseTimeoutMs.reviewer),
      agent: sandcastle.cursor(agentModels.reviewer),
      promptFile: "./.sandcastle/review-prompt.md",
      promptArgs: {
        TASK_ID: issue.id,
        ISSUE_TITLE: issue.title,
        BRANCH: issue.branch,
        ISSUE_CONTEXT: issueContext,
      },
    });

    const reviewOutput = parseReview(review.stdout);
    if (reviewOutput.verdict === "blocked") {
      return {
        commits: [],
        reason: `Review blocked the merge: ${reviewOutput.summary}`,
      };
    }

    const status = await sandbox.exec("git status --porcelain");
    if (status.exitCode !== 0) {
      return {
        commits: [],
        reason: `Could not verify the reviewed worktree: ${status.stderr}`,
      };
    }
    if (status.stdout.trim()) {
      return {
        commits: [],
        reason:
          "The reviewer approved a dirty worktree. Uncommitted changes were preserved for inspection.",
      };
    }

    const implementationCommits =
      implement.commits.length > 0
        ? implement.commits
        : [{ sha: existingHeadSha }];
    return {
      commits: [...implementationCommits, ...review.commits],
      reason: reviewOutput.summary,
    };
  } catch (error) {
    pipelineFailed = true;
    throw error;
  } finally {
    try {
      const closed = await sandbox.close();
      if (closed.preservedWorktreePath) {
        console.warn(
          `  ! Preserved dirty worktree for #${issue.id}: ${closed.preservedWorktreePath}`,
        );
      }
    } catch (closeError) {
      if (!pipelineFailed) throw closeError;
      console.error(
        `  ! Cleanup also failed for #${issue.id}: ${describeError(closeError)}`,
      );
    }
  }
}

function temporaryBranch(phase: string, round: number): string {
  return `sandcastle/${phase}-${process.pid}-${round}-${randomUUID().slice(0, 8)}`;
}

function deleteBranchIfMerged(branch: string, targetBranch: string): void {
  if (!branchLanded(branch, targetBranch)) return;
  try {
    // `git branch -d` checks merge ancestry against the current branch, not
    // targetBranch. The explicit check above is the deletion safety gate.
    capture("git", ["branch", "-D", branch]);
  } catch (error) {
    console.warn(
      `  ! Could not remove temporary branch ${branch}: ${describeError(error)}`,
    );
  }
}

async function withDeadline<T>(
  operation: Promise<T>,
  timeoutMs: number,
  label: string,
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`${label} timed out after ${timeoutMs}ms.`)),
      timeoutMs,
    );
  });

  try {
    return await Promise.race([operation, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function buildIntegrationBranch(
  approvedIssues: ApprovedIssue[],
  featureHead: string,
  targetHead: string,
  round: number,
): Promise<{ branch: string; head: string }> {
  const branch = temporaryBranch("integration", round);
  const sandbox = await sandcastle.createSandbox({
    branch,
    baseBranch: featureHead,
    sandbox: docker({
      imageName: DOCKER_IMAGE,
      // Merge and verification need no tracker access.
      env: { GH_TOKEN: "" },
    }),
    hooks,
    copyToWorktree,
    timeouts: lifecycleTimeouts,
  });
  let mergeFailed = false;

  try {
    const merge = await sandbox.run({
      name: `merger-round-${round}`,
      maxIterations: 1,
      idleTimeoutSeconds: IDLE_TIMEOUT_SECONDS,
      completionTimeoutSeconds: COMPLETION_TIMEOUT_SECONDS,
      signal: phaseSignal(phaseTimeoutMs.merger),
      agent: sandcastle.cursor(agentModels.merger),
      promptFile: "./.sandcastle/merge-prompt.md",
      promptArgs: {
        TARGET_HEAD: targetHead,
        BRANCHES: approvedIssues
          .map(({ issue, sha }) => `- \`${issue.branch}\` at commit \`${sha}\``)
          .join("\n"),
        ISSUES: approvedIssues
          .map(({ issue }) => `- ${issue.id}: ${issue.title}`)
          .join("\n"),
      },
    });
    if (!merge.completionSignal) {
      throw new Error(
        "The merger stopped without confirming that its verification passed.",
      );
    }

    const targetAncestry = await sandbox.exec(
      `git merge-base --is-ancestor ${targetHead} HEAD`,
    );
    if (targetAncestry.exitCode !== 0) {
      throw new Error(
        `The integration branch does not contain the pinned target ${targetHead}.`,
      );
    }

    for (const { issue, sha } of approvedIssues) {
      const ancestry = await sandbox.exec(
        `git merge-base --is-ancestor ${sha} HEAD`,
      );
      if (ancestry.exitCode !== 0) {
        throw new Error(
          `The integration branch does not contain the reviewed commit ${sha} for #${issue.id}.`,
        );
      }
    }

    const verification = await withDeadline(
      sandbox.exec("just check"),
      phaseTimeoutMs.merger,
      "Integration verification",
    );
    if (verification.exitCode !== 0) {
      throw new Error(
        `Orchestrator-run just check failed: ${verification.stderr || verification.stdout}`,
      );
    }

    const status = await sandbox.exec("git status --porcelain");
    if (status.exitCode !== 0 || status.stdout.trim()) {
      throw new Error(
        "The integration worktree is not clean after verification.",
      );
    }

    const head = await sandbox.exec("git rev-parse HEAD");
    if (head.exitCode !== 0 || !/^[0-9a-f]{40}$/.test(head.stdout.trim())) {
      throw new Error(`Could not resolve integration HEAD: ${head.stderr}`);
    }
    return { branch, head: head.stdout.trim() };
  } catch (error) {
    mergeFailed = true;
    throw error;
  } finally {
    try {
      const closed = await sandbox.close();
      if (closed.preservedWorktreePath) {
        console.warn(
          `  ! Preserved integration worktree: ${closed.preservedWorktreePath}`,
        );
      }
    } catch (closeError) {
      if (!mergeFailed) throw closeError;
      console.error(
        `  ! Integration cleanup also failed: ${describeError(closeError)}`,
      );
    }
  }
}

async function integrateAndPublishGroup(
  group: ApprovedIssue[],
  baseHead: string,
  targetBranch: string,
  targetHead: string,
  round: number,
): Promise<void> {
  group.sort((left, right) => Number(left.issue.id) - Number(right.issue.id));
  let temporaryIntegration: { branch: string; head: string } | undefined;

  try {
    assertTargetStable(targetBranch, targetHead);
    const resumable = group.every(
      ({ issue }) =>
        issue.checkpoint === "integrated" &&
        issue.integrationHead === group[0]!.issue.integrationHead &&
        issue.expectedRemoteTree === group[0]!.issue.expectedRemoteTree,
    );

    let publishedHead: string;
    let expectedRemoteTree: string;
    if (resumable) {
      publishedHead = group[0]!.issue.integrationHead!;
      expectedRemoteTree = group[0]!.issue.expectedRemoteTree!;
    } else {
      expectedRemoteTree = capture("git", [
        "rev-parse",
        `${baseHead}^{tree}`,
      ]);
      if (group.length === 1 && group[0]!.issue.parent === null) {
        publishedHead = group[0]!.sha;
      } else {
        temporaryIntegration = await buildIntegrationBranch(
          group,
          baseHead,
          targetHead,
          round,
        );
        updateIntegrationBranch(
          group[0]!.issue.integrationBranch,
          baseHead,
          temporaryIntegration.head,
        );
        publishedHead = temporaryIntegration.head;
      }

      for (const { issue, sha } of group) {
        const active = activeClaims.get(issue.id);
        if (active) {
          activeClaims.set(issue.id, {
            ...active,
            checkpoint: "integrated",
            approvedSha: sha,
            integrationHead: publishedHead,
            expectedRemoteTree,
          });
        }
      }
      persistRunState();
    }

    const parent = group[0]!.issue.parent;
    const ready =
      parent === null ||
      !featureHasRemainingAgentTasks(
        parent,
        new Set(group.map(({ issue }) => issue.id)),
      );
    const receipt = publishIntegrationBranch(
      group[0]!.issue,
      publishedHead,
      targetBranch,
      expectedRemoteTree,
      ready,
    );

    for (const { issue, sha } of group) {
      const active = activeClaims.get(issue.id);
      if (active) {
        activeClaims.set(issue.id, {
          ...active,
          checkpoint: "published",
          approvedSha: sha,
          integrationHead: publishedHead,
          expectedRemoteTree,
          publication: receipt,
        });
      }
    }
    persistRunState();

    for (const { issue, sha } of group) {
      const active = activeClaims.get(issue.id);
      if (!active || !closeLandedIssue(active, sha, receipt)) {
        blockIssue(
          issue,
          `The reviewed commit ${sha} was not proven on the published Feature branch.`,
        );
      }
    }
    console.log(
      `Published ${group[0]!.issue.integrationBranch} in ${receipt.prUrl}; closed ${group.length} Task(s).`,
    );
  } finally {
    if (temporaryIntegration) {
      deleteBranchIfMerged(
        temporaryIntegration.branch,
        group[0]!.issue.integrationBranch,
      );
    }
  }
}

async function main(): Promise<void> {
  runPreflight();
  shutdownController.signal.throwIfAborted();
  console.log(
    `AFK limits: ${MAX_PARALLEL_ISSUES} concurrent, ${TASK_BUDGET} Tasks, ${TIME_BUDGET_MINUTES} minutes`,
  );

  // Preflight proves that the checked-out branch is the repository default.
  // It remains the immutable PR base, and the local checkout never moves.
  const targetBranch = capture("git", ["branch", "--show-current"]);
  const expectedTargetHead = capture("git", ["rev-parse", "HEAD"]);
  assertRemoteBaseMatches(targetBranch, expectedTargetHead);
  runStateTargetBranch = targetBranch;
  runStateTargetHead = expectedTargetHead;
  const recoveredIssues = recoverInterruptedRun();
  shutdownController.signal.throwIfAborted();

  if (recoveredIssues.length > 0) {
    const recoveredGroups = new Map<string, ApprovedIssue[]>();
    for (const approved of recoveredIssues) {
      const group =
        recoveredGroups.get(approved.issue.integrationBranch) ?? [];
      group.push(approved);
      recoveredGroups.set(approved.issue.integrationBranch, group);
    }
    for (const group of recoveredGroups.values()) {
      const baseHead =
        group[0]!.issue.checkpoint === "integrated"
          ? group[0]!.issue.integrationHead!
          : prepareIntegrationBase(group[0]!.issue, expectedTargetHead);
      try {
        await integrateAndPublishGroup(
          group,
          baseHead,
          targetBranch,
          expectedTargetHead,
          0,
        );
      } catch (error) {
        throw new Error(
          `Could not resume ${group[0]!.issue.integrationBranch} from its durable checkpoint: ${describeError(error)}`,
        );
      }
    }
  }

  let claimedTaskCount = 0;

  for (let round = 1; claimedTaskCount < TASK_BUDGET; round++) {
    shutdownController.signal.throwIfAborted();
    wholeRunSignal.throwIfAborted();
    console.log(
      `\n=== Round ${round}; ${claimedTaskCount}/${TASK_BUDGET} Task budget used ===\n`,
    );
    assertTargetStable(targetBranch, expectedTargetHead);
    authorizeAutopilotTasks();
    promoteUnblockedQueuedIssues();

    // Phase 1: plan only from the explicitly authorised tracker view. A named
    // throwaway branch prevents a read-only planner mistake from touching the
    // host checkout.
    const authorizedIssues = readAuthorizedIssues();
    if (authorizedIssues === "[]") {
      console.log("No authorised issues to work on. Exiting.");
      break;
    }
    const plannerBranch = temporaryBranch("planner", round);
    const plan = await (async () => {
      try {
        const result = await sandcastle.run({
          sandbox: docker({
            imageName: DOCKER_IMAGE,
            env: { GH_TOKEN: "" },
          }),
          branchStrategy: {
            type: "branch",
            branch: plannerBranch,
            baseBranch: expectedTargetHead,
          },
          name: `planner-round-${round}`,
          maxIterations: 1,
          idleTimeoutSeconds: IDLE_TIMEOUT_SECONDS,
          completionTimeoutSeconds: COMPLETION_TIMEOUT_SECONDS,
          signal: phaseSignal(phaseTimeoutMs.planner),
          timeouts: lifecycleTimeouts,
          agent: sandcastle.cursor(agentModels.planner),
          promptFile: "./.sandcastle/plan-prompt.md",
          promptArgs: {
            MAX_PARALLEL_ISSUES: String(
              Math.min(
                MAX_PARALLEL_ISSUES,
                TASK_BUDGET - claimedTaskCount,
              ),
            ),
            AUTHORIZED_ISSUES: authorizedIssues,
          },
          output: sandcastle.Output.object({ tag: "plan", schema: planSchema }),
        });
        if (result.commits.length > 0 || result.preservedWorktreePath) {
          throw new Error(
            "The planner modified its read-only worktree. The changes were not applied to the target branch.",
          );
        }
        return result;
      } finally {
        deleteBranchIfMerged(plannerBranch, targetBranch);
      }
    })();

    const plannedIssues = plan.output.issues.slice(
      0,
      Math.min(MAX_PARALLEL_ISSUES, TASK_BUDGET - claimedTaskCount),
    );
    if (plannedIssues.length === 0) {
      console.log("No unblocked issues to work on. Exiting.");
      break;
    }

    console.log(
      `Planning complete. ${plannedIssues.length} issue(s) selected:`,
    );
    for (const issue of plannedIssues) {
      console.log(`  ${issue.id}: ${issue.title} → ${issue.branch}`);
    }

    const issues = plannedIssues
      .map((issue) => {
        const claimed = claimIssue(issue);
        if (claimed) {
          const { taskEnvironment: _taskEnvironment, ...persistable } = claimed;
          activeClaims.set(issue.id, persistable);
          persistRunState();
        }
        return claimed;
      })
      .filter((issue): issue is ClaimedIssue => issue !== undefined);
    claimedTaskCount += issues.length;

    if (issues.length === 0) {
      console.warn("No selected issue could be claimed. Stopping.");
      break;
    }

    const integrationBases = new Map<string, string>();
    for (const issue of issues) {
      const base = prepareIntegrationBase(issue, expectedTargetHead);
      const existing = integrationBases.get(issue.integrationBranch);
      if (existing && existing !== base) {
        throw new Error(
          `Feature base changed while claiming ${issue.integrationBranch}.`,
        );
      }
      integrationBases.set(issue.integrationBranch, base);
    }

    // Phase 2: independent Task pipelines fail independently.
    const settled = await Promise.allSettled(
      issues.map((issue) =>
        runIssuePipeline(
          issue,
          integrationBases.get(issue.integrationBranch)!,
        ),
      ),
    );

    for (const [index, outcome] of settled.entries()) {
      if (outcome.status === "rejected") {
        console.error(
          `  ✗ ${issues[index]!.id} (${issues[index]!.branch}) failed: ${describeError(outcome.reason)}`,
        );
      }
    }

    const entries = settled.map((outcome, index) => ({
      outcome,
      issue: issues[index]!,
    }));
    const completedIssues = entries
      .filter(
        (entry) =>
          entry.outcome.status === "fulfilled" &&
          entry.outcome.value.commits.length > 0,
      )
      .map((entry) => entry.issue);
    const completedBranches = completedIssues.map((issue) => issue.branch);

    for (const { outcome, issue } of entries) {
      if (completedIssues.includes(issue)) continue;
      const reason =
        outcome.status === "rejected"
          ? `The run failed: ${describeError(outcome.reason)}`
          : outcome.value.reason;
      blockIssue(issue, reason);
    }

    console.log(
      `\nExecution complete. ${completedBranches.length} branch(es) with approved commits:`,
    );
    for (const branch of completedBranches) console.log(`  ${branch}`);

    if (completedBranches.length === 0) {
      console.log("No approved commits produced. Nothing to merge.");
      continue;
    }

    const approvedIssues: ApprovedIssue[] = completedIssues.map((issue) => {
      const sha = capture("git", [
        "rev-parse",
        "--verify",
        `${issue.branch}^{commit}`,
      ]);
      if (!/^[0-9a-f]{40}$/.test(sha)) {
        throw new Error(`Could not pin the reviewed commit for #${issue.id}.`);
      }
      const { taskEnvironment: _taskEnvironment, ...persistable } = issue;
      const reviewed = {
        ...persistable,
        checkpoint: "reviewed" as const,
        approvedSha: sha,
      };
      activeClaims.set(issue.id, reviewed);
      return { issue: reviewed, sha };
    });
    persistRunState();

    const groups = new Map<string, ApprovedIssue[]>();
    for (const approved of approvedIssues) {
      const group = groups.get(approved.issue.integrationBranch) ?? [];
      group.push(approved);
      groups.set(approved.issue.integrationBranch, group);
    }

    // Phase 3: integrate and publish each Feature independently. Publication
    // is a hard gate for Task closure.
    const publicationFailures: string[] = [];
    for (const [integrationBranch, group] of groups) {
      const baseHead = integrationBases.get(integrationBranch)!;
      try {
        await integrateAndPublishGroup(
          group,
          baseHead,
          targetBranch,
          expectedTargetHead,
          round,
        );
      } catch (error) {
        const reason = `Feature integration or publication failed: ${describeError(error)}. Durable reviewed checkpoints were preserved.`;
        console.error(reason);
        publicationFailures.push(`${integrationBranch}: ${describeError(error)}`);
      }
    }
    if (publicationFailures.length > 0) {
      persistRunState();
      throw new Error(
        `Publication stopped with resumable work: ${publicationFailures.join("; ")}`,
      );
    }
  }

  console.log("\nAll done.");
  if (runHadBlockedWork && process.exitCode === undefined) {
    console.warn("One or more issues require attention.");
    process.exitCode = 2;
  }
}

async function runSandcastle(): Promise<void> {
  const releaseRunLock = acquireRunLock();
  const releaseOnExit = () => releaseRunLock();
  process.once("exit", releaseOnExit);

  for (const signal of ["SIGINT", "SIGTERM"] as const) {
    process.prependOnceListener(signal, () => {
      shutdownController.abort(
        new Error(`The orchestrator was interrupted by ${signal}.`),
      );
      for (const issue of activeClaims.values()) {
        stopClaim(issue, `The orchestrator was interrupted by ${signal}.`);
      }
    });
  }

  try {
    await main();
  } catch (error) {
    console.error(`\nSandcastle stopped: ${describeError(error)}`);
    process.exitCode = 1;
  } finally {
    for (const issue of activeClaims.values()) {
      if (closedPendingCleanup.has(issue.id)) continue;
      stopClaim(
        issue,
        "The orchestrator stopped before it could finalize this issue.",
      );
    }
    process.removeListener("exit", releaseOnExit);
    releaseRunLock();
  }
}

const entryPoint = process.argv[1] ? resolve(process.argv[1]) : undefined;
if (entryPoint === fileURLToPath(import.meta.url)) await runSandcastle();
