import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";



export async function POST(_request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  const response = await apiFetchJson(`/runs/${runId}/embed`, {
    method: "POST",
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

