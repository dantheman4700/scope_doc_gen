import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { projectId: string; fileId: string };
}

export async function PATCH(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson(`/projects/${params.projectId}/files/${params.fileId}/toggle-mode`, {
    method: "PATCH",
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}


