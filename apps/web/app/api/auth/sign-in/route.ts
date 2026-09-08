import { beginOidcAuthorization } from "../../../../lib/server/oidc-flow";
import { oidcRuntime } from "../../../../lib/server/oidc-runtime";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const runtime = await oidcRuntime();
  return beginOidcAuthorization(runtime.client, runtime.transactions);
}
