import { getServiceStatus } from "@flash-trips/api-client";
import { createClient } from "@flash-trips/api-client/client";
import { NextResponse } from "next/server";
import { v7 as uuid7 } from "uuid";

import { apiBaseUrl } from "../../../lib/server/config";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const client = createClient({ baseUrl: apiBaseUrl() });

  try {
    const { data } = await getServiceStatus({ client, throwOnError: true });
    return NextResponse.json(data);
  } catch {
    const requestId = uuid7();
    return NextResponse.json(
      {
        code: "backend_unavailable",
        detail: "The application backend is unavailable.",
        request_id: requestId,
        retryable: true,
        status: 503,
        title: "Service Unavailable",
        type: "https://flash-trips.example/problems/backend-unavailable",
      },
      {
        headers: {
          "content-type": "application/problem+json",
          "x-request-id": requestId,
        },
        status: 503,
      },
    );
  }
}
