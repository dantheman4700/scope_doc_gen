import { NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface SystemConfig {
  history_enabled: boolean;
}

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/config`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return NextResponse.json({ history_enabled: false }, { status: 200 });
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch {
    return NextResponse.json({ history_enabled: false }, { status: 200 });
  }
}

