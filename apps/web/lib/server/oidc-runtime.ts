import "server-only";

import { OidcAuthorizationClient, type OidcProvider } from "./oidc";
import { OidcTransactionStore } from "./oidc-transaction";

interface DiscoveryDocument {
  authorization_endpoint: string;
  issuer: string;
  jwks_uri: string;
  token_endpoint: string;
}

interface OidcRuntime {
  client: OidcAuthorizationClient;
  transactions: OidcTransactionStore;
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function localHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

function providerEnvironment(): {
  discoveryUrl: URL;
  provider: Pick<
    OidcProvider,
    "clientId" | "clientSecret" | "issuer" | "redirectUri" | "scope"
  >;
  providerHostname: string;
} {
  const tenantId = requiredEnvironment("FLASH_TRIPS_OIDC_TENANT_ID");
  const tenantSubdomain = requiredEnvironment(
    "FLASH_TRIPS_OIDC_TENANT_SUBDOMAIN",
  );
  if (!/^[0-9a-f-]{36}$/i.test(tenantId)) {
    throw new Error("FLASH_TRIPS_OIDC_TENANT_ID must be a tenant UUID");
  }
  if (!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/i.test(tenantSubdomain)) {
    throw new Error("FLASH_TRIPS_OIDC_TENANT_SUBDOMAIN is invalid");
  }

  const providerHostname = `${tenantSubdomain}.ciamlogin.com`;
  const issuer = requiredEnvironment("FLASH_TRIPS_OIDC_ISSUER");
  const expectedIssuer = `https://${providerHostname}/${tenantId}/v2.0`;
  if (issuer !== expectedIssuer) {
    throw new Error("FLASH_TRIPS_OIDC_ISSUER is not the exact tenant issuer");
  }

  const redirect = new URL(
    requiredEnvironment("FLASH_TRIPS_OIDC_REDIRECT_URI"),
  );
  const localRedirect = localHostname(redirect.hostname);
  if (
    redirect.hash !== "" ||
    redirect.search !== "" ||
    (redirect.protocol !== "https:" &&
      !(redirect.protocol === "http:" && localRedirect))
  ) {
    throw new Error("FLASH_TRIPS_OIDC_REDIRECT_URI is not an exact safe URI");
  }
  if (process.env.NODE_ENV === "production" && localRedirect) {
    throw new Error("Production cannot use the development OIDC registration");
  }

  const clientId = requiredEnvironment("FLASH_TRIPS_OIDC_CLIENT_ID");
  return {
    discoveryUrl: new URL(`${issuer}/.well-known/openid-configuration`),
    provider: {
      clientId,
      clientSecret: requiredEnvironment("FLASH_TRIPS_OIDC_CLIENT_SECRET"),
      issuer,
      redirectUri: redirect.toString(),
      scope: `api://${clientId}/principal:read`,
    },
    providerHostname,
  };
}

function endpoint(
  document: Record<string, unknown>,
  name: keyof DiscoveryDocument,
  providerHostname: string,
): string {
  const value = document[name];
  if (typeof value !== "string") {
    throw new Error("OIDC discovery is invalid");
  }
  const url = new URL(value);
  if (url.protocol !== "https:" || url.hostname !== providerHostname) {
    throw new Error("OIDC discovery returned an untrusted endpoint");
  }
  return url.toString();
}

async function loadProvider(
  fetcher: typeof fetch = fetch,
): Promise<OidcProvider> {
  const configured = providerEnvironment();
  const response = await fetcher(configured.discoveryUrl, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("OIDC discovery failed");
  }
  const body: unknown = await response.json();
  if (typeof body !== "object" || body === null) {
    throw new Error("OIDC discovery is invalid");
  }
  const document = body as Record<string, unknown>;
  if (document.issuer !== configured.provider.issuer) {
    throw new Error("OIDC discovery issuer does not match configuration");
  }
  return {
    ...configured.provider,
    authorizationEndpoint: endpoint(
      document,
      "authorization_endpoint",
      configured.providerHostname,
    ),
    jwksUri: endpoint(document, "jwks_uri", configured.providerHostname),
    tokenEndpoint: endpoint(
      document,
      "token_endpoint",
      configured.providerHostname,
    ),
  };
}

let resolved: Promise<OidcRuntime> | undefined;

export function oidcRuntime(): Promise<OidcRuntime> {
  resolved ??= loadProvider().then((provider) => ({
    client: new OidcAuthorizationClient(provider),
    transactions: new OidcTransactionStore(
      Buffer.from(
        requiredEnvironment("FLASH_TRIPS_SESSION_TOKEN_KEY"),
        "base64url",
      ),
    ),
  }));
  return resolved;
}
