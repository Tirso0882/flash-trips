import "server-only";

import type { ProblemResponse } from "@flash-trips/api-client";
import { NextResponse } from "next/server";
import { v7 as uuid7 } from "uuid";

type ProblemWithoutRequestId = Omit<ProblemResponse, "request_id">;

function problemResponse(problem: ProblemWithoutRequestId): NextResponse {
  const requestId = uuid7();
  return NextResponse.json(
    { ...problem, request_id: requestId } satisfies ProblemResponse,
    {
      headers: {
        "content-type": "application/problem+json",
        "x-request-id": requestId,
      },
      status: problem.status,
    },
  );
}

export function authenticationRequiredProblem(): NextResponse {
  return problemResponse({
    code: "authentication_required",
    detail: "Authentication is required.",
    retryable: false,
    status: 401,
    title: "Unauthorized",
    type: "https://flash-trips.example/problems/authentication-required",
  });
}

export function backendUnavailableProblem(): NextResponse {
  return problemResponse({
    code: "backend_unavailable",
    detail: "The application backend is unavailable.",
    retryable: true,
    status: 503,
    title: "Service Unavailable",
    type: "https://flash-trips.example/problems/backend-unavailable",
  });
}

export function invalidRequestProblem(): NextResponse {
  return problemResponse({
    code: "invalid_request",
    detail: "The request did not match the required contract.",
    retryable: false,
    status: 400,
    title: "Invalid Request",
    type: "https://flash-trips.example/problems/invalid-request",
  });
}
