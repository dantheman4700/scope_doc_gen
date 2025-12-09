import { NextResponse } from "next/server";

import { apiFetchJson } from "@/lib/fetch";

interface RoadmapItem {
  text: string;
  completed: boolean;
}

interface RoadmapSection {
  category: string;
  items: RoadmapItem[];
}

interface RoadmapConfig {
  sections: RoadmapSection[];
}

export async function GET() {
  const response = await apiFetchJson<RoadmapConfig>("/system/roadmap", {
    method: "GET",
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? { sections: [] }, { status: response.status });
}

export async function PUT(request: Request) {
  const body = await request.json();
  
  const response = await apiFetchJson<RoadmapConfig>("/system/roadmap", {
    method: "PUT",
    body: JSON.stringify(body),
    throwIfUnauthorized: false,
  });

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

