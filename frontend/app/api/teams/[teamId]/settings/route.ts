import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";



export interface TeamSettings {
  team_id?: string;
  scope_prompt?: string | null;
  pso_prompt?: string | null;
  image_prompt?: string | null;
  pso_image_prompt?: string | null;
  enable_solution_image?: boolean;
  enable_pso_image?: boolean;
  scope_template_id?: string | null;
  pso_template_id?: string | null;
  vector_similar_limit?: number;
  enable_oneshot_research?: boolean;
  enable_oneshot_vector?: boolean;
  research_mode_default?: string;
  image_size?: string;
}

export async function GET(_request: Request, { params }: { params: Promise<{teamId: string}> }) {
  const { teamId } = await params;

  const response = await apiFetchJson<TeamSettings>(`/teams/${teamId}/settings`, {
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? {}, { status: response.status });
}

export async function PUT(request: Request, { params }: { params: Promise<{teamId: string}> }) {
  const { teamId } = await params;

  const payload = await request.json();
  const response = await apiFetchJson<TeamSettings>(`/teams/${teamId}/settings`, {
    method: "PUT",
    body: JSON.stringify(payload),
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? {}, { status: response.status });
}

