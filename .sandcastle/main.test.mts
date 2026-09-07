import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { parseReview, planSchema } from "./main.mts";

const issue = (id: string, branch = `sandcastle/issue-${id}`) => ({
  id,
  title: `Issue ${id}`,
  branch,
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

describe("Sandcastle prompt wiring", () => {
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
    assert.equal(source.match(/env:\s*\{\s*GH_TOKEN:\s*""\s*\}/g)?.length, 3);
    assert.match(
      source,
      /"run",\s*"--rm",\s*"--entrypoint",\s*"agent",\s*DOCKER_IMAGE,\s*"--version"/,
    );
  });
});
