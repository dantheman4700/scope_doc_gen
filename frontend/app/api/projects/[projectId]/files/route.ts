import { NextResponse } from "next/server";

import { apiFetch, apiFetchJson } from "@/lib/fetch";



export async function POST(request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const contentType = request.headers.get("content-type");
  if (!contentType?.toLowerCase().startsWith("multipart/form-data")) {
    return NextResponse.json({ detail: "multipart/form-data body required" }, { status: 400 });
  }

  const headers = new Headers();
  headers.set("content-type", contentType);

  let backendResponse: Response;
  try {
    backendResponse = await apiFetch(`/projects/${projectId}/files/`, {
      method: "POST",
      body: request.body,
      headers,
      duplex: "half",
      throwIfUnauthorized: false
    });
  } catch (error) {
    console.error("Upload proxy request failed", error);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ detail: `Upload failed: ${message}` }, { status: 502 });
  }

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}

export async function DELETE(request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const url = new URL(request.url);
  const fileId = url.searchParams.get("fileId");
  if (!fileId) {
    return NextResponse.json({ detail: "fileId query parameter required" }, { status: 400 });
  }

  const backendResponse = await apiFetch(`/projects/${projectId}/files/${fileId}`, {
    method: "DELETE",
    throwIfUnauthorized: false
  });

  if (!backendResponse.ok) {
    const payload = await backendResponse.json().catch(() => ({}));
    return NextResponse.json(payload, { status: backendResponse.status });
  }

  return new NextResponse(null, { status: 204 });
}

export async function GET(_request: Request, { params }: { params: Promise<{projectId: string}> }) {
  const { projectId } = await params;

  const response = await apiFetchJson(`/projects/${projectId}/files/`, {
    throwIfUnauthorized: false
  });

  return NextResponse.json(response.data ?? [], { status: response.status });
}

