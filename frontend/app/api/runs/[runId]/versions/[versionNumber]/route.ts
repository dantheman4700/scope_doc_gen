import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ runId: string; versionNumber: string }> }
) {
  const { runId, versionNumber } = await params;

  const response = await apiFetchJson<{
    success: boolean;
    message: string;
  }>(`/runs/${runId}/versions/${versionNumber}`, {
    method: "DELETE",
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}
