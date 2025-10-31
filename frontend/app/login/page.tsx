import Link from "next/link";
import { Suspense } from "react";

import { getSessionUser } from "@/lib/auth";
import { LoginForm } from "@/components/LoginForm";
import { redirect } from "next/navigation";

export const metadata = {
  title: "Sign in · Scope Doc"
};

export default async function LoginPage() {
  const existing = await getSessionUser();
  if (existing) {
    redirect("/projects");
  }

  return (
    <div style={{ display: "flex", justifyContent: "center", paddingTop: "4rem" }}>
      <Suspense fallback={null}>
      <LoginForm />
      </Suspense>
    </div>
  );
}

