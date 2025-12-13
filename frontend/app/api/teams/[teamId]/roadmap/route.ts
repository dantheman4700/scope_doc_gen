import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";



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

export async function GET(_request: Request, { params }: { params: Promise<{teamId: string}> }) {
  const { teamId } = await params;

  const response = await apiFetchJson<RoadmapConfig>(`/teams/${teamId}/roadmap`, {
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? { sections: [] }, { status: response.status });
}

export async function PUT(request: Request, { params }: { params: Promise<{teamId: string}> }) {
  const { teamId } = await params;

  const payload = await request.json();
  const response = await apiFetchJson<RoadmapConfig>(`/teams/${teamId}/roadmap`, {
    method: "PUT",
    body: JSON.stringify(payload),
    throwIfUnauthorized: false,
  });
  return NextResponse.json(response.data ?? { sections: [] }, { status: response.status });
}

