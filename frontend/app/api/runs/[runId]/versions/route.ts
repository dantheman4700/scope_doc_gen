import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/fetch";



export async function GET(request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  try {
    const backendResponse = await apiFetch(`/runs/${runId}/versions`);
    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    console.error("Failed to fetch versions:", error);
    return NextResponse.json(
      { error: "Failed to fetch versions" },
      { status: 500 }
    );
  }
}
