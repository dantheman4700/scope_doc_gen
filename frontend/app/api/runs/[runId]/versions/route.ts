import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";
import type { RunVersion } from "@/types/backend";

export async function GET(
  request: Request,
  { params }: { params: { runId: string } }
) {
  const response = await apiFetchJson<RunVersion[]>(
    `/runs/${params.runId}/versions`,
    { method: "GET" }
  );

  return NextResponse.json(response.data ?? [], { status: response.status });
}

