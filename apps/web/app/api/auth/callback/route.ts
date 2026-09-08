import { cookies } from "next/headers";
import { type NextRequest } from "next/server";

import { resolvePlannerId } from "../../../../lib/server/authenticated-session";
import { completeOidcAuthorization } from "../../../../lib/server/oidc-flow";
import { oidcRuntime } from "../../../../lib/server/oidc-runtime";
import { oidcTransactionCookie } from "../../../../lib/server/oidc-transaction";
import { sessionManager } from "../../../../lib/server/session-runtime";
import { applicationSession } from "../../../../lib/server/session-policy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<Response> {
  const cookieStore = await cookies();
  const runtime = await oidcRuntime();
  return completeOidcAuthorization({
    client: runtime.client,
    establishSession: async (accessToken, previousIdentifier) => {
      const plannerId = await resolvePlannerId(accessToken);
      return sessionManager().authenticate({
        accessToken,
        plannerId,
        previousIdentifier,
      });
    },
    previousIdentifier: cookieStore.get(applicationSession.cookieName)?.value,
    requestUrl: request.url,
    store: runtime.transactions,
    transactionCookie: cookieStore.get(oidcTransactionCookie.name)?.value,
  });
}
