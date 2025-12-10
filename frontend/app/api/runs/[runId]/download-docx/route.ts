import { NextResponse } from "next/server";

import { apiFetch } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

export async function GET(request: Request, { params }: RouteParams) {
  // Parse version from query string
  const url = new URL(request.url);
  const version = url.searchParams.get("version");
  
  // Build backend URL with optional version param
  let backendUrl = `/runs/${params.runId}/download-docx`;
  if (version) {
    backendUrl += `?version=${version}`;
  }

  const backendResponse = await apiFetch(backendUrl, {
    method: "GET",
    throwIfUnauthorized: false
  });

  const headers = new Headers(backendResponse.headers);
  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers
  });
}
