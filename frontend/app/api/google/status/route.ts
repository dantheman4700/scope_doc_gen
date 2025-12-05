import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface StatusResponse {
  connected: boolean;
}

export async function GET() {
  const response = await apiFetchJson<StatusResponse>("/google/status", {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? { connected: false }, { status: response.status });
}


