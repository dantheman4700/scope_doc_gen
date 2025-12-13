import { NextRequest, NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RegenJobStatus {
  id: string;
  run_id: string;
  status: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  version_id?: string;
  version_number?: number;
  error?: string;
}

export async function GET(
  _request: NextRequest, 
  { params }: { params: Promise<{ runId: string; jobId: string }> }
) {
  const { runId, jobId } = await params;

  const response = await apiFetchJson<RegenJobStatus>(
    `/runs/${runId}/regen-status/${jobId}`,
    { throwIfUnauthorized: false }
  );

  if (!response.data) {
    return NextResponse.json({ error: "Job not found" }, { status: response.status || 404 });
  }

  return NextResponse.json(response.data, { status: response.status });
}
