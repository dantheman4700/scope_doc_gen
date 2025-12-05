import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

interface ExportResponse {
  doc_id?: string;
  doc_url?: string;
  status?: string;
  detail?: string;
}

export async function POST(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson<ExportResponse>(`/runs/${params.runId}/export-google-doc`, {
    method: "POST",
    throwIfUnauthorized: false
  });

  // Pass backend payload and status straight through
  return NextResponse.json(response.data ?? {}, { status: response.status });
}


