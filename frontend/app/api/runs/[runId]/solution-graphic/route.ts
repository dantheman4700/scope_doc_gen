import { NextResponse } from "next/server";



export async function GET(_request: Request, { params }: { params: Promise<{runId: string}> }) {
  const { runId } = await params;

  const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8010";
  
  try {
    const response = await fetch(`${backendUrl}/runs/${runId}/solution-graphic`, {
      headers: {
        "Accept": "image/*",
      },
    });
    
    if (!response.ok) {
      return NextResponse.json(
        { error: "Image not available" },
        { status: response.status }
      );
    }
    
    const data = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "image/png";
    
    return new NextResponse(data, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch image" },
      { status: 500 }
    );
  }
}

