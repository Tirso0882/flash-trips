import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const root = resolve(import.meta.dirname, "../..");
const postgresPassword = "journey-postgres-only";
const runtimePassword = "journey-runtime-only";
const migrationPassword = "journey-migration-only";
const plannerId = "01991e28-1d65-7000-8000-000000000001";
const otherPlannerId = "01991e28-1d65-7000-8000-000000000002";
export const otherPlannerTripId = "01991e28-1d65-7000-8000-000000000003";
const otherPlannerStayId = "01991e28-1d65-7000-8000-000000000004";
const localSubject = "local-subject";

interface LocalProvider {
  ca_file: string;
  discovery_url: string;
  issuer: string;
  jwks_uri: string;
}

export interface ManagedProcess {
  child: ChildProcess;
  name: string;
  output: () => string;
}

export interface DisposablePostgres {
  containerName: string;
  migrationUrl: string;
  query: (sql: string) => string;
  runtimeUrl: string;
  stop: () => void;
}

export interface JourneyHarness {
  baseUrl: string;
  stop: () => Promise<void>;
}

function commandFailure(
  command: string,
  result: ReturnType<typeof spawnSync>,
): Error {
  return new Error(
    `${command} failed with exit code ${result.status ?? "unknown"}\n` +
      `${String(result.stdout ?? "")}${String(result.stderr ?? "")}`,
  );
}

function run(
  command: string,
  args: string[],
  options: { env?: NodeJS.ProcessEnv; input?: string } = {},
): string {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    env: options.env ?? process.env,
    input: options.input,
  });
  if (result.error !== undefined || result.status !== 0) {
    throw commandFailure(`${command} ${args.join(" ")}`, result);
  }
  return result.stdout;
}

export function startProcess(
  name: string,
  command: string,
  args: string[],
  env: NodeJS.ProcessEnv,
): ManagedProcess {
  const child = spawn(command, args, {
    cwd: root,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const chunks: Buffer[] = [];
  for (const stream of [child.stdout, child.stderr]) {
    stream?.on("data", (chunk: Buffer) => {
      chunks.push(chunk);
      if (chunks.length > 200) chunks.shift();
    });
  }
  return {
    child,
    name,
    output: () => Buffer.concat(chunks).toString("utf8"),
  };
}

async function stopProcess(process: ManagedProcess | undefined): Promise<void> {
  if (process === undefined || process.child.exitCode !== null) return;
  process.child.kill("SIGTERM");
  await Promise.race([
    new Promise<void>((resolveExit) => {
      process.child.once("exit", () => resolveExit());
    }),
    delay(5_000),
  ]);
  if (process.child.exitCode === null) process.child.kill("SIGKILL");
}

export async function waitForHttp(
  name: string,
  url: string,
  process?: ManagedProcess,
  timeoutMilliseconds = 45_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMilliseconds;
  let lastFailure = "no response";
  while (Date.now() < deadline) {
    if (
      process?.child.exitCode !== null &&
      process?.child.exitCode !== undefined
    ) {
      throw new Error(
        `${name} exited before becoming ready\n${process.output()}`,
      );
    }
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastFailure = `HTTP ${response.status}`;
    } catch (error) {
      lastFailure = error instanceof Error ? error.message : String(error);
    }
    await delay(200);
  }
  throw new Error(
    `${name} did not become ready: ${lastFailure}\n${process?.output() ?? ""}`,
  );
}

async function waitForLocalHttps(
  name: string,
  url: string,
  process: ManagedProcess,
): Promise<void> {
  for (let attempt = 0; attempt < 225; attempt += 1) {
    if (process.child.exitCode !== null) {
      throw new Error(
        `${name} exited before becoming ready\n${process.output()}`,
      );
    }
    const response = spawnSync(
      "curl",
      ["--fail", "--insecure", "--silent", url],
      { cwd: root, stdio: "ignore" },
    );
    if (response.status === 0) return;
    await delay(200);
  }
  throw new Error(`${name} did not become ready\n${process.output()}`);
}

async function freePort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("Could not allocate a journey port");
  }
  await new Promise<void>((resolveClose, reject) => {
    server.close((error) =>
      error === undefined ? resolveClose() : reject(error),
    );
  });
  return address.port;
}

export function dockerContainerExists(containerName: string): boolean {
  const result = spawnSync("docker", ["inspect", containerName], {
    cwd: root,
    stdio: "ignore",
  });
  return result.status === 0;
}

