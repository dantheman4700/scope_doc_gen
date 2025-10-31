import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";
import type { Project } from "@/types/backend";

export async function POST(request: Request) {
  const payload = await request.json();
  const response = await apiFetchJson<Record<string, unknown>>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

export async function GET() {
  const response = await apiFetchJson<Project[]>("/projects", {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

