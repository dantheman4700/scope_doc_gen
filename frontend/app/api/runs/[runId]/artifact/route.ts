import { NextRequest } from "next/server";
import { apiFetch } from "@/lib/fetch";



export async function GET(request: NextRequest, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  try {
    const { searchParams } = new URL(request.url);
    const kind = searchParams.get("kind") || "rendered_doc";
    
    // First get the run to find project ID
    const runRes = await apiFetch(`/runs/${runId}`);
    if (!runRes.ok) {
      return new Response("Run not found", { status: 404 });
    }
    const runData = await runRes.json();
    
    // Get artifact content
    // For rendered_doc, use download-md endpoint
    if (kind === "rendered_doc") {
      const mdRes = await apiFetch(`/runs/${runId}/download-md`);
      if (!mdRes.ok) {
        return new Response("Artifact not found", { status: 404 });
      }
      const text = await mdRes.text();
      return new Response(text, {
        status: 200,
        headers: { "Content-Type": "text/markdown; charset=utf-8" },
      });
    }
    
    return new Response("Artifact type not supported", { status: 400 });
  } catch (error) {
    console.error("Failed to fetch artifact:", error);
    return new Response("Failed to fetch artifact", { status: 500 });
  }
}
