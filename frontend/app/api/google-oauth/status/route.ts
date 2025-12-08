import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface GoogleConnectionStatus {
  connected: boolean;
  email: string | null;
  can_export: boolean;
}

export async function GET() {
  try {
    const response = await apiFetchJson<GoogleConnectionStatus>("/google-oauth/status", {
      throwIfUnauthorized: false,
    });

    if (!response.data) {
      return NextResponse.json(
        { connected: false, email: null, can_export: false },
        { status: 200 }
      );
    }

    return NextResponse.json(response.data, { status: response.status });
  } catch {
    return NextResponse.json(
      { connected: false, email: null, can_export: false },
      { status: 200 }
    );
  }
}
