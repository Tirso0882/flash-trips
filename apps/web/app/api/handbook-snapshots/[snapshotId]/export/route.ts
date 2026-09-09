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
  params: Promise<{ snapshotId: string }>;
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
    const { snapshotId } = await context.params;
    const response = await fetch(
      `${apiBaseUrl()}/api/v1/handbook-snapshots/${encodeURIComponent(snapshotId)}/export`,
      {
        cache: "no-store",
        headers: { authorization: `Bearer ${session.accessToken}` },
      },
    );
    const content = await response.arrayBuffer();
    if (!response.ok) {
      return new NextResponse(content, {
        headers: {
          "content-type":
            response.headers.get("content-type") ?? "application/problem+json",
          "x-request-id": response.headers.get("x-request-id") ?? "",
        },
        status: response.status,
      });
    }
    return new NextResponse(content, {
      headers: {
        "content-disposition":
          response.headers.get("content-disposition") ??
          `attachment; filename="flash-trips-${snapshotId}.html"`,
        "content-type": "text/html; charset=utf-8",
        digest: response.headers.get("digest") ?? "",
        "x-request-id": response.headers.get("x-request-id") ?? "",
      },
      status: response.status,
    });
  } catch {
    return backendUnavailableProblem();
  }
}
