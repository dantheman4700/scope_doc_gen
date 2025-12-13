import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

export async function GET(
  _request: Request, 
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  
  const response = await apiFetchJson<Record<string, unknown>>(`/runs/${runId}`, {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}
