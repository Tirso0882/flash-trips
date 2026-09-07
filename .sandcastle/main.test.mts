import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import {
  AUTOPILOT_FEATURE_QUERY,
  hasExternalPreRunGates,
  parseAfkEnvironment,
  parseReview,
  planSchema,
  positiveIntegerSetting,
  resolveTaskEnvironment,
  selectAutopilotAuthorizations,
} from "./main.mts";

const issue = (id: string, branch = `sandcastle/task-${id}`) => ({
  id,
  title: `Issue ${id}`,
  branch,
});

const task = (
  id: number,
  labels = ["ready-for-agent"],
  blockedBy: number[] = [],
  body = "",
) => ({
  id,
  body,
  state: "OPEN" as const,
  labels,
  subIssueCount: 0,
  blockedBy,
  labelsTruncated: false,
  blockersTruncated: false,
});

const feature = (
  id: number,
  tasks: ReturnType<typeof task>[],
  labels = ["agent:autopilot"],
) => ({
  id,
  labels,
  labelsTruncated: false,
  tasksTruncated: false,
  tasks,
});

describe("Sandcastle plan validation", () => {
  it("accepts at most three distinct issue branches", () => {
    const result = planSchema.parse({
      issues: [issue("1"), issue("2"), issue("3")],
    });

    assert.equal(result.issues.length, 3);
  });

  it("rejects duplicate issue ids and branches", () => {
    assert.throws(() =>
      planSchema.parse({
        issues: [issue("1"), issue("1")],
      }),
    );
    assert.throws(() =>
      planSchema.parse({
        issues: [issue("1"), issue("2", "sandcastle/issue-1")],
      }),
    );
  });

  it("rejects excess work and unsafe branch names", () => {
    assert.throws(() =>
      planSchema.parse({
        issues: [issue("1"), issue("2"), issue("3"), issue("4")],
      }),
    );
    assert.throws(() =>
      planSchema.parse({
        issues: [issue("1", "main")],
      }),
    );
  });
});

describe("Sandcastle review parsing", () => {
  it("parses one validated review block", () => {
    assert.deepEqual(
      parseReview(
        '<review>{"verdict":"approved","summary":"Checks passed."}</review>',
      ),
      { verdict: "approved", summary: "Checks passed." },
    );
  });

  it("rejects missing, duplicate, malformed, and unknown verdicts", () => {
    assert.throws(() => parseReview("approved"));
    assert.throws(() =>
      parseReview(
        '<review>{"verdict":"approved","summary":"One"}</review>' +
          '<review>{"verdict":"approved","summary":"Two"}</review>',
      ),
    );
    assert.throws(() => parseReview("<review>{bad json}</review>"));
    assert.throws(() =>
      parseReview(
        '<review>{"verdict":"maybe","summary":"Not a gate."}</review>',
      ),
    );
  });
});

describe("Sandcastle Feature autopilot", () => {
  it("discovers Features without nesting their Task graph", () => {
    assert.doesNotMatch(AUTOPILOT_FEATURE_QUERY, /\bsubIssues\s*\(/);
  });

  it("authorizes the ready frontier under each opted-in Feature", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([
        feature(117, [task(241), task(240)]),
        feature(118, [task(250)]),
      ]),
      [
        { id: "240", label: "agent:implement" },
        { id: "241", label: "agent:implement" },
        { id: "250", label: "agent:implement" },
      ],
    );
  });

  it("queues the first Task when its declared blocker remains open", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([feature(117, [task(240, undefined, [239])])]),
      [{ id: "240", label: "agent:queued" }],
    );
  });

  it("skips Tasks needing attention without suppressing siblings", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([
        feature(117, [
          task(240, ["ready-for-agent", "agent:blocked"]),
          task(241),
        ]),
        feature(118, [task(250, ["needs-info"]), task(251)]),
      ]),
      [
        { id: "241", label: "agent:implement" },
        { id: "251", label: "agent:implement" },
      ],
    );
  });

  it("does not reauthorize Tasks already owned by the pipeline", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([
        feature(117, [
          task(240, ["ready-for-agent", "agent:queued"], [239]),
          task(241),
        ]),
      ]),
      [{ id: "241", label: "agent:implement" }],
    );
  });

  it("ignores Features without the explicit autopilot label", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([
        feature(117, [task(240)], ["ready-for-agent"]),
      ]),
      [],
    );
  });

  it("blocks a Task with uncleared external gates", () => {
    assert.deepEqual(
      selectAutopilotAuthorizations([
        feature(117, [
          task(
            245,
            ["ready-for-agent"],
            [],
            "## External human or evidence gates\n\n- Disposable tenant",
          ),
        ]),
      ]),
      [
        {
          id: "245",
          label: "agent:blocked",
          reason:
            "Task #245 has external pre-run gates. Apply agent:gates-cleared only after its disposable resources and credentials are ready.",
        },
      ],
    );
  });
});

