"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { createSupabaseClient, hasSupabase } from "@/lib/supabase-client";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  
  // Only create Supabase client when actually needed (on submit), not on component mount
  const getSupabase = () => hasSupabase() ? createSupabaseClient() : null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const supabase = getSupabase();
      if (supabase) {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) {
          setError(authError.message ?? "Unable to sign in");
          setBusy(false);
          return;
        }
      } else {
        const response = await fetch("/api/login", {
          method: "POST",
          headers: {
            "content-type": "application/json"
          },
          body: JSON.stringify({ email, password })
        });

        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          setError(payload?.detail ?? "Unable to sign in");
          setBusy(false);
          return;
        }
      }

      const next = searchParams?.get("next") ?? "/projects";
      router.push(next);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ maxWidth: 360 }}>
      <h1>Sign in</h1>
      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="form-field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {error ? <p style={{ color: "#dc2626" }}>{error}</p> : null}
      <button className="btn-primary" type="submit" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

