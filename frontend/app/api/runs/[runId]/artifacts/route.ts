import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteContext {
  params: { runId: string };
}

export async function GET(_request: Request, { params }: RouteContext) {
  const response = await apiFetchJson<unknown>(`/runs/${params.runId}/artifacts`, {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

