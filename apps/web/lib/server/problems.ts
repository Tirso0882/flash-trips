import "server-only";

import type { ProblemResponse } from "@flash-trips/api-client";
import { NextResponse } from "next/server";
import { v7 as uuid7 } from "uuid";

export function authenticationRequiredProblem(): NextResponse {
  const requestId = uuid7();
  const problem: ProblemResponse = {
    code: "authentication_required",
    detail: "Authentication is required.",
    request_id: requestId,
    retryable: false,
    status: 401,
    title: "Unauthorized",
    type: "https://flash-trips.example/problems/authentication-required",
  };
  return NextResponse.json(problem, {
    headers: {
      "content-type": "application/problem+json",
      "x-request-id": requestId,
    },
    status: 401,
  });
}
