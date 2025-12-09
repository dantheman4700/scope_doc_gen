import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RouteParams {
  params: { teamId: string };
}

export interface RoadmapItem {
  text: string;
  completed: boolean;
}

export interface RoadmapSection {
  category: string;
  items: RoadmapItem[];
}

export interface RoadmapConfig {
  sections: RoadmapSection[];
}

export async function GET(_request: Request, { params }: RouteParams) {
  const response = await apiFetchJson<RoadmapConfig>(`/teams/${params.teamId}/roadmap`, {
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? { sections: [] }, { status: response.status });
}

export async function PUT(request: Request, { params }: RouteParams) {
  const payload = await request.json();
  const response = await apiFetchJson<RoadmapConfig>(`/teams/${params.teamId}/roadmap`, {
    method: "PUT",
    body: JSON.stringify(payload),
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? { sections: [] }, { status: response.status });
}

