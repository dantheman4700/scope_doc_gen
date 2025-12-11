import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

export async function POST(request: Request, { params }: RouteParams) {
  try {
    const backendResponse = await apiFetch(`/runs/${params.runId}/check-ambiguity`, {
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

