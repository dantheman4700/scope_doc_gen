"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { createSupabaseClient, hasSupabase } from "@/lib/supabase-client";

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);

    try {
      if (hasSupabase()) {
        const supabase = createSupabaseClient();
        const { error: signOutError } = await supabase.auth.signOut({ scope: "global" });
        if (signOutError) {
          throw signOutError;
        }
      }

      const response = await fetch("/api/logout", {
        method: "POST",
        credentials: "include",
        redirect: "manual"
      });

      if (response.status === 401) {
        router.push("/login");
        router.refresh();
        return;
      }

      if (response.status >= 200 && response.status < 400) {
        router.push("/login");
        router.refresh();
        return;
      }

      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body?.detail ?? "Unable to sign out");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="logout-control">
      <button className="btn-primary" type="button" onClick={handleLogout} disabled={busy}>
        {busy ? "Signing out…" : "Sign out"}
      </button>
      {error ? <p className="error-text">{error}</p> : null}
    </div>
  );
}

export default LogoutButton;

