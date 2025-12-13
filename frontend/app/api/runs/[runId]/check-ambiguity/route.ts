import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/fetch";



export async function POST(request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  try {
    const backendResponse = await apiFetch(`/runs/${runId}/check-ambiguity`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    console.error("Failed to check ambiguity:", error);
    return NextResponse.json(
      { error: "Failed to check ambiguity" },
      { status: 500 }
    );
  }
}

