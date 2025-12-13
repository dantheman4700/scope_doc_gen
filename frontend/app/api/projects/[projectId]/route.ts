import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";
import type { Project } from "@/types/backend";



export async function GET(_request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const response = await apiFetchJson<Project>(`/projects/${projectId}`, {
    throwIfUnauthorized: false
  });

  if (response.status === 404) {
    return NextResponse.json({ detail: "Project not found" }, { status: 404 });
  }

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

