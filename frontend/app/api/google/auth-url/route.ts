import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface AuthUrlResponse {
  url: string;
}

export async function GET() {
  const response = await apiFetchJson<AuthUrlResponse>("/google/auth-url", {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}


