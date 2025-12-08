import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface DisconnectResponse {
  success: boolean;
  message: string;
}

export async function POST() {
  try {
    const response = await apiFetchJson<DisconnectResponse>("/google-oauth/disconnect", {
      method: "POST",
      throwIfUnauthorized: false,
    });

    if (!response.data) {
      return NextResponse.json(
        { success: false, message: "Failed to disconnect" },
        { status: 500 }
      );
    }

    return NextResponse.json(response.data, { status: response.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Failed to disconnect" },
      { status: 500 }
    );
  }
}
