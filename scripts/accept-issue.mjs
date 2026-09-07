#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const defaultRoot = resolve(scriptDirectory, "..");

function usage() {
  return "Usage: just accept <issue>";
}

function parseArguments(argv) {
  let root = defaultRoot;
  let issue;

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--root") {
      const value = argv[index + 1];
      if (!value) throw new Error(`${usage()}\n--root requires a path.`);
      root = resolve(value);
      index += 1;
      continue;
    }
    if (issue !== undefined) throw new Error(usage());
    issue = argument;
  }

  if (!issue || !/^[1-9]\d*$/.test(issue)) {
    throw new Error(`${usage()}\nThe issue must be a positive integer.`);
  }

  return { issue: Number(issue), root };
}

function requireObject(value, description) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${description} must be an object.`);
  }
  return value;
}

function requireShortText(value, description) {
  if (
    typeof value !== "string" ||
    value.trim().length === 0 ||
    value.length > 240 ||
    /[\r\n]/.test(value)
  ) {
    throw new Error(
      `${description} must be one non-empty line of at most 240 characters.`,
    );
  }
  return value.trim();
}

function readManifest(root, requestedIssue) {
  const path = join(root, "acceptance", "issues", `${requestedIssue}.json`);
  if (!existsSync(path)) {
    throw new Error(
      `No acceptance check is registered for issue #${requestedIssue}.`,
    );
  }

  let parsed;
  try {
    parsed = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`Could not read ${relative(root, path)}: ${error.message}`);
  }

  const manifest = requireObject(parsed, "Acceptance manifest");
  if (manifest.schema_version !== 1) {
    throw new Error("Acceptance manifest schema_version must be 1.");
  }
  if (manifest.issue !== requestedIssue) {
    throw new Error(
      `Acceptance manifest issue ${manifest.issue} does not match #${requestedIssue}.`,
    );
  }

  const title = requireShortText(manifest.title, "Acceptance title");
  const outcome = requireShortText(manifest.outcome, "Acceptance outcome");
  if (!Array.isArray(manifest.checks) || manifest.checks.length === 0) {
    throw new Error("Acceptance manifest must contain at least one check.");
  }

  const checks = manifest.checks.map((value, index) => {
    const check = requireObject(value, `Acceptance check ${index + 1}`);
    const name = requireShortText(check.name, `Acceptance check ${index + 1} name`);
    if (
      !Array.isArray(check.command) ||
      check.command.length === 0 ||
      check.command.some(
        (part) =>
          typeof part !== "string" ||
          part.length === 0 ||
          /[\0\r\n]/.test(part),
      )
    ) {
      throw new Error(
        `Acceptance check ${index + 1} command must be a non-empty string array.`,
      );
    }

    const cwd =
      check.cwd === undefined
        ? root
        : resolve(root, requireShortText(check.cwd, `Acceptance check ${index + 1} cwd`));
    const relativeCwd = relative(root, cwd);
    if (isAbsolute(relativeCwd) || relativeCwd.startsWith("..")) {
      throw new Error(`Acceptance check ${index + 1} cwd leaves the repository.`);
    }

    return { command: check.command, cwd, name };
  });

  return { checks, issue: requestedIssue, outcome, title };
}

function writeCapturedOutput(result) {
  if (result.stdout) process.stderr.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) process.stderr.write(`${result.error.message}\n`);
}

function runAcceptance(manifest) {
  for (const check of manifest.checks) {
    const [executable, ...args] = check.command;
    const result = spawnSync(executable, args, {
      cwd: check.cwd,
      encoding: "utf8",
      env: process.env,
      maxBuffer: 20 * 1024 * 1024,
    });

    if (result.error || result.status !== 0) {
      console.log(`Task #${manifest.issue}: ${manifest.title}`);
      console.log(`Output: ${manifest.outcome}`);
      console.log(`FAIL: ${check.name}`);
      writeCapturedOutput(result);
      return 1;
    }
  }

  console.log(`Task #${manifest.issue}: ${manifest.title}`);
  console.log(`Output: ${manifest.outcome}`);
  console.log(
    `PASS: ${manifest.checks.length} focused acceptance check${
      manifest.checks.length === 1 ? "" : "s"
    } passed.`,
  );
  return 0;
}

export function main(argv = process.argv.slice(2)) {
  try {
    const { issue, root } = parseArguments(argv);
    return runAcceptance(readManifest(root, issue));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main();
}
