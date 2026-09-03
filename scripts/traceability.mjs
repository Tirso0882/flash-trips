#!/usr/bin/env node

import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { join, relative, resolve } from "node:path";

const args = process.argv.slice(2);
const rootIndex = args.indexOf("--root");
const root = resolve(rootIndex === -1 ? "." : args[rootIndex + 1]);
const writeReport = args.includes("--write");
const registryPath = join(root, "requirements/registry.json");
const reportPath = join(root, "requirements/coverage.md");
const errors = [];

function fail(message) {
  errors.push(message);
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`cannot read registry: ${error.message}`);
    return {};
  }
}

function duplicateValues(values) {
  const seen = new Set();
  const duplicates = new Set();
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value);
    seen.add(value);
  }
  return [...duplicates].sort();
}

function filesBelow(path) {
  if (!existsSync(path)) return [];
  const files = [];
  for (const entry of readdirSync(path).sort()) {
    const target = join(path, entry);
    if (statSync(target).isDirectory()) {
      files.push(...filesBelow(target));
    } else {
      files.push(target);
    }
  }
  return files;
}

function sameMembers(actual, expected) {
  return (
    Array.isArray(actual) &&
    actual.length === expected.length &&
    [...actual].sort().every((value, index) => value === [...expected].sort()[index])
  );
}

const expectedRequirementIds = {
  user_story: Array.from({ length: 90 }, (_, index) =>
    `US-${String(index + 1).padStart(3, "0")}`),
  implementation_decision: Array.from({ length: 54 }, (_, index) =>
    `IMP-${String(index + 1).padStart(3, "0")}`),
  testing_decision: Array.from({ length: 17 }, (_, index) =>
    `TEST-${String(index + 1).padStart(3, "0")}`),
  out_of_scope_constraint: Array.from({ length: 15 }, (_, index) =>
    `OOS-${String(index + 1).padStart(3, "0")}`),
  enabler: [
    "E-ACCEPTANCE",
    "E-ACCOMMODATION",
    "E-AZURE-TEST",
    "E-DECISIONS",
    "E-ID",
    "E-PLACES-ROUTES",
    "E-READINESS",
    "E-REASONING",
    "E-RECOVERY",
    "E-WX",
  ],
};

const dispositionByKind = {
  user_story: "primary_implementation",
  implementation_decision: "governing_specification",
  testing_decision: "governing_specification",
  out_of_scope_constraint: "governing_specification",
  adr: "decision_record",
  enabler: "enabler_ticket",
};

function validateApprovalBindings(bindings = {}) {
  const preCommit = bindings.pre_commit_planning ?? {};
  if (preCommit.representation !== "proposed_result") {
    fail("pre-commit planning Approval must represent proposed_result");
  }
  if (
    !sameMembers(preCommit.binds, [
      "proposed_result_fingerprint",
      "accepted_base_plan_revision",
      "evidence",
      "policy",
    ])
  ) {
    fail("pre-commit planning Approval binding is incomplete");
  }

  const postCommit = bindings.post_commit_handbook_delivery ?? {};
  if (postCommit.representation !== "committed_plan_revision") {
    fail("post-commit Handbook delivery Approval must represent committed_plan_revision");
  }
  if (
    !sameMembers(postCommit.binds, [
      "committed_plan_revision",
      "eligible_snapshot_inputs",
    ])
  ) {
    fail("post-commit Handbook delivery Approval binding is incomplete");
  }
}

function validateAdrs(requirements) {
  const adrFiles = filesBelow(join(root, "docs/adr")).filter((path) =>
    /^\d{4}-.+\.md$/.test(path.split("/").at(-1)),
  );
  const adrNumbers = adrFiles.map((path) => path.split("/").at(-1).slice(0, 4));
  for (const number of duplicateValues(adrNumbers)) {
    fail(`duplicate ADR identifier ${number}`);
  }

  const registered = new Map(
    requirements
      .filter((requirement) => requirement.kind === "adr")
      .map((requirement) => [requirement.id.replace("ADR-", ""), requirement]),
  );
  for (const number of adrNumbers) {
    if (!registered.has(number)) fail(`ADR-${number} is not registered`);
  }
  for (const number of registered.keys()) {
    if (!adrNumbers.includes(number)) fail(`ADR-${number} has no decision file`);
  }
}

