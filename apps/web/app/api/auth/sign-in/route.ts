import { NextResponse } from "next/server";

import { beginOidcAuthorization } from "../../../../lib/server/oidc-flow";
import { oidcRuntime } from "../../../../lib/server/oidc-runtime";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  try {
    const runtime = await oidcRuntime();
    return beginOidcAuthorization(runtime.client, runtime.transactions);
  } catch {
    return NextResponse.redirect(
      new URL("/planner?sign_in=failed", request.url),
    );
  }
}
