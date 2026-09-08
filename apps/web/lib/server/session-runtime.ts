import "server-only";

import postgres, { type Sql } from "postgres";

import { PostgresSessionRepository } from "./postgres-session-repository";
import { ApplicationSessionManager } from "./session";
import { originValidation } from "./session-policy";

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function keyFromEnvironment(name: string): Buffer {
  const key = Buffer.from(requiredEnvironment(name), "base64url");
  if (key.byteLength !== 32) {
    throw new Error(`${name} must be a base64url-encoded 32-byte key`);
  }
  return key;
}

function allowedOriginsFromEnvironment(): ReadonlySet<string> {
  const configured = requiredEnvironment(
    originValidation.allowedOriginsEnvironment,
  );
  const origins = configured.split(",").map((entry) => entry.trim());
  if (origins.some((entry) => entry.length === 0)) {
    throw new Error(
      `${originValidation.allowedOriginsEnvironment} must contain only origins`,
    );
  }
  return new Set(
    origins.map((entry) => {
      const url = new URL(entry);
      if (
        url.origin !== entry ||
        (url.protocol !== "https:" && url.hostname !== "localhost")
      ) {
        throw new Error(
          `${originValidation.allowedOriginsEnvironment} must contain HTTPS origins`,
        );
      }
      return url.origin;
    }),
  );
}

function sessionDatabase(): Sql {
  const value = requiredEnvironment("DATABASE_URL").replace(
    "postgresql+asyncpg://",
    "postgresql://",
  );
  if (!value.startsWith("postgresql://") && !value.startsWith("postgres://")) {
    throw new Error("DATABASE_URL must use PostgreSQL");
  }
  return postgres(value, {
    max: 5,
    prepare: true,
  });
}

let resolved: ApplicationSessionManager | undefined;

export function sessionManager(): ApplicationSessionManager {
  resolved ??= new ApplicationSessionManager({
    allowedOrigins: allowedOriginsFromEnvironment(),
    digestKey: keyFromEnvironment("FLASH_TRIPS_SESSION_DIGEST_KEY"),
    repository: new PostgresSessionRepository(sessionDatabase()),
    tokenEncryptionKey: keyFromEnvironment("FLASH_TRIPS_SESSION_TOKEN_KEY"),
  });
  return resolved;
}
