import "server-only";

import { NextResponse } from "next/server";

import { apiBaseUrl } from "./config";
import { sessionManager } from "./session-runtime";
import { applicationSession } from "./session-policy";

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function applicationSessionResponse(
  cookieValue: string,
  csrfToken: string,
): NextResponse {
  const response = NextResponse.json({ csrf_token: csrfToken });
  response.cookies.set(
    applicationSession.cookieName,
    cookieValue,
    applicationSession.cookieOptions,
  );
  return response;
}

export async function resolvePlannerId(
  accessToken: string,
  fetcher: typeof fetch = fetch,
): Promise<string> {
  const response = await fetcher(
    `${apiBaseUrl()}/api/v1/authenticated-principal`,
    {
      cache: "no-store",
      headers: { authorization: `Bearer ${accessToken}` },
    },
  );
  if (!response.ok) {
    throw new Error("Authentication failed");
  }
  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("planner_id" in body) ||
    typeof body.planner_id !== "string" ||
    !uuidPattern.test(body.planner_id)
  ) {
    throw new Error("Authentication failed");
  }
  return body.planner_id;
}

export async function issueApplicationSession(
  accessToken: string,
  previousIdentifier?: string,
): Promise<NextResponse> {
  const plannerId = await resolvePlannerId(accessToken);
  const issued = await sessionManager().authenticate({
    accessToken,
    plannerId,
    previousIdentifier,
  });
  return applicationSessionResponse(issued.cookieValue, issued.csrfToken);
}
