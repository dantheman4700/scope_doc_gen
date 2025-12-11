import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await apiFetchJson<{ default_team_id?: string | null }>("/auth/preferences");
    
    if (response.status >= 400) {
      return NextResponse.json(
        { error: "Failed to fetch preferences" },
        { status: response.status }
      );
    }
    
    // Return just the data, not the wrapper object
    return NextResponse.json(response.data || {});
  } catch (error) {
    console.error("Failed to fetch preferences:", error);
    return NextResponse.json(
      { error: "Failed to fetch preferences" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    
    const response = await apiFetchJson<{ default_team_id?: string | null }>("/auth/preferences", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    
    if (response.status >= 400) {
      return NextResponse.json(
        { error: "Failed to update preferences" },
        { status: response.status }
      );
    }
    
    // Return just the data, not the wrapper object
    return NextResponse.json(response.data || {});
  } catch (error) {
    console.error("Failed to update preferences:", error);
    return NextResponse.json(
      { error: "Failed to update preferences" },
      { status: 500 }
    );
  }
}

