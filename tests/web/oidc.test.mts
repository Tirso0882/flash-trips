import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import test from "node:test";

import {
  OidcAuthorizationClient,
  OidcCallbackError,
  type OidcProvider,
} from "../../apps/web/lib/server/oidc.ts";
import {
  beginOidcAuthorization,
  completeOidcAuthorization,
} from "../../apps/web/lib/server/oidc-flow.ts";
import { OidcTransactionStore } from "../../apps/web/lib/server/oidc-transaction.ts";
import { applicationSession } from "../../apps/web/lib/server/session-policy.ts";

const provider: OidcProvider = {
  authorizationEndpoint: "https://tenant.example/authorize",
  clientId: "client-id",
  clientSecret: "client-secret",
  issuer: "https://tenant.example",
  jwksUri: "https://tenant.example/discovery/v2.0/keys",
  redirectUri: "https://app.example/api/auth/callback",
  scope: "api://flash-trips/access",
  tokenEndpoint: "https://tenant.example/token",
};

test("authorization uses code challenge, exact redirect, state, nonce, and Google", () => {
  const client = new OidcAuthorizationClient(provider);
  const started = client.begin();
  const authorization = new URL(started.authorizationUrl);
  const verifier = started.transaction.codeVerifier;

  assert.equal(authorization.origin + authorization.pathname, provider.authorizationEndpoint);
  assert.equal(authorization.searchParams.get("client_id"), provider.clientId);
  assert.equal(authorization.searchParams.get("redirect_uri"), provider.redirectUri);
  assert.equal(authorization.searchParams.get("response_type"), "code");
  assert.equal(authorization.searchParams.get("response_mode"), "query");
  assert.equal(
    authorization.searchParams.get("scope"),
    `openid profile ${provider.scope}`,
  );
  assert.equal(authorization.searchParams.get("code_challenge_method"), "S256");
  assert.equal(
    authorization.searchParams.get("code_challenge"),
    createHash("sha256").update(verifier).digest("base64url"),
  );
  assert.equal(authorization.searchParams.get("state"), started.transaction.state);
  assert.equal(authorization.searchParams.get("nonce"), started.transaction.nonce);
  assert.equal(authorization.searchParams.get("domain_hint"), "google.com");
});

test("callback failures exchange no token and establish no application session", async () => {
  const client = new OidcAuthorizationClient(provider);
  const transaction = client.begin().transaction;
  let exchanges = 0;
  const exchange = async (): Promise<never> => {
    exchanges += 1;
    throw new Error("must not exchange");
  };

  await assert.rejects(
    client.complete({ code: "authorization-code", state: "wrong" }, transaction, exchange),
    (error: unknown) =>
      error instanceof OidcCallbackError && error.reason === "invalid_state",
  );
  await assert.rejects(
    client.complete({ state: transaction.state }, transaction, exchange),
    (error: unknown) =>
      error instanceof OidcCallbackError && error.reason === "invalid_code",
  );
  assert.equal(exchanges, 0);
});

test("callback sends PKCE once and rejects an invalid ID-token nonce", async () => {
  const client = new OidcAuthorizationClient(provider);
  const transaction = client.begin().transaction;
  let body = "";
  const exchange = async (_url: string, init: RequestInit): Promise<Response> => {
    body = String(init.body);
    return Response.json({
      access_token: randomBytes(32).toString("base64url"),
      id_token: "not-a-verifiable-id-token",
      token_type: "Bearer",
    });
  };

  await assert.rejects(
    client.complete(
      { code: "authorization-code", state: transaction.state },
      transaction,
      exchange,
    ),
    (error: unknown) =>
      error instanceof OidcCallbackError && error.reason === "invalid_nonce",
  );
  const request = new URLSearchParams(body);
  assert.equal(request.get("code"), "authorization-code");
  assert.equal(request.get("code_verifier"), transaction.codeVerifier);
  assert.equal(request.get("redirect_uri"), provider.redirectUri);
  assert.equal(request.get("client_secret"), provider.clientSecret);
});

