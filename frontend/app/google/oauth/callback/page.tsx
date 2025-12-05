"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// Force this page to render dynamically (no prerender) because it depends on
// query string params provided by Google after the OAuth redirect.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string>("Connecting your Google account…");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing OAuth parameters from Google.");
      return;
    }

    async function completeOAuth() {
      try {
        const response = await fetch("/api/google/oauth/callback", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ code, state })
        });
        const data = (await response.json().catch(() => ({}))) as { detail?: string; connected?: boolean };

        if (!response.ok || !data.connected) {
          const detail = data.detail ?? `Google connection failed (${response.status})`;
          throw new Error(detail);
        }

        setStatus("success");
        setMessage("Google Drive connected. Redirecting…");

        // Give the user a moment to see the success message, then go back to projects.
        setTimeout(() => {
          router.replace("/projects");
        }, 1200);
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Google connection failed.";
        setStatus("error");
        setMessage(detail);
      }
    }

    void completeOAuth();
  }, [router, searchParams]);

  return (
    <div className="card" style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>
      <h1>Google Drive Connection</h1>
      <p className={status === "error" ? "error-text" : "success-text"}>{message}</p>
    </div>
  );
}

export default function GoogleOAuthCallbackPage() {
  return (
    <Suspense fallback={<div className="card" style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>Connecting your Google account…</div>}>
      <CallbackContent />
    </Suspense>
  );
}


