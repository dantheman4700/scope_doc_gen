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
    version_number: number;
    is_subversion: boolean;
    message: string;
  }>(`/runs/${runId}/auto-save`, {
    method: "POST",
    body: JSON.stringify(body),
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}
