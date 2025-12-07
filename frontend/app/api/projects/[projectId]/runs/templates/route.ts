import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { projectId: string };
}

export async function GET(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson(
    `/projects/${params.projectId}/runs/templates`,
    {
      throwIfUnauthorized: false
    }
  );

  return NextResponse.json(response.data ?? [], { status: response.status });
}

