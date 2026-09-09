import { getCurrentPlanRevision } from "@flash-trips/api-client";
import { createClient } from "@flash-trips/api-client/client";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { apiBaseUrl } from "../../../../../lib/server/config";
import {
  authenticationRequiredProblem,
  backendUnavailableProblem,
} from "../../../../../lib/server/problems";
import { sessionManager } from "../../../../../lib/server/session-runtime";
import { applicationSession } from "../../../../../lib/server/session-policy";

export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{ tripId: string }>;
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<NextResponse> {
  const cookieStore = await cookies();
  const session = await sessionManager().authorize({
    cookieValue: cookieStore.get(applicationSession.cookieName)?.value,
    method: "GET",
  });
  if (session === null) return authenticationRequiredProblem();

  try {
    const { tripId } = await context.params;
    const result = await getCurrentPlanRevision({
      client: createClient({ baseUrl: apiBaseUrl() }),
      headers: { authorization: `Bearer ${session.accessToken}` },
      path: { trip_id: tripId },
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
