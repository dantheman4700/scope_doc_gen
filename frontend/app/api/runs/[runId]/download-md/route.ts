import { NextResponse } from "next/server";

import { apiFetch } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

export async function GET(_request: Request, { params }: RouteParams) {
  const backendResponse = await apiFetch(`/runs/${params.runId}/download-md`, {
    method: "GET",
    throwIfUnauthorized: false
  });

  const headers = new Headers(backendResponse.headers);
  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers
  });
}


