import { NextRequest, NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const response = await apiFetchJson<{ message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(body),
    });
    
    if (response.status >= 400) {
      return NextResponse.json(
        response.data || { detail: "Failed to change password" },
        { status: response.status }
      );
    }
    
    return NextResponse.json(response.data, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to change password" },
      { status: 500 }
    );
  }
}

