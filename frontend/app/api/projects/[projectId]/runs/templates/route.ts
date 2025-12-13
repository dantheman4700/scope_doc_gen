import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";



export async function GET(_request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const response = await apiFetchJson(
    `/projects/${projectId}/runs/templates`,
    {
      throwIfUnauthorized: false
    }
  );

  return NextResponse.json(response.data ?? [], { status: response.status });
}

