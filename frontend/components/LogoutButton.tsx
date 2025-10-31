"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { createSupabaseClient } from "@/lib/supabase-client";

const HAS_SUPABASE = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supabase = useMemo(() => (HAS_SUPABASE ? createSupabaseClient() : null), []);

  async function handleLogout() {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);

    try {
      if (HAS_SUPABASE && supabase) {
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