test("a verified callback returns only the server-side access token", async () => {
  const observed: string[] = [];
  const client = new OidcAuthorizationClient(provider, {
    verifyIdToken: async (idToken, nonce) => {
      observed.push(idToken, nonce);
    },
  });
  const transaction = client.begin().transaction;
  const result = await client.complete(
    { code: "authorization-code", state: transaction.state },
    transaction,
    async () =>
      Response.json({
        access_token: "exact-audience-access-token",
        id_token: "signed-id-token",
        token_type: "Bearer",
      }),
  );

  assert.deepEqual(result, { accessToken: "exact-audience-access-token" });
  assert.deepEqual(observed, ["signed-id-token", transaction.nonce]);
});

test("the short-lived transaction cookie hides PKCE data and rejects tampering", () => {
  let now = new Date("2026-09-08T10:00:00Z");
  const store = new OidcTransactionStore(Buffer.alloc(32, 7), () => now);
  const transaction = new OidcAuthorizationClient(provider).begin().transaction;
  const cookie = store.seal(transaction);

  assert.equal(cookie.includes(transaction.codeVerifier), false);
  assert.deepEqual(store.open(cookie), transaction);
  const tamperedCookie = `${cookie[0] === "A" ? "B" : "A"}${cookie.slice(1)}`;
  assert.equal(store.open(tamperedCookie), null);
  now = new Date("2026-09-08T10:10:00.001Z");
  assert.equal(store.open(cookie), null);
});

test("the authorization route redirects and sets only a protected transaction cookie", () => {
  const client = new OidcAuthorizationClient(provider);
  const store = new OidcTransactionStore(Buffer.alloc(32, 7));
  const response = beginOidcAuthorization(client, store);

  assert.equal(response.status, 307);
  assert.equal(new URL(response.headers.get("location")!).origin, "https://tenant.example");
  const cookie = response.headers.get("set-cookie");
  assert.match(cookie!, /^__Host-flash_trips_oidc=/);
  assert.match(cookie!, /HttpOnly/);
  assert.match(cookie!, /Secure/);
  assert.match(cookie!, /SameSite=lax/i);
  assert.doesNotMatch(cookie!, /client-secret/);
});

test("the callback route issues an opaque session and consumes its transaction", async () => {
  const store = new OidcTransactionStore(Buffer.alloc(32, 7));
  const client = new OidcAuthorizationClient(provider, {
    verifyIdToken: async () => undefined,
  });
  const transaction = client.begin().transaction;
  let establishedWith = "";
  const response = await completeOidcAuthorization({
    client,
    establishSession: async (accessToken) => {
      establishedWith = accessToken;
      return { cookieValue: Buffer.alloc(32, 5).toString("base64url") };
    },
    fetcher: async () =>
      Response.json({
        access_token: "provider-access-token",
        id_token: "signed-id-token",
        token_type: "Bearer",
      }),
    requestUrl: `https://app.example/api/auth/callback?code=one-time-code&state=${transaction.state}`,
    store,
    transactionCookie: store.seal(transaction),
  });

  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "https://app.example/planner");
  assert.equal(establishedWith, "provider-access-token");
  const cookies = response.headers.getSetCookie();
  assert.equal(cookies.some((cookie) => cookie.startsWith(`${applicationSession.cookieName}=`)), true);
  assert.equal(
    cookies.some(
      (cookie) =>
        cookie.startsWith("__Host-flash_trips_oidc=") && cookie.includes("Max-Age=0"),
    ),
    true,
  );
  assert.equal(cookies.join(";").includes("provider-access-token"), false);
});

test("callback errors are non-enumerating and establish no session", async () => {
  const store = new OidcTransactionStore(Buffer.alloc(32, 7));
  const client = new OidcAuthorizationClient(provider);
  let established = false;
  const response = await completeOidcAuthorization({
    client,
    establishSession: async () => {
      established = true;
      return { cookieValue: "must-not-be-issued" };
    },
    requestUrl:
      "https://attacker.example/api/auth/callback?code=secret-code&state=wrong-state",
    store,
    transactionCookie: store.seal(client.begin().transaction),
  });

  assert.equal(response.status, 307);
  assert.equal(
    response.headers.get("location"),
    "https://app.example/planner?sign_in=failed",
  );
  assert.equal(established, false);
  assert.equal(response.headers.get("location")!.includes("state"), false);
  assert.equal(response.headers.get("location")!.includes("code"), false);
});
