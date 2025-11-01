import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { runId: string };
}

export async function POST(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson(`/runs/${params.runId}/embed`, {
    method: "POST",
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

