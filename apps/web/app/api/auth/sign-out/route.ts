import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { authenticationRequiredProblem } from "../../../../lib/server/problems";
import { sessionManager } from "../../../../lib/server/session-runtime";
import {
  applicationSession,
  originValidation,
  sessionBoundCsrf,
} from "../../../../lib/server/session-policy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(applicationSession.cookieName)?.value;
  const sessions = sessionManager();
  const authorized = await sessions.authorize({
    cookieValue,
    csrfToken: request.headers.get(sessionBoundCsrf.requestHeader) ?? undefined,
    method: request.method,
    origin: request.headers.get(originValidation.requestHeader) ?? undefined,
  });
  if (authorized === null || cookieValue === undefined) {
    return authenticationRequiredProblem();
  }

  await sessions.revoke(cookieValue);
  const response = new NextResponse(null, { status: 204 });
  response.cookies.set(applicationSession.cookieName, "", {
    ...applicationSession.cookieOptions,
    maxAge: 0,
  });
  return response;
}
