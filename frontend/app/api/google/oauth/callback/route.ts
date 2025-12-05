import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface CallbackPayload {
  code: string;
  state: string;
}

interface StatusResponse {
  connected: boolean;
  detail?: string;
}

export async function POST(request: Request) {
  const body = (await request.json()) as CallbackPayload;

  const response = await apiFetchJson<StatusResponse>("/google/oauth/callback", {
    method: "POST",
    body: JSON.stringify(body),
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}


