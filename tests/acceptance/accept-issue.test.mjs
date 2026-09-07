import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const script = resolve("scripts/accept-issue.mjs");

function fixture(manifest) {
  const root = mkdtempSync(join(tmpdir(), "flash-trips-accept-"));
  const path = join(root, "acceptance/issues/123.json");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(manifest)}\n`);
  return root;
}

function manifest(command) {
  return {
    schema_version: 1,
    issue: 123,
    title: "Make one user-visible change",
    outcome: "The expected behavior is available through its public seam.",
    checks: [
      {
        name: "public behavior",
        command,
      },
    ],
  };
}

function run(root, issue = "123") {
  return spawnSync(process.execPath, [script, issue, "--root", root], {
    encoding: "utf8",
  });
}

test("prints a three-line summary and hides successful check output", () => {
  const root = fixture(
    manifest([
      process.execPath,
      "-e",
      "console.log('verbose passing output')",
    ]),
  );

  try {
    const result = run(root);

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.stdout.trim().split("\n"), [
      "Task #123: Make one user-visible change",
      "Output: The expected behavior is available through its public seam.",
      "PASS: 1 focused acceptance check passed.",
    ]);
    assert.doesNotMatch(result.stdout, /verbose passing output/);
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
});

test("shows captured diagnostics when a focused check fails", () => {
  const root = fixture(
    manifest([
      process.execPath,
      "-e",
      "console.error('useful failure detail'); process.exit(1)",
    ]),
  );

  try {
    const result = run(root);

    assert.equal(result.status, 1);
    assert.match(result.stdout, /FAIL: public behavior/);
    assert.match(result.stderr, /useful failure detail/);
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
});

test("rejects unknown issues and invalid issue arguments", () => {
  const root = fixture(
    manifest([process.execPath, "-e", "process.exit(0)"]),
  );

  try {
    const missing = run(root, "124");
    assert.equal(missing.status, 2);
    assert.match(missing.stderr, /No acceptance check is registered/);

    const invalid = run(root, "../123");
    assert.equal(invalid.status, 2);
    assert.match(invalid.stderr, /positive integer/);
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
});
