import { apiFetch } from "@/lib/fetch";



export async function POST(request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  try {
    const body = await request.json();

    // Use apiFetch which handles both cookies and Supabase Bearer token
    const backendResponse = await apiFetch(`/runs/${runId}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      throwIfUnauthorized: false,
    });

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text();
      return new Response(
        JSON.stringify({ error: errorText }),
        { 
          status: backendResponse.status,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Stream SSE response to client
    return new Response(backendResponse.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    console.error("Chat request failed:", error);
    return new Response(
      JSON.stringify({ error: "Chat request failed" }),
      { 
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
