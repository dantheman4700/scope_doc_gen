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

export async function POST(request: Request, { params }: RouteParams) {
  // Pass through query parameters (like ?force=true)
  const url = new URL(request.url);
  const force = url.searchParams.get("force");
  const backendUrl = force === "true" 
    ? `/runs/${params.runId}/export-google-doc?force=true`
    : `/runs/${params.runId}/export-google-doc`;
  
  const response = await apiFetchJson<ExportResponse>(backendUrl, {
    method: "POST",
    throwIfUnauthorized: false
  });

  // Pass backend payload and status straight through
  return NextResponse.json(response.data ?? {}, { status: response.status });
}


