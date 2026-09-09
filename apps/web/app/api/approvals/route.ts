import {
  approvePlanRevision,
  type BoundApprovalActionRequest,
} from "@flash-trips/api-client";
import { createClient } from "@flash-trips/api-client/client";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "../../../lib/server/config";
import {
  authenticationRequiredProblem,
  backendUnavailableProblem,
} from "../../../lib/server/problems";
import { sessionManager } from "../../../lib/server/session-runtime";
import {
  applicationSession,
  sessionBoundCsrf,
} from "../../../lib/server/session-policy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const session = await sessionManager().authorize({
    cookieValue: cookieStore.get(applicationSession.cookieName)?.value,
    csrfToken: request.headers.get(sessionBoundCsrf.requestHeader) ?? undefined,
    method: "POST",
    origin: request.headers.get("origin") ?? undefined,
  });
  if (session === null) return authenticationRequiredProblem();

  try {
    const body = (await request.json()) as BoundApprovalActionRequest;
    const result = await approvePlanRevision({
      body,
      client: createClient({ baseUrl: apiBaseUrl() }),
      headers: { authorization: `Bearer ${session.accessToken}` },
    });
    if (result.response === undefined) return backendUnavailableProblem();
    return NextResponse.json(result.data ?? result.error, {
      headers: {
        "content-type":
          result.response.headers.get("content-type") ?? "application/json",
        "x-request-id": result.response.headers.get("x-request-id") ?? "",
      },
      status: result.response.status,
    });
  } catch {
    return backendUnavailableProblem();
  }
}
