import { apiFetch } from "@/lib/fetch";
import { NextRequest } from "next/server";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ projectId: string; fileId: string }> }
) {
  const { projectId, fileId } = await params;
  
  try {
    const backendResponse = await apiFetch(
      `/projects/${projectId}/files/${fileId}/download`,
      {
        method: "GET",
        throwIfUnauthorized: false,
      }
    );

    if (!backendResponse.ok) {
      const text = await backendResponse.text().catch(() => "Download failed");
      return new Response(text, { status: backendResponse.status });
    }

    const contentType = backendResponse.headers.get("content-type") ?? "application/octet-stream";
    const contentDisposition = backendResponse.headers.get("content-disposition");
    const contentLength = backendResponse.headers.get("content-length");

    const headers = new Headers();
    headers.set("Content-Type", contentType);
    if (contentDisposition) {
      headers.set("Content-Disposition", contentDisposition);
    }
    if (contentLength) {
      headers.set("Content-Length", contentLength);
    }

    const body = await backendResponse.arrayBuffer();
    return new Response(body, {
      status: 200,
      headers,
    });
  } catch (error) {
    console.error("File download failed:", error);
    return new Response("Failed to download file", { status: 500 });
  }
}
