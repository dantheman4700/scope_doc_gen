import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";
import type { Team } from "@/types/backend";

export async function GET() {
  const response = await apiFetchJson<Team[]>("/teams", {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

export async function POST(request: Request) {
  const payload = await request.json();
  const response = await apiFetchJson<Team>("/teams", {
    method: "POST",
    body: JSON.stringify(payload),
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

