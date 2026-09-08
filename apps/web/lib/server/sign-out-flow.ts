import "server-only";

import { NextResponse } from "next/server";

import { authenticationRequiredProblem } from "./problems";
import { applicationSession } from "./session-policy";
import type { ApplicationSessionManager } from "./session";

interface CompleteApplicationSignOutInput {
  cookieValue: string | undefined;
  csrfToken: string | undefined;
  method: string;
  origin: string | undefined;
  sessions: Pick<ApplicationSessionManager, "authorize" | "revoke">;
}

export async function completeApplicationSignOut(
  input: CompleteApplicationSignOutInput,
): Promise<NextResponse> {
  const authorized = await input.sessions.authorize({
    cookieValue: input.cookieValue,
    csrfToken: input.csrfToken,
    method: input.method,
    origin: input.origin,
  });
  if (authorized === null || input.cookieValue === undefined) {
    return authenticationRequiredProblem();
  }

  await input.sessions.revoke(input.cookieValue);
  const response = new NextResponse(null, { status: 204 });
  response.cookies.set(applicationSession.cookieName, "", {
    ...applicationSession.cookieOptions,
    maxAge: 0,
  });
  return response;
}
