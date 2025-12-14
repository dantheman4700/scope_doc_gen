import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;

  const response = await apiFetchJson<{
    is_indexed: boolean;
    indexed_chunks: number;
  }>(`/runs/${runId}/index-status`, {
    method: "GET",
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? { is_indexed: false, indexed_chunks: 0 }, { status: response.status });
}
