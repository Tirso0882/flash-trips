import { getServiceStatus } from "@flash-trips/api-client";
import { createClient } from "@flash-trips/api-client/client";
import { NextResponse } from "next/server";

import { apiBaseUrl } from "../../../lib/server/config";
import { backendUnavailableProblem } from "../../../lib/server/problems";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const client = createClient({ baseUrl: apiBaseUrl() });

  try {
    const { data } = await getServiceStatus({ client, throwOnError: true });
    return NextResponse.json(data);
  } catch {
    return backendUnavailableProblem();
  }
}
