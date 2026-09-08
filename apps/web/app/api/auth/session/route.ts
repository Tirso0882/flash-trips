import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { authenticationRequiredProblem } from "../../../../lib/server/problems";
import { sessionManager } from "../../../../lib/server/session-runtime";
import { applicationSession } from "../../../../lib/server/session-policy";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const session = await sessionManager().authorize({
    cookieValue: cookieStore.get(applicationSession.cookieName)?.value,
    method: "GET",
  });
  if (session === null) {
    return authenticationRequiredProblem();
  }
  return NextResponse.json({ csrf_token: session.csrfToken });
}
