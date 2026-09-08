import "server-only";

import { NextResponse } from "next/server";

import type { OidcAuthorizationClient } from "./oidc";
import {
  oidcTransactionCookie,
  type OidcTransactionStore,
} from "./oidc-transaction";
import { applicationSession } from "./session-policy";

interface EstablishedSession {
  cookieValue: string;
}

interface CompleteAuthorizationInput {
  client: OidcAuthorizationClient;
  establishSession: (
    accessToken: string,
    previousIdentifier?: string,
  ) => Promise<EstablishedSession>;
  fetcher?: typeof fetch;
  previousIdentifier?: string;
  requestUrl: string;
  store: OidcTransactionStore;
  transactionCookie: string | undefined;
}

export function beginOidcAuthorization(
  client: OidcAuthorizationClient,
  store: OidcTransactionStore,
): NextResponse {
  const started = client.begin();
  const response = NextResponse.redirect(started.authorizationUrl);
  response.cookies.set(
    oidcTransactionCookie.name,
    store.seal(started.transaction),
    oidcTransactionCookie.options,
  );
  return response;
}

export async function completeOidcAuthorization(
  input: CompleteAuthorizationInput,
): Promise<NextResponse> {
  const callbackUrl = new URL(input.requestUrl);
  const transaction = input.store.open(input.transactionCookie);
  let response: NextResponse;

  if (transaction === null || !input.client.callbackMatches(callbackUrl)) {
    response = failedResponse(input.client);
  } else {
    try {
      const completed = await input.client.complete(
        {
          code: callbackUrl.searchParams.get("code") ?? undefined,
          error: callbackUrl.searchParams.get("error") ?? undefined,
          state: callbackUrl.searchParams.get("state") ?? undefined,
        },
        transaction,
        input.fetcher,
      );
      const session = await input.establishSession(
        completed.accessToken,
        input.previousIdentifier,
      );
      response = NextResponse.redirect(input.client.plannerUrl());
      response.cookies.set(
        applicationSession.cookieName,
        session.cookieValue,
        applicationSession.cookieOptions,
      );
    } catch {
      response = failedResponse(input.client);
    }
  }

  response.cookies.set(oidcTransactionCookie.name, "", {
    ...oidcTransactionCookie.options,
    maxAge: 0,
  });
  return response;
}

function failedResponse(client: OidcAuthorizationClient): NextResponse {
  return NextResponse.redirect(client.plannerUrl(true));
}
