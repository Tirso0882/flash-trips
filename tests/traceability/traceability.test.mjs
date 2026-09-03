import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const script = resolve("scripts/traceability.mjs");

function writeFixtureFile(root, path, content) {
  const target = join(root, path);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, content);
}

function validRegistry() {
  const registry = {
    schema_version: 1,
    sources: [
      { id: "ISSUE-40", location: "https://github.com/Tirso0882/flash-trips/issues/40" },
      { id: "ISSUE-115", location: "https://github.com/Tirso0882/flash-trips/issues/115" },
    ],
    owners: [
      { id: "FT-01", source: "ISSUE-40" },
      { id: "E-DECISIONS", source: "ISSUE-115" },
    ],
    approval_bindings: {
      pre_commit_planning: {
        representation: "proposed_result",
        binds: ["proposed_result_fingerprint", "accepted_base_plan_revision", "evidence", "policy"],
      },
      post_commit_handbook_delivery: {
        representation: "committed_plan_revision",
        binds: ["committed_plan_revision", "eligible_snapshot_inputs"],
      },
    },
    conflicts: [
      {
        id: "CONFLICT-001",
        status: "resolved",
        stale_clause: "Responses remain replayable forever.",
        replacement_clause: "Responses remain replayable for 30 days.",
        authority: "ISSUE-40",
        affected_files: ["docs/adr/0002-second.md"],
      },
    ],
    requirements: [
      {
        id: "US-001",
        kind: "user_story",
        text: "A story.",
        source: "ISSUE-40",
        ownership: [{ disposition: "primary_implementation", owner: "FT-01" }],
        references: [],
      },
      {
        id: "ADR-0001",
        kind: "adr",
        text: "First decision.",
        source: "ISSUE-115",
        ownership: [{ disposition: "decision_record", owner: "E-DECISIONS" }],
        references: ["US-001"],
      },
      {
        id: "ADR-0002",
        kind: "adr",
        text: "Second decision.",
        source: "ISSUE-115",
        ownership: [{ disposition: "decision_record", owner: "E-DECISIONS" }],
        references: [],
      },
    ],
  };

  for (let number = 2; number <= 90; number += 1) {
    registry.requirements.push({
      id: `US-${String(number).padStart(3, "0")}`,
      kind: "user_story",
      text: "A story.",
      source: "ISSUE-40",
      ownership: [{ disposition: "primary_implementation", owner: "FT-01" }],
      references: [],
    });
  }
  for (const [prefix, kind, count] of [
    ["IMP", "implementation_decision", 54],
    ["TEST", "testing_decision", 17],
    ["OOS", "out_of_scope_constraint", 15],
  ]) {
    for (let number = 1; number <= count; number += 1) {
      registry.requirements.push({
        id: `${prefix}-${String(number).padStart(3, "0")}`,
        kind,
        text: "A requirement.",
        source: "ISSUE-40",
        ownership: [
          { disposition: "governing_specification", owner: "E-DECISIONS" },
        ],
        references: [],
      });
    }
  }
  for (const id of [
    "E-ACCEPTANCE",
    "E-ACCOMMODATION",
    "E-AZURE-TEST",
    "E-DECISIONS",
    "E-ID",
    "E-PLACES-ROUTES",
    "E-READINESS",
    "E-REASONING",
    "E-RECOVERY",
    "E-SCAFFOLD",
    "E-WX",
  ]) {
    registry.requirements.push({
      id,
      kind: "enabler",
      text: "An enabler.",
      source: "ISSUE-115",
      ownership: [{ disposition: "enabler_ticket", owner: "E-DECISIONS" }],
      references: [],
    });
  }
  return registry;
}

function runTraceability(root, ...args) {
  return spawnSync(process.execPath, [script, "--root", root, ...args], {
    encoding: "utf8",
  });
}

function fixture() {
  const root = mkdtempSync(join(tmpdir(), "flash-trips-traceability-"));
  writeFixtureFile(root, "docs/adr/0001-first.md", "# First decision\n");
  writeFixtureFile(root, "docs/adr/0002-second.md", "# Second decision\n\nResponses remain replayable for 30 days.\n");
  writeFixtureFile(
    root,
    "requirements/registry.json",
    `${JSON.stringify(validRegistry(), null, 2)}\n`,
  );
  const generated = runTraceability(root, "--write");
  assert.equal(generated.status, 0, generated.stderr);
  return root;
}

function mutateRegistry(root, mutate) {
  const path = join(root, "requirements/registry.json");
  const registry = JSON.parse(readFileSync(path, "utf8"));
  mutate(registry);
  writeFileSync(path, `${JSON.stringify(registry, null, 2)}\n`);
}

function assertFailure(root, expected) {
  const result = runTraceability(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, expected);
}

test("accepts a complete registry and current generated report", () => {
  const result = runTraceability(fixture());
  assert.equal(result.status, 0, result.stderr);
});

test("rejects duplicate ADR identifiers", () => {
  const root = fixture();
  writeFixtureFile(root, "docs/adr/0001-duplicate.md", "# Duplicate\n");
  assertFailure(root, /duplicate ADR identifier 0001/);
});

test("rejects orphan requirements", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements[0].ownership = [];
  });
  assertFailure(root, /US-001 must have exactly one ownership disposition/);
});

test("rejects an incomplete requirement family", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements = registry.requirements.filter(
      ({ id }) => id !== "IMP-054",
    );
  });
  assertFailure(
    root,
    /implementation_decision registry is incomplete; missing IMP-054/,
  );
});

test("rejects an invalid ownership disposition", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements[0].ownership[0].disposition = "contributor";
  });
  assertFailure(
    root,
    /US-001 must use ownership disposition primary_implementation/,
  );
});

test("rejects an unknown requirement kind", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements.push({
      id: "UNKNOWN-001",
      kind: "unknown",
      text: "An unknown requirement.",
      source: "ISSUE-40",
      ownership: [{ owner: "E-DECISIONS" }],
      references: [],
    });
  });
  assertFailure(root, /UNKNOWN-001 has unknown requirement kind unknown/);
});

test("rejects multiple primary story owners", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements[0].ownership.push({
      disposition: "primary_implementation",
      owner: "E-DECISIONS",
    });
  });
  assertFailure(root, /US-001 has multiple primary implementation owners/);
});

test("rejects a stale generated coverage report", () => {
  const root = fixture();
  writeFixtureFile(root, "requirements/coverage.md", "# stale\n");
  assertFailure(root, /generated coverage report is stale/);
});

test("rejects unresolved normative conflicts", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.conflicts[0].status = "open";
  });
  assertFailure(root, /CONFLICT-001 is not resolved/);
});

test("rejects unknown references", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.requirements[1].references = ["US-999"];
  });
  assertFailure(root, /ADR-0001 references unknown requirement US-999/);
});

test("rejects stale normative clauses in affected files", () => {
  const root = fixture();
  writeFixtureFile(root, "docs/adr/0002-second.md", "# Second\n\nResponses remain replayable forever.\n");
  assertFailure(root, /CONFLICT-001 stale clause remains active/);
});

test("rejects invalid pre-commit Approval binding", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.approval_bindings.pre_commit_planning.representation = "plan_revision";
  });
  assertFailure(root, /pre-commit planning Approval must represent proposed_result/);
});

test("rejects invalid post-commit Approval binding", () => {
  const root = fixture();
  mutateRegistry(root, (registry) => {
    registry.approval_bindings.post_commit_handbook_delivery.binds = [
      "committed_plan_revision",
    ];
  });
  assertFailure(root, /post-commit Handbook delivery Approval binding is incomplete/);
});
