import "server-only";

import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

import { createRemoteJWKSet, jwtVerify } from "jose";

export interface OidcProvider {
  authorizationEndpoint: string;
  clientId: string;
  clientSecret: string;
  issuer: string;
  jwksUri: string;
  redirectUri: string;
  scope: string;
  tokenEndpoint: string;
}

export interface OidcTransaction {
  codeVerifier: string;
  nonce: string;
  state: string;
}

type CallbackFailure =
  "invalid_code" | "invalid_nonce" | "invalid_state" | "provider_error";

type TokenFetcher = (
  input: string | URL | Request,
  init: RequestInit,
) => Promise<Response>;

type IdTokenVerifier = (idToken: string, nonce: string) => Promise<void>;

interface OidcAuthorizationClientOptions {
  verifyIdToken?: IdTokenVerifier;
}

interface CallbackParameters {
  code?: string;
  error?: string;
  state?: string;
}

interface CompletedAuthorization {
  accessToken: string;
}

export class OidcCallbackError extends Error {
  readonly reason: CallbackFailure;

  constructor(reason: CallbackFailure) {
    super("Sign-in could not be completed.");
    this.name = "OidcCallbackError";
    this.reason = reason;
  }
}

function opaqueValue(): string {
  return randomBytes(32).toString("base64url");
}

function valuesMatch(actual: string | undefined, expected: string): boolean {
  if (actual === undefined) {
    return false;
  }
  const actualBytes = Buffer.from(actual);
  const expectedBytes = Buffer.from(expected);
  return (
    actualBytes.byteLength === expectedBytes.byteLength &&
    timingSafeEqual(actualBytes, expectedBytes)
  );
}

export class OidcAuthorizationClient {
  private readonly provider: OidcProvider;
  private readonly verifyIdToken: IdTokenVerifier;

  constructor(
    provider: OidcProvider,
    options: OidcAuthorizationClientOptions = {},
  ) {
    this.provider = provider;
    const keys = createRemoteJWKSet(new URL(provider.jwksUri));
    this.verifyIdToken =
      options.verifyIdToken ??
      (async (idToken, nonce) => {
        const verified = await jwtVerify(idToken, keys, {
          algorithms: ["RS256"],
          audience: provider.clientId,
          issuer: provider.issuer,
          requiredClaims: ["exp", "iat", "nonce", "sub"],
        });
        if (
          typeof verified.payload.nonce !== "string" ||
          !valuesMatch(verified.payload.nonce, nonce)
        ) {
          throw new Error("Invalid nonce");
        }
      });
  }

  callbackMatches(url: URL): boolean {
    return `${url.origin}${url.pathname}` === this.provider.redirectUri;
  }

  plannerUrl(signInFailed = false): URL {
    const destination = new URL("/planner", this.provider.redirectUri);
    if (signInFailed) {
      destination.searchParams.set("sign_in", "failed");
    }
    return destination;
  }

  begin(): {
    authorizationUrl: string;
    transaction: OidcTransaction;
  } {
    const transaction = {
      codeVerifier: opaqueValue(),
      nonce: opaqueValue(),
      state: opaqueValue(),
    };
    const authorization = new URL(this.provider.authorizationEndpoint);
    authorization.searchParams.set("client_id", this.provider.clientId);
    authorization.searchParams.set(
      "code_challenge",
      createHash("sha256").update(transaction.codeVerifier).digest("base64url"),
    );
    authorization.searchParams.set("code_challenge_method", "S256");
    authorization.searchParams.set("domain_hint", "google.com");
    authorization.searchParams.set("nonce", transaction.nonce);
    authorization.searchParams.set("redirect_uri", this.provider.redirectUri);
    authorization.searchParams.set("response_mode", "query");
    authorization.searchParams.set("response_type", "code");
    authorization.searchParams.set(
      "scope",
      `openid profile ${this.provider.scope}`,
    );
    authorization.searchParams.set("state", transaction.state);
    return {
      authorizationUrl: authorization.toString(),
      transaction,
    };
  }

  async complete(
    callback: CallbackParameters,
    transaction: OidcTransaction,
    fetcher: TokenFetcher = fetch,
  ): Promise<CompletedAuthorization> {
    if (!valuesMatch(callback.state, transaction.state)) {
      throw new OidcCallbackError("invalid_state");
    }
    if (
      callback.error !== undefined ||
      callback.code === undefined ||
      callback.code.length === 0
    ) {
      throw new OidcCallbackError(
        callback.error === undefined ? "invalid_code" : "provider_error",
      );
    }

    let response: Response;
    try {
      response = await fetcher(this.provider.tokenEndpoint, {
        body: new URLSearchParams({
          client_id: this.provider.clientId,
          client_secret: this.provider.clientSecret,
          code: callback.code,
          code_verifier: transaction.codeVerifier,
          grant_type: "authorization_code",
          redirect_uri: this.provider.redirectUri,
        }),
        cache: "no-store",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        method: "POST",
      });
    } catch {
      throw new OidcCallbackError("invalid_code");
    }
    if (!response.ok) {
      throw new OidcCallbackError("invalid_code");
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new OidcCallbackError("invalid_code");
    }
    if (
      typeof body !== "object" ||
      body === null ||
      !("access_token" in body) ||
      typeof body.access_token !== "string" ||
      body.access_token.length === 0 ||
      !("id_token" in body) ||
      typeof body.id_token !== "string" ||
      !("token_type" in body) ||
      typeof body.token_type !== "string" ||
      body.token_type.toLowerCase() !== "bearer"
    ) {
      throw new OidcCallbackError("invalid_code");
    }

    try {
      await this.verifyIdToken(body.id_token, transaction.nonce);
    } catch {
      throw new OidcCallbackError("invalid_nonce");
    }
    return { accessToken: body.access_token };
  }
}
