import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface ConnectResponse {
  authorization_url: string;
}

export async function GET() {
  try {
    const response = await apiFetchJson<ConnectResponse>("/google-oauth/connect", {
      throwIfUnauthorized: false,
    });

    if (!response.data?.authorization_url) {
      return NextResponse.json(
        { error: "Failed to initiate Google connection" },
        { status: 500 }
      );
    }

    return NextResponse.json(response.data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to initiate Google connection" },
      { status: 500 }
    );
  }
}
