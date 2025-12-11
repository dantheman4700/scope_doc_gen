import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

export async function POST(request: Request, { params }: RouteParams) {
  try {
    const body = await request.json();
    
    const backendResponse = await apiFetch(`/runs/${params.runId}/generate-more-questions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    console.error("Failed to generate more questions:", error);
    return NextResponse.json(
      { error: "Failed to generate more questions" },
      { status: 500 }
    );
  }
}