describe("Sandcastle AFK environment", () => {
  it("parses only a strict names-only environment section", () => {
    assert.deepEqual(
      parseAfkEnvironment(
        "## AFK environment\n\n- FLASH_TRIPS_OIDC_CLIENT_ID\n- FLASH_TRIPS_OIDC_ISSUER\n",
      ),
      ["FLASH_TRIPS_OIDC_CLIENT_ID", "FLASH_TRIPS_OIDC_ISSUER"],
    );
    assert.throws(() =>
      parseAfkEnvironment("## AFK environment\n\n- TOKEN=value"),
    );
  });

  it("detects non-empty external gate sections", () => {
    assert.equal(
      hasExternalPreRunGates(
        "## External human or evidence gates\n\n- Tenant configured",
      ),
      true,
    );
    assert.equal(hasExternalPreRunGates("## Other\n\nNone"), false);
  });

  it("validates positive work-budget settings", () => {
    const previous = process.env.TEST_SANDCASTLE_BUDGET;
    process.env.TEST_SANDCASTLE_BUDGET = "12";
    assert.equal(positiveIntegerSetting("TEST_SANDCASTLE_BUDGET", 3, 20), 12);
    process.env.TEST_SANDCASTLE_BUDGET = "0";
    assert.throws(() =>
      positiveIntegerSetting("TEST_SANDCASTLE_BUDGET", 3, 20),
    );
    if (previous === undefined) delete process.env.TEST_SANDCASTLE_BUDGET;
    else process.env.TEST_SANDCASTLE_BUDGET = previous;
  });

  it("passes only locally allowlisted Task credentials", () => {
    process.env.SANDCASTLE_TASK_ENV_ALLOWLIST = "DISPOSABLE_CLIENT_SECRET";
    process.env.DISPOSABLE_CLIENT_SECRET = "not-for-diagnostics";
    assert.deepEqual(
      resolveTaskEnvironment(
        "## AFK environment\n\n- DISPOSABLE_CLIENT_SECRET",
      ),
      { DISPOSABLE_CLIENT_SECRET: "not-for-diagnostics" },
    );
    assert.throws(
      () => resolveTaskEnvironment("## AFK environment\n\n- GH_TOKEN"),
      (error: unknown) =>
        error instanceof Error &&
        error.message.includes("orchestrator credential") &&
        !error.message.includes("not-for-diagnostics"),
    );
    delete process.env.SANDCASTLE_TASK_ENV_ALLOWLIST;
    delete process.env.DISPOSABLE_CLIENT_SECRET;
  });
});

describe("Sandcastle prompt wiring", () => {
  it("requires the repository default branch as the PR base", () => {
    const source = readFileSync(new URL("./main.mts", import.meta.url), "utf8");

    assert.match(source, /function repositoryDefaultBranch\(\)/);
    assert.match(source, /branch !== defaultBranch/);
    assert.match(
      source,
      /Sandcastle must run from the default branch \$\{defaultBranch\}/,
    );
  });

  it("lets Sandcastle supply its reserved target branch argument", () => {
    const source = readFileSync(new URL("./main.mts", import.meta.url), "utf8");
    const prompt = readFileSync(
      new URL("./review-prompt.md", import.meta.url),
      "utf8",
    );

    assert.doesNotMatch(source, /\bTARGET_BRANCH\s*:/);
    assert.match(prompt, /\{\{TARGET_BRANCH\}\}/);
  });

  it("keeps GitHub tracker access on the host", () => {
    const source = readFileSync(new URL("./main.mts", import.meta.url), "utf8");
    const prompts = ["plan", "implement", "review"].map((name) =>
      readFileSync(new URL(`./${name}-prompt.md`, import.meta.url), "utf8"),
    );

    for (const prompt of prompts) {
      assert.doesNotMatch(prompt, /(?:^|\s)gh\s+(?:api|issue)\b/);
    }
    assert.match(source, /AUTHORIZED_ISSUES:\s*authorizedIssues/);
    assert.equal(source.match(/ISSUE_CONTEXT:\s*issueContext/g)?.length, 2);
    assert.equal(source.match(/env:\s*\{\s*GH_TOKEN:\s*""\s*\}/g)?.length, 2);
    assert.match(
      source,
      /env:\s*\{\s*\.\.\.issue\.taskEnvironment,\s*GH_TOKEN:\s*""\s*\}/,
    );
    assert.match(
      source,
      /"run",\s*"--rm",\s*"--entrypoint",\s*"agent",\s*DOCKER_IMAGE,\s*"--version"/,
    );
  });
});
