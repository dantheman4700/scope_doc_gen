import { NextResponse } from "next/server";
import { apiFetchJson } from "@/lib/fetch";

interface RegenerateRequest {
  answers: string;
  regen_graphic: boolean;
  extra_research: boolean;
  research_provider: string;
}

interface RegenerateResponse {
  version_id: string;
  version_number: number;
  message: string;
}

export async function POST(
  request: Request,
  { params }: { params: { runId: string } }
) {
  const body = (await request.json()) as RegenerateRequest;
  
  const response = await apiFetchJson<RegenerateResponse>(
    `/runs/${params.runId}/regenerate`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );

  return NextResponse.json(response.data ?? {}, { status: response.status });
}

