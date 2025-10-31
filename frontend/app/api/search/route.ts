import { NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const payload = await request.json();
  const backendResponse = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(payload),
    credentials: "include"
  });

  const body = backendResponse.headers.get("content-type")?.includes("application/json")
    ? await backendResponse.json()
    : await backendResponse.text();

  return NextResponse.json(body, { status: backendResponse.status });
}

