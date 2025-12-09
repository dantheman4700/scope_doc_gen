import { NextRequest, NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string; jobId: string };
}

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

export async function GET(_request: NextRequest, { params }: RouteParams) {
  const response = await apiFetchJson<RegenJobStatus>(
    `/runs/${params.runId}/regen-status/${params.jobId}`,
    { throwIfUnauthorized: false }
  );

  if (!response.data) {
    return NextResponse.json({ error: "Job not found" }, { status: response.status || 404 });
  }

  return NextResponse.json(response.data, { status: response.status });
}

