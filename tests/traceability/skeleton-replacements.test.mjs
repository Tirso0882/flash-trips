import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const markerPattern =
  /SKELETON_REPLACEMENT: issue (\d+) \((FT-\d+)\) (?:deepens|replaces)/g;

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return extname(path) === ".py" ? [path] : [];
  });
}

function markerEntries() {
  return sourceFiles(join(root, "src")).flatMap((path) => {
    const source = readFileSync(path, "utf8");
    return [...source.matchAll(markerPattern)].map((match) => ({
      feature: match[2],
      issue: Number(match[1]),
    }));
  });
}

test("every walking-skeleton replacement marker names a registered open Feature issue", () => {
  const registry = JSON.parse(
    readFileSync(join(root, "requirements/registry.json"), "utf8"),
  );
  const verified = JSON.parse(
    readFileSync(join(root, "requirements/skeleton-replacements.json"), "utf8"),
  );
  const sourceById = new Map(
    registry.sources.map((source) => [source.id, source.location]),
  );
  const markers = markerEntries();
  const markerFeatures = new Set(markers.map(({ feature }) => feature));
  const ownerIssue = new Map(
    registry.owners
      .filter((owner) => markerFeatures.has(owner.id))
      .map((owner) => {
        const location = sourceById.get(owner.source);
        const issueMatch = location?.match(/\/issues\/(\d+)$/);
        assert.ok(issueMatch);
        return [owner.id, Number(issueMatch[1])];
      }),
  );
  const openIssues = new Map(
    verified.issues.map((issue) => [
      `${issue.feature}:${issue.issue}`,
      issue.state,
    ]),
  );
  assert.ok(markers.length > 0);
  for (const marker of markers) {
    assert.equal(ownerIssue.get(marker.feature), marker.issue);
    assert.equal(openIssues.get(`${marker.feature}:${marker.issue}`), "OPEN");
  }
  assert.deepEqual(
    new Set(markers.map(({ feature, issue }) => `${feature}:${issue}`)),
    new Set(openIssues.keys()),
  );

  if (process.env.FLASH_TRIPS_VERIFY_OPEN_ISSUES === "1") {
    for (const marker of new Map(
      markers.map(({ feature, issue }) => [issue, feature]),
    )) {
      const [issue, feature] = marker;
      const result = spawnSync(
        "gh",
        ["issue", "view", String(issue), "--json", "state,title"],
        { cwd: root, encoding: "utf8" },
      );
      assert.equal(result.status, 0, result.stderr);
      const live = JSON.parse(result.stdout);
      assert.equal(live.state, "OPEN");
      assert.match(live.title, new RegExp(`^\\[${feature}\\]`));
    }
  }
});
