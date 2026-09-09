import {
  createTrip,
  listTrips,
  type CreateTripRequest,
} from "@flash-trips/api-client";
import { createClient } from "@flash-trips/api-client/client";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "../../../lib/server/config";
import {
  authenticationRequiredProblem,
  backendUnavailableProblem,
  invalidRequestProblem,
} from "../../../lib/server/problems";
import { sessionManager } from "../../../lib/server/session-runtime";
import {
  applicationSession,
  sessionBoundCsrf,
} from "../../../lib/server/session-policy";

export const dynamic = "force-dynamic";

interface NewTripForm {
  city: string;
  starts_on: string;
  ends_on: string;
  nights: number;
}

interface BackendResult {
  data?: unknown;
  error?: unknown;
  response?: Response;
}

function isNewTripForm(value: unknown): value is NewTripForm {
  return (
    typeof value === "object" &&
    value !== null &&
    "city" in value &&
    typeof value.city === "string" &&
    "starts_on" in value &&
    typeof value.starts_on === "string" &&
    "ends_on" in value &&
    typeof value.ends_on === "string" &&
    "nights" in value &&
    typeof value.nights === "number"
  );
}

function backendResponse(data: unknown, backend: Response): NextResponse {
  const headers = new Headers();
  for (const name of ["content-type", "location", "x-request-id"]) {
    const value = backend.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  return NextResponse.json(data, {
    headers,
    status: backend.status,
  });
}

async function forwardBackend(
  operation: () => Promise<BackendResult>,
): Promise<NextResponse> {
  try {
    const result = await operation();
    if (result.response === undefined) return backendUnavailableProblem();
    return backendResponse(result.data ?? result.error, result.response);
  } catch {
    return backendUnavailableProblem();
  }
}

async function sessionCookie(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(applicationSession.cookieName)?.value;
}

export async function GET(): Promise<NextResponse> {
  const session = await sessionManager().authorize({
    cookieValue: await sessionCookie(),
    method: "GET",
  });
  if (session === null) return authenticationRequiredProblem();

  return forwardBackend(() =>
    listTrips({
      client: createClient({ baseUrl: apiBaseUrl() }),
      headers: { authorization: `Bearer ${session.accessToken}` },
    }),
  );
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const session = await sessionManager().authorize({
    cookieValue: await sessionCookie(),
    csrfToken: request.headers.get(sessionBoundCsrf.requestHeader) ?? undefined,
    method: "POST",
    origin: request.headers.get("origin") ?? undefined,
  });
  if (session === null) return authenticationRequiredProblem();

  let form: unknown;
  try {
    form = await request.json();
  } catch {
    return invalidRequestProblem();
  }
  if (!isNewTripForm(form)) return invalidRequestProblem();
  const body: CreateTripRequest = {
    structure: {
      stays: [form],
    },
  };
  return forwardBackend(() =>
    createTrip({
      body,
      client: createClient({ baseUrl: apiBaseUrl() }),
      headers: { authorization: `Bearer ${session.accessToken}` },
    }),
  );
}
