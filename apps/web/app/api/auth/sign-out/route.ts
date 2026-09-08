import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { sessionManager } from "../../../../lib/server/session-runtime";
import { completeApplicationSignOut } from "../../../../lib/server/sign-out-flow";
import {
  applicationSession,
  originValidation,
  sessionBoundCsrf,
} from "../../../../lib/server/session-policy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(applicationSession.cookieName)?.value;
  return completeApplicationSignOut({
    cookieValue,
    csrfToken: request.headers.get(sessionBoundCsrf.requestHeader) ?? undefined,
    method: request.method,
    origin: request.headers.get(originValidation.requestHeader) ?? undefined,
    sessions: sessionManager(),
  });
}
