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
  version?: number;
}

export async function POST(request: Request, { params }: RouteParams) {
  // Pass through query parameters (force, version)
  const url = new URL(request.url);
  const queryParams = new URLSearchParams();
  
  const force = url.searchParams.get("force");
  if (force === "true") {
    queryParams.set("force", "true");
  }
  
  const version = url.searchParams.get("version");
  if (version) {
    queryParams.set("version", version);
  }
  
  const queryString = queryParams.toString();
  const backendUrl = `/runs/${params.runId}/export-google-doc${queryString ? `?${queryString}` : ""}`;
  
  const response = await apiFetchJson<ExportResponse>(backendUrl, {
    method: "POST",
    throwIfUnauthorized: false
  });

  // Pass backend payload and status straight through
  return NextResponse.json(response.data ?? {}, { status: response.status });
}


