import assert from "node:assert/strict";
import test from "node:test";

import {
  applicationSessionResponse,
  resolvePlannerId,
} from "../../apps/web/lib/server/authenticated-session.ts";
import { authenticationRequiredProblem } from "../../apps/web/lib/server/problems.ts";
import { completeApplicationSignOut } from "../../apps/web/lib/server/sign-out-flow.ts";
import { applicationSession } from "../../apps/web/lib/server/session-policy.ts";
import {
  ApplicationSessionManager,
  type NewStoredSession,
  type SessionRepository,
  type StoredSession,
} from "../../apps/web/lib/server/session.ts";

class MemorySessions implements SessionRepository {
  readonly sessions: StoredSession[] = [];
  touches = 0;

  async create(session: NewStoredSession): Promise<void> {
    this.sessions.push({ ...session, revokedAt: null });
  }

  async find(identifierDigest: Uint8Array): Promise<StoredSession | null> {
    return (
      this.sessions.find((session) =>
        Buffer.from(session.identifierDigest).equals(
          Buffer.from(identifierDigest),
        ),
      ) ?? null
    );
  }

  async revoke(id: string, revokedAt: Date): Promise<void> {
    const session = this.sessions.find((candidate) => candidate.id === id);
    if (session !== undefined) {
      session.revokedAt = revokedAt;
    }
  }

  async touch(
    id: string,
    lastSeenAt: Date,
    idleExpiresAt: Date,
  ): Promise<void> {
    const session = this.sessions.find((candidate) => candidate.id === id);
    assert.notEqual(session, undefined);
    session.lastSeenAt = lastSeenAt;
    session.idleExpiresAt = idleExpiresAt;
    this.touches += 1;
  }
}

const digestKey = Buffer.alloc(32, 1);
const tokenKey = Buffer.alloc(32, 2);

function manager(
  repository: MemorySessions,
  now: Date,
): ApplicationSessionManager {
  return new ApplicationSessionManager({
    allowedOrigins: new Set(["https://app.example"]),
    clock: () => now,
    digestKey,
    repository,
    tokenEncryptionKey: tokenKey,
  });
}

test("application sessions use the required lifetime limits", () => {
  assert.equal(applicationSession.idleLifetimeSeconds, 12 * 60 * 60);
  assert.equal(applicationSession.absoluteLifetimeSeconds, 7 * 24 * 60 * 60);
  assert.equal(applicationSession.cookieOptions.maxAge, undefined);
});

test("the BFF emits only the opaque application cookie and CSRF token", async () => {
  const cookieValue = Buffer.alloc(32, 3).toString("base64url");
  const csrfToken = Buffer.alloc(32, 4).toString("base64url");
  const response = applicationSessionResponse(cookieValue, csrfToken);
  const setCookie = response.headers.get("set-cookie");

  assert.notEqual(setCookie, null);
  assert.match(
    setCookie!,
    new RegExp(`^${applicationSession.cookieName}=${cookieValue};`),
  );
  assert.match(setCookie!, /HttpOnly/);
  assert.match(setCookie!, /Secure/);
  assert.match(setCookie!, /SameSite=strict/i);
  assert.doesNotMatch(setCookie!, /Max-Age|Expires/);
  assert.deepEqual(await response.json(), { csrf_token: csrfToken });
});

test("an unusable session answers with a non-disclosing problem document", async () => {
  const response = authenticationRequiredProblem();

  assert.equal(response.status, 401);
  assert.equal(
    response.headers.get("content-type"),
    "application/problem+json",
  );
  const body = (await response.json()) as Record<string, unknown>;
  assert.equal(body.code, "authentication_required");
  assert.equal(body.detail, "Authentication is required.");
  assert.equal(body.retryable, false);
  assert.equal(body.request_id, response.headers.get("x-request-id"));
});

test("the BFF forwards only the exact-audience access token to FastAPI", async () => {
  const accessToken = "exact-audience-token";
  let observedHeaders = new Headers();
  const fetcher = async (
    _input: URL | RequestInfo,
    init?: RequestInit,
  ): Promise<Response> => {
    observedHeaders = new Headers(init?.headers);
    return Response.json({
      planner_id: "01991e28-1d65-7000-8000-000000000001",
    });
  };

  const plannerId = await resolvePlannerId(accessToken, fetcher);

  assert.equal(plannerId, "01991e28-1d65-7000-8000-000000000001");
  assert.deepEqual([...observedHeaders], [
    ["authorization", `Bearer ${accessToken}`],
  ]);
});

