import assert from "node:assert/strict";
import test from "node:test";

import { loadProvider } from "../../apps/web/lib/server/oidc-runtime.ts";

const tenantId = "7a3eb701-647d-4e3a-8b36-e3108cc5bc49";
const tenantSubdomain = "flashtripsid07";
const issuer = `https://${tenantId}.ciamlogin.com/${tenantId}/v2.0`;

// External ID answers discovery on whichever host is asked and always reports
// the tenant-identifier issuer, so the endpoint hosts mirror the request.
function externalIdentityDiscovery(
  document: Record<string, unknown> = {},
): { fetcher: typeof fetch; requested: string[] } {
  const requested: string[] = [];
  const fetcher = (async (input: string | URL | Request) => {
    const url = new URL(String(input));
    requested.push(url.toString());
    const host = url.host;
    return Response.json({
      authorization_endpoint: `https://${host}/${tenantId}/oauth2/v2.0/authorize`,
      issuer,
      jwks_uri: `https://${host}/${tenantId}/discovery/v2.0/keys`,
      token_endpoint: `https://${host}/${tenantId}/oauth2/v2.0/token`,
      ...document,
    });
  }) as typeof fetch;
  return { fetcher, requested };
}

function configure(overrides: Record<string, string> = {}): void {
  const environment: Record<string, string> = {
    FLASH_TRIPS_OIDC_CLIENT_ID: "planner-client-id",
    FLASH_TRIPS_OIDC_CLIENT_SECRET: "planner-client-secret",
    FLASH_TRIPS_OIDC_ISSUER: issuer,
    FLASH_TRIPS_OIDC_REDIRECT_URI: "https://app.example/api/auth/callback",
    FLASH_TRIPS_OIDC_TENANT_ID: tenantId,
    FLASH_TRIPS_OIDC_TENANT_SUBDOMAIN: tenantSubdomain,
    ...overrides,
  };
  for (const [name, value] of Object.entries(environment)) {
    if (value.length === 0) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
}

test("discovery is fetched from the tenant subdomain that serves the endpoints", async () => {
  configure();
  const discovery = externalIdentityDiscovery();

  const provider = await loadProvider(discovery.fetcher);

  assert.equal(discovery.requested.length, 1);
  assert.equal(
    new URL(discovery.requested[0]!).host,
    `${tenantSubdomain}.ciamlogin.com`,
  );
  for (const endpoint of [
    provider.authorizationEndpoint,
    provider.jwksUri,
    provider.tokenEndpoint,
  ]) {
    assert.equal(new URL(endpoint).host, `${tenantSubdomain}.ciamlogin.com`);
  }
  assert.equal(provider.issuer, issuer);
  assert.equal(provider.scope, "api://planner-client-id/principal:read");
});

test("an issuer that is not the exact tenant issuer is rejected", async () => {
  configure({
    FLASH_TRIPS_OIDC_ISSUER: `https://${tenantSubdomain}.ciamlogin.com/${tenantId}/v2.0`,
  });
  const discovery = externalIdentityDiscovery();

  await assert.rejects(
    loadProvider(discovery.fetcher),
    /exact tenant issuer/,
  );
  assert.deepEqual(discovery.requested, []);
});

test("endpoints outside the tenant subdomain are refused", async () => {
  configure();
  const discovery = externalIdentityDiscovery({
    token_endpoint: "https://attacker.example/oauth2/v2.0/token",
  });

  await assert.rejects(loadProvider(discovery.fetcher), /untrusted endpoint/);
});

test("a discovery issuer that disagrees with configuration is refused", async () => {
  configure();
  const discovery = externalIdentityDiscovery({
    issuer: "https://other-tenant.ciamlogin.com/other/v2.0",
  });

  await assert.rejects(loadProvider(discovery.fetcher), /issuer does not match/);
});

test("a required setting is reported by name when absent", async () => {
  configure({ FLASH_TRIPS_OIDC_CLIENT_SECRET: "" });
  const discovery = externalIdentityDiscovery();

  await assert.rejects(
    loadProvider(discovery.fetcher),
    /FLASH_TRIPS_OIDC_CLIENT_SECRET is required/,
  );
});
