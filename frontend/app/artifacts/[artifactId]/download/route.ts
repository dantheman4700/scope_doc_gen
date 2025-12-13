import { NextResponse } from "next/server";

import { apiFetch } from "@/lib/fetch";

export async function GET(
  _request: Request, 
  { params }: { params: Promise<{ artifactId: string }> }
) {
  const { artifactId } = await params;
  
  const backendResponse = await apiFetch(`/artifacts/${artifactId}/download`, {
    method: "GET",
    throwIfUnauthorized: false,
    redirect: "manual"
  });

  if (backendResponse.status >= 300 && backendResponse.status < 400) {
    const location = backendResponse.headers.get("location");
    if (location) {
      return NextResponse.redirect(location, backendResponse.status);
    }
  }

  const contentType = backendResponse.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = await backendResponse.json().catch(() => ({}));
    const signedUrl = (payload as { signed_url?: string }).signed_url;
    if (signedUrl) {
      return NextResponse.redirect(signedUrl, 302);
    }
    return NextResponse.json(payload ?? {}, { status: backendResponse.status });
  }

  const body = await backendResponse.arrayBuffer();
  const headers = new Headers();

  if (contentType) {
    headers.set("content-type", contentType);
  }

  const disposition = backendResponse.headers.get("content-disposition");
  if (disposition) {
    headers.set("content-disposition", disposition);
  }

  return new NextResponse(body, {
    status: backendResponse.status,
    headers
  });
}
