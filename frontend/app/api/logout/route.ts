import { NextResponse } from "next/server";

import { createSupabaseRouteClient } from "@/lib/supabase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const HAS_SUPABASE = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export async function POST() {
  if (HAS_SUPABASE) {
    const supabase = createSupabaseRouteClient();
    await supabase.auth.signOut({ scope: "global" });
    return new NextResponse(null, { status: 204 });
  }

  const backendResponse = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
    redirect: "manual"
  });

  // If backend returns 204, we need to handle it without a body
  if (backendResponse.status === 204) {
    const response = new NextResponse(null, { status: 204 });
    const setCookie = backendResponse.headers.get("set-cookie");
    if (setCookie) {
      response.headers.set("set-cookie", setCookie);
    }
    return response;
  }

  // For other status codes, return JSON
  const response = NextResponse.json({}, { status: backendResponse.status });
  const setCookie = backendResponse.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }
  return response;
}

