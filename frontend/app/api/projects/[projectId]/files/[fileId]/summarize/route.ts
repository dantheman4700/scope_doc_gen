import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

export async function POST(
  _request: Request, 
  { params }: { params: Promise<{ projectId: string; fileId: string }> }
) {
  const { projectId, fileId } = await params;

  const response = await apiFetchJson(`/projects/${projectId}/files/${fileId}/summarize`, {
    method: "POST",
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}