function validateRegistry(registry) {
  if (registry.schema_version !== 1) fail("unsupported registry schema_version");

  const sources = Array.isArray(registry.sources) ? registry.sources : [];
  const owners = Array.isArray(registry.owners) ? registry.owners : [];
  const requirements = Array.isArray(registry.requirements)
    ? registry.requirements
    : [];
  const conflicts = Array.isArray(registry.conflicts) ? registry.conflicts : [];
  const sourceIds = new Set(sources.map(({ id }) => id));
  const ownerIds = new Set(owners.map(({ id }) => id));
  const requirementIds = new Set(requirements.map(({ id }) => id));

  for (const id of duplicateValues(sources.map(({ id }) => id))) {
    fail(`duplicate source identifier ${id}`);
  }
  for (const id of duplicateValues(owners.map(({ id }) => id))) {
    fail(`duplicate owner identifier ${id}`);
  }
  for (const id of duplicateValues(requirements.map(({ id }) => id))) {
    fail(`duplicate requirement identifier ${id}`);
  }
  for (const [kind, expectedIds] of Object.entries(expectedRequirementIds)) {
    const actualIds = requirements
      .filter((requirement) => requirement.kind === kind)
      .map((requirement) => requirement.id);
    if (!sameMembers(actualIds, expectedIds)) {
      const missing = expectedIds.filter((id) => !actualIds.includes(id));
      const unexpected = actualIds.filter((id) => !expectedIds.includes(id));
      fail(
        `${kind} registry is incomplete` +
          (missing.length ? `; missing ${missing.join(", ")}` : "") +
          (unexpected.length ? `; unexpected ${unexpected.join(", ")}` : ""),
      );
    }
  }
  for (const owner of owners) {
    if (!sourceIds.has(owner.source)) {
      fail(`${owner.id} references unknown source ${owner.source}`);
    }
  }

  for (const requirement of requirements) {
    if (!requirement.id || !requirement.kind || !requirement.text) {
      fail("every requirement needs id, kind, and text");
      continue;
    }
    if (!(requirement.kind in dispositionByKind)) {
      fail(
        `${requirement.id} has unknown requirement kind ${requirement.kind}`,
      );
    }
    if (!sourceIds.has(requirement.source)) {
      fail(`${requirement.id} references unknown source ${requirement.source}`);
    }
    const ownership = Array.isArray(requirement.ownership)
      ? requirement.ownership
      : [];
    const primaryOwners = ownership.filter(
      ({ disposition }) => disposition === "primary_implementation",
    );
    if (requirement.kind === "user_story" && primaryOwners.length > 1) {
      fail(`${requirement.id} has multiple primary implementation owners`);
    }
    if (ownership.length !== 1) {
      fail(`${requirement.id} must have exactly one ownership disposition`);
    }
    for (const entry of ownership) {
      const expectedDisposition = dispositionByKind[requirement.kind];
      if (entry.disposition !== expectedDisposition) {
        fail(
          `${requirement.id} must use ownership disposition ${expectedDisposition}`,
        );
      }
      if (!ownerIds.has(entry.owner)) {
        fail(`${requirement.id} references unknown owner ${entry.owner}`);
      }
    }
    for (const reference of requirement.references ?? []) {
      if (!requirementIds.has(reference)) {
        fail(`${requirement.id} references unknown requirement ${reference}`);
      }
    }
  }

  for (const conflict of conflicts) {
    if (conflict.status !== "resolved") {
      fail(`${conflict.id} is not resolved`);
    }
    if (!sourceIds.has(conflict.authority)) {
      fail(`${conflict.id} references unknown authority ${conflict.authority}`);
    }
    if (
      !conflict.stale_clause ||
      !conflict.replacement_clause ||
      !Array.isArray(conflict.affected_files) ||
      conflict.affected_files.length === 0
    ) {
      fail(`${conflict.id} is missing ledger fields`);
      continue;
    }
    for (const file of conflict.affected_files) {
      const path = join(root, file);
      if (!existsSync(path)) {
        fail(`${conflict.id} references missing affected file ${file}`);
        continue;
      }
      const content = readFileSync(path, "utf8");
      const contentWithoutReplacement = content.replaceAll(
        conflict.replacement_clause,
        "",
      );
      if (contentWithoutReplacement.includes(conflict.stale_clause)) {
        fail(`${conflict.id} stale clause remains active in ${file}`);
      }
      if (!content.includes(conflict.replacement_clause)) {
        fail(`${conflict.id} replacement clause is missing from ${file}`);
      }
    }
  }

  validateApprovalBindings(registry.approval_bindings);
  validateAdrs(requirements);
  return { conflicts, requirements };
}

function renderCoverage({ conflicts, requirements }) {
  const counts = new Map();
  for (const requirement of requirements) {
    counts.set(requirement.kind, (counts.get(requirement.kind) ?? 0) + 1);
  }

  const lines = [
    "# Requirement coverage",
    "",
    "Generated by `npm run traceability -- --write`. Do not edit by hand.",
    "",
    "## Summary",
    "",
    `Registered requirements: ${requirements.length}`,
    ...[...counts.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([kind, count]) => `${kind}: ${count}`),
    "",
    "Every requirement below has exactly one ownership disposition.",
    "",
    "## Coverage",
    "",
  ];

  for (const requirement of [...requirements].sort((a, b) =>
    a.id.localeCompare(b.id),
  )) {
    const ownership = requirement.ownership[0];
    lines.push(
      `### ${requirement.id}`,
      "",
      `Kind: ${requirement.kind}`,
      `Source: ${requirement.source}`,
      `Ownership: ${ownership.disposition} by ${ownership.owner}`,
      `Requirement: ${requirement.text}`,
      "",
    );
  }

  lines.push("## Conflict ledger", "");
  for (const conflict of [...conflicts].sort((a, b) =>
    a.id.localeCompare(b.id),
  )) {
    lines.push(
      `### ${conflict.id}`,
      "",
      `Status: ${conflict.status}`,
      `Authority: ${conflict.authority}`,
      `Affected files: ${conflict.affected_files.join(", ")}`,
      `Superseded wording: ${conflict.stale_clause}`,
      `Authoritative replacement: ${conflict.replacement_clause}`,
      "",
    );
  }
  return `${lines.join("\n")}\n`;
}

const registry = readJson(registryPath);
const validated = validateRegistry(registry);
const expectedReport = errors.length === 0 ? renderCoverage(validated) : null;

if (!writeReport && expectedReport !== null) {
  if (!existsSync(reportPath) || readFileSync(reportPath, "utf8") !== expectedReport) {
    fail("generated coverage report is stale; run npm run traceability -- --write");
  }
}

if (errors.length > 0) {
  for (const error of errors) process.stderr.write(`traceability: ${error}\n`);
  process.exitCode = 1;
} else if (writeReport) {
  writeFileSync(reportPath, expectedReport);
  process.stdout.write(
    `wrote ${relative(root, reportPath)} with ${validated.requirements.length} requirements\n`,
  );
} else {
  process.stdout.write(
    `traceability valid: ${validated.requirements.length} requirements\n`,
  );
}