async function startDisposablePostgres(): Promise<DisposablePostgres> {
  const containerName = `flash-trips-journey-${randomUUID()}`;
  run("docker", [
    "run",
    "--detach",
    "--rm",
    "--name",
    containerName,
    "--env",
    `POSTGRES_PASSWORD=${postgresPassword}`,
    "--publish",
    "127.0.0.1::5432",
    "postgres:17-alpine",
  ]);

  try {
    let consecutiveReadyChecks = 0;
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const ready = spawnSync(
        "docker",
        [
          "exec",
          containerName,
          "pg_isready",
          "-U",
          "postgres",
          "-d",
          "postgres",
        ],
        { cwd: root, stdio: "ignore" },
      );
      consecutiveReadyChecks =
        ready.status === 0 ? consecutiveReadyChecks + 1 : 0;
      if (consecutiveReadyChecks === 3) break;
      if (attempt === 79) throw new Error("PostgreSQL did not become ready");
      await delay(200);
    }
    const mapping = run("docker", ["port", containerName, "5432/tcp"]).trim();
    const port = mapping.slice(mapping.lastIndexOf(":") + 1);
    const setup = `
CREATE ROLE flash_trips_migration LOGIN PASSWORD '${migrationPassword}';
CREATE ROLE flash_trips_runtime LOGIN PASSWORD '${runtimePassword}';
CREATE DATABASE flash_trips OWNER flash_trips_migration;
GRANT CONNECT ON DATABASE flash_trips TO flash_trips_runtime;
`;
    run(
      "docker",
      ["exec", "-i", containerName, "psql", "-U", "postgres", "-d", "postgres"],
      { input: setup },
    );
    const grants = `
GRANT USAGE ON SCHEMA public TO flash_trips_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE flash_trips_migration IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flash_trips_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE flash_trips_migration IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO flash_trips_runtime;
`;
    run(
      "docker",
      [
        "exec",
        "-i",
        containerName,
        "psql",
        "-U",
        "postgres",
        "-d",
        "flash_trips",
      ],
      { input: grants },
    );
    const migrationUrl =
      `postgresql+asyncpg://flash_trips_migration:${migrationPassword}` +
      `@127.0.0.1:${port}/flash_trips`;
    const runtimeUrl =
      `postgresql+asyncpg://flash_trips_runtime:${runtimePassword}` +
      `@127.0.0.1:${port}/flash_trips`;
    run("uv", ["run", "alembic", "upgrade", "head"], {
      env: { ...process.env, MIGRATION_DATABASE_URL: migrationUrl },
    });
    return {
      containerName,
      migrationUrl,
      query: (sql) =>
        run(
          "docker",
          [
            "exec",
            "-i",
            containerName,
            "psql",
            "-At",
            "-U",
            "postgres",
            "-d",
            "flash_trips",
          ],
          { input: sql },
        ).trim(),
      runtimeUrl,
      stop: () => {
        spawnSync("docker", ["rm", "--force", containerName], {
          cwd: root,
          stdio: "ignore",
        });
      },
    };
  } catch (error) {
    spawnSync("docker", ["rm", "--force", containerName], {
      cwd: root,
      stdio: "ignore",
    });
    throw error;
  }
}

export async function withDisposablePostgres<T>(
  work: (database: DisposablePostgres) => Promise<T>,
): Promise<T> {
  const database = await startDisposablePostgres();
  try {
    return await work(database);
  } finally {
    database.stop();
  }
}

function withoutOidcTenantEnvironment(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  delete env.FLASH_TRIPS_OIDC_TENANT_ID;
  delete env.FLASH_TRIPS_OIDC_TENANT_SUBDOMAIN;
  return env;
}

function sqlLiteral(value: string): string {
  return value.replaceAll("'", "''");
}

async function readProviderStatus(
  path: string,
  process: ManagedProcess,
): Promise<LocalProvider> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (process.child.exitCode !== null) {
      throw new Error(`local OIDC provider exited\n${process.output()}`);
    }
    try {
      const parsed: unknown = JSON.parse(await readFile(path, "utf8"));
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        !("ca_file" in parsed) ||
        typeof parsed.ca_file !== "string" ||
        !("discovery_url" in parsed) ||
        typeof parsed.discovery_url !== "string" ||
        !("issuer" in parsed) ||
        typeof parsed.issuer !== "string" ||
        !("jwks_uri" in parsed) ||
        typeof parsed.jwks_uri !== "string"
      ) {
        throw new Error("local OIDC provider returned invalid status");
      }
      return {
        ca_file: parsed.ca_file,
        discovery_url: parsed.discovery_url,
        issuer: parsed.issuer,
        jwks_uri: parsed.jwks_uri,
      };
    } catch {
      await delay(50);
    }
  }
  throw new Error(
    `local OIDC provider did not become ready\n${process.output()}`,
  );
}