test("authentication rotates an opaque identifier and retains tokens only server-side", async () => {
  const repository = new MemorySessions();
  const sessions = manager(repository, new Date("2026-09-08T10:00:00Z"));
  const providerToken = "provider-token-secret";

  const first = await sessions.authenticate({
    accessToken: providerToken,
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });
  const second = await sessions.authenticate({
    accessToken: providerToken,
    plannerId: "01991e28-1d65-7000-8000-000000000001",
    previousIdentifier: first.cookieValue,
  });

  assert.notEqual(first.cookieValue, second.cookieValue);
  assert.match(second.cookieValue, /^[A-Za-z0-9_-]{43}$/);
  assert.equal(JSON.stringify(second).includes(providerToken), false);
  assert.equal(JSON.stringify(repository.sessions).includes(providerToken), false);
  assert.equal(repository.sessions[0]?.revokedAt?.toISOString(), "2026-09-08T10:00:00.000Z");
  assert.equal(
    repository.sessions.some((session) =>
      Buffer.from(session.identifierDigest).includes(
        Buffer.from(second.cookieValue),
      ),
    ),
    false,
  );
});

test("revocation and both expiry limits fail closed immediately", async () => {
  const repository = new MemorySessions();
  let now = new Date("2026-09-08T10:00:00Z");
  const sessions = new ApplicationSessionManager({
    allowedOrigins: new Set(["https://app.example"]),
    clock: () => now,
    digestKey,
    repository,
    tokenEncryptionKey: tokenKey,
  });
  const issued = await sessions.authenticate({
    accessToken: "exact-audience-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });

  assert.notEqual(
    await sessions.authorize({ cookieValue: issued.cookieValue, method: "GET" }),
    null,
  );
  await sessions.revoke(issued.cookieValue);
  assert.equal(
    await sessions.authorize({ cookieValue: issued.cookieValue, method: "GET" }),
    null,
  );

  const idle = await sessions.authenticate({
    accessToken: "exact-audience-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });
  now = new Date("2026-09-08T22:00:00.001Z");
  assert.equal(
    await sessions.authorize({ cookieValue: idle.cookieValue, method: "GET" }),
    null,
  );

  now = new Date("2026-09-08T10:00:00Z");
  const absolute = await sessions.authenticate({
    accessToken: "exact-audience-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });
  const stored = repository.sessions.at(-1);
  assert.notEqual(stored, undefined);
  stored!.idleExpiresAt = new Date("2026-09-16T10:00:00Z");
  now = new Date("2026-09-15T10:00:00.001Z");
  assert.equal(
    await sessions.authorize({
      cookieValue: absolute.cookieValue,
      method: "GET",
    }),
    null,
  );
});

test("the BFF sign-out clears its cookie and prevents replay", async () => {
  const repository = new MemorySessions();
  const sessions = manager(repository, new Date("2026-09-08T10:00:00Z"));
  const issued = await sessions.authenticate({
    accessToken: "exact-audience-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });

  const response = await completeApplicationSignOut({
    cookieValue: issued.cookieValue,
    csrfToken: issued.csrfToken,
    method: "POST",
    origin: "https://app.example",
    sessions,
  });

  assert.equal(response.status, 204);
  assert.match(
    response.headers.get("set-cookie")!,
    new RegExp(`^${applicationSession.cookieName}=;.*Max-Age=0`),
  );
  assert.equal(
    await sessions.authorize({
      cookieValue: issued.cookieValue,
      method: "GET",
    }),
    null,
  );
});

test("unsafe requests require allowed origin and session-bound CSRF", async () => {
  const repository = new MemorySessions();
  const sessions = manager(repository, new Date("2026-09-08T10:00:00Z"));
  const first = await sessions.authenticate({
    accessToken: "exact-audience-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });
  const second = await sessions.authenticate({
    accessToken: "another-token",
    plannerId: "01991e28-1d65-7000-8000-000000000001",
  });

  assert.equal(
    await sessions.authorize({
      cookieValue: first.cookieValue,
      csrfToken: first.csrfToken,
      method: "POST",
      origin: "https://evil.example",
    }),
    null,
  );
  assert.equal(
    await sessions.authorize({
      cookieValue: first.cookieValue,
      csrfToken: second.csrfToken,
      method: "POST",
      origin: "https://app.example",
    }),
    null,
  );
  assert.notEqual(
    await sessions.authorize({
      cookieValue: first.cookieValue,
      csrfToken: first.csrfToken,
      method: "POST",
      origin: "https://app.example",
    }),
    null,
  );
  assert.equal(repository.touches, 1);

  await sessions.authorize({ cookieValue: first.cookieValue, method: "GET" });
  assert.equal(repository.touches, 1);
});
