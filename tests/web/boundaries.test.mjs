import assert from "node:assert/strict";
import {
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");

function lintPlannerSource(source) {
  const temporaryDirectory = mkdtempSync(
    join(root, "apps/web/app/(planner)/boundary-test-"),
  );
  const violation = join(temporaryDirectory, "page.tsx");
  writeFileSync(violation, source);

  try {
    return spawnSync("pnpm", ["--dir", "apps/web", "exec", "eslint", violation], {
      cwd: root,
      encoding: "utf8",
    });
  } finally {
    rmSync(temporaryDirectory, { force: true, recursive: true });
  }
}

test("Node tests reject live network access", async () => {
  await assert.rejects(
    fetch("https://identity.example/token"),
    /Live network access is disabled in tests/,
  );
});

test("Planner routes cannot import the Operator surface", () => {
  const result = lintPlannerSource(
    'import OperatorPage from "../../(operator)/operator/page";\nexport default OperatorPage;\n',
  );

  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(
    result.stdout,
    /Planner and Operator surfaces must remain separate/,
  );
});

test("UI modules cannot import server-only configuration", () => {
  const result = lintPlannerSource(
    '"use client";\nimport { applicationSession } from "../../../lib/server/session-policy";\nexport default function Page() { return applicationSession.cookieName; }\n',
  );

  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout, /UI routes must cross the Next.js BFF interface/);
});
