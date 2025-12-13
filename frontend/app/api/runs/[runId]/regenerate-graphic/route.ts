import { apiFetch } from "@/lib/fetch";
import { NextResponse } from "next/server";



export async function POST(request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  const body = await request.json().catch(() => ({}));
  
  const backendResponse = await apiFetch(`/runs/${runId}/regenerate-graphic`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    throwIfUnauthorized: false,
  });

  if (!backendResponse.ok) {
    const errorData = await backendResponse.json().catch(() => ({ detail: "Unknown error" }));
    return NextResponse.json(errorData, { status: backendResponse.status });
  }

  // Return the image blob
  const blob = await backendResponse.blob();
  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type": backendResponse.headers.get("Content-Type") || "image/png",
    },
  });
}

