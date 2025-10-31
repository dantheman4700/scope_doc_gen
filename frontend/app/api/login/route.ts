import { NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const HAS_SUPABASE = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export async function POST(request: Request) {
  if (HAS_SUPABASE) {
    return NextResponse.json(
      { detail: "Login handled client-side via Supabase" },
      { status: 405 }
    );
  }

  const payload = await request.json();

  const backendResponse = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(payload),
    credentials: "include"
  });

  const result = await backendResponse.json().catch(() => ({}));
  const response = NextResponse.json(result, { status: backendResponse.status });
  const setCookie = backendResponse.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }
  return response;
}

