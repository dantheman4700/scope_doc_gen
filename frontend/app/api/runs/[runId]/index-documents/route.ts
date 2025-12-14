import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  const body = await request.json();

  const response = await apiFetchJson<{
    success: boolean;
    indexed_chunks: number;
    deleted_old: number;
    version: number;
    message: string;
  }>(`/runs/${runId}/index-documents`, {
    method: "POST",
    body: JSON.stringify(body),
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}