export async function startJourneyHarness(): Promise<JourneyHarness> {
  const temporaryDirectory = await mkdtemp(
    join(tmpdir(), "flash-trips-journey-"),
  );
  const providerStatus = join(temporaryDirectory, "provider.json");
  const providerProcess = startProcess(
    "local OIDC provider",
    "uv",
    ["run", "python", "-m", "tests.journey.local_provider", providerStatus],
    process.env,
  );
  let apiProcess: ManagedProcess | undefined;
  let database: DisposablePostgres | undefined;
  let webProcess: ManagedProcess | undefined;
  const cleanup = async (): Promise<void> => {
    await stopProcess(webProcess);
    await stopProcess(apiProcess);
    database?.stop();
    await stopProcess(providerProcess);
    await rm(temporaryDirectory, { force: true, recursive: true });
  };

  try {
    const provider = await readProviderStatus(providerStatus, providerProcess);
    const webCertificate = join(temporaryDirectory, "web-certificate.pem");
    const webKey = join(temporaryDirectory, "web-key.pem");
    run("openssl", [
      "req",
      "-x509",
      "-newkey",
      "rsa:2048",
      "-nodes",
      "-keyout",
      webKey,
      "-out",
      webCertificate,
      "-days",
      "1",
      "-subj",
      "/CN=localhost",
      "-addext",
      "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]);
    database = await startDisposablePostgres();
    database.query(`
INSERT INTO planners (id, access_status)
VALUES ('${plannerId}', 'Active');
INSERT INTO external_identities (id, issuer, subject, planner_id)
VALUES (
  '01991e28-1d65-7000-8000-000000000005',
  '${sqlLiteral(provider.issuer)}',
  '${localSubject}',
  '${plannerId}'
);
INSERT INTO planners (id, access_status)
VALUES ('${otherPlannerId}', 'Active');
INSERT INTO trips (id, planner_id)
VALUES ('${otherPlannerTripId}', '${otherPlannerId}');
INSERT INTO trip_structures (
  id, trip_id, planner_id, position, city, starts_on, ends_on, nights
)
VALUES (
  '${otherPlannerStayId}',
  '${otherPlannerTripId}',
  '${otherPlannerId}',
  0,
  'Porto',
  '2026-11-01',
  '2026-11-04',
  3
);
`);
    const [apiPort, webPort] = await Promise.all([freePort(), freePort()]);
    const baseUrl = `https://localhost:${webPort}`;
    const commonOidc = {
      FLASH_TRIPS_OIDC_CLIENT_ID: "journey-client",
      FLASH_TRIPS_OIDC_ISSUER: provider.issuer,
      FLASH_TRIPS_TEST_OIDC_JWKS_URI: provider.jwks_uri,
    };
    apiProcess = startProcess(
      "FastAPI",
      "uv",
      ["run", "python", "-m", "flash_trips.composition"],
      {
        ...withoutOidcTenantEnvironment(),
        ...commonOidc,
        DATABASE_URL: database.runtimeUrl,
        EXTERNAL_IDENTITY_ALLOWLIST: JSON.stringify([
          { issuer: provider.issuer, subject: localSubject },
        ]),
        HOST: "127.0.0.1",
        LIVE_CALL_ALLOWANCE: "0",
        PORT: String(apiPort),
        SSL_CERT_FILE: provider.ca_file,
      },
    );
    await waitForHttp(
      "FastAPI",
      `http://127.0.0.1:${apiPort}/api/v1/status`,
      apiProcess,
    );
    webProcess = startProcess(
      "Next.js",
      "pnpm",
      [
        "--dir",
        "apps/web",
        "exec",
        "next",
        "dev",
        "--hostname",
        "127.0.0.1",
        "--port",
        String(webPort),
        "--experimental-https",
        "--experimental-https-key",
        webKey,
        "--experimental-https-cert",
        webCertificate,
      ],
      {
        ...withoutOidcTenantEnvironment(),
        ...commonOidc,
        DATABASE_URL: database.runtimeUrl,
        FLASH_TRIPS_ALLOWED_ORIGINS: baseUrl,
        FLASH_TRIPS_API_BASE_URL: `http://127.0.0.1:${apiPort}`,
        FLASH_TRIPS_OIDC_CLIENT_SECRET: "journey-client-secret",
        FLASH_TRIPS_OIDC_REDIRECT_URI: `${baseUrl}/api/auth/callback`,
        FLASH_TRIPS_SESSION_DIGEST_KEY:
          "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        FLASH_TRIPS_SESSION_TOKEN_KEY:
          "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI",
        FLASH_TRIPS_TEST_OIDC_DISCOVERY_URL: provider.discovery_url,
        NODE_EXTRA_CA_CERTS: provider.ca_file,
        // Scoped to this spawned process. The test-only runtime seam accepts
        // OIDC endpoints only from the loopback provider.
        NODE_TLS_REJECT_UNAUTHORIZED: "0",
      },
    );
    await waitForLocalHttps("Next.js", `${baseUrl}/planner`, webProcess);
    process.env.FLASH_TRIPS_JOURNEY_POSTGRES_CONTAINER = database.containerName;
    return {
      baseUrl,
      stop: async () => {
        delete process.env.FLASH_TRIPS_JOURNEY_POSTGRES_CONTAINER;
        await cleanup();
      },
    };
  } catch (error) {
    await cleanup();
    throw error;
  }
}
