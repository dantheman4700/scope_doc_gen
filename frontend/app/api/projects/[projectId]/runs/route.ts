import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";



export async function POST(request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const payload = await request.json();

  const response = await apiFetchJson<Record<string, unknown>>(
    `/projects/${projectId}/runs`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      throwIfUnauthorized: false
    }
  );

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

export async function GET(_request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const response = await apiFetchJson(`/projects/${projectId}/runs`, {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

