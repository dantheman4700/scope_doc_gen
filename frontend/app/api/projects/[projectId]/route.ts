import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";
import type { Project } from "@/types/backend";

interface RouteParams {
  params: { projectId: string };
}

export async function GET(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson<Project>(`/projects/${params.projectId}`, {
    throwIfUnauthorized: false
  });

  if (response.status === 404) {
    return NextResponse.json({ detail: "Project not found" }, { status: 404 });
  }

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

