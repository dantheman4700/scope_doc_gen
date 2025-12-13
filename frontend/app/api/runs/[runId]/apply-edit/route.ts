import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/fetch";



export async function POST(request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  try {
    const body = await request.json();
    
    const backendResponse = await apiFetch(`/runs/${runId}/apply-edit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    console.error("Failed to apply edit:", error);
    return NextResponse.json(
      { error: "Failed to apply edit" },
      { status: 500 }
    );
  }
}
