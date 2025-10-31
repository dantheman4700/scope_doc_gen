import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { projectId: string };
}

export async function POST(request: Request, { params }: RouteParams) {
  const payload = await request.json();

  const response = await apiFetchJson<Record<string, unknown>>(
    `/projects/${params.projectId}/runs`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      throwIfUnauthorized: false
    }
  );

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

export async function GET(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson(`/projects/${params.projectId}/runs`, {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

