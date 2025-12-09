import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

import { getSessionUser } from "@/lib/auth";
import LogoutButton from "@/components/LogoutButton";
import { APP_VERSION } from "@/lib/version";

export const metadata: Metadata = {
  title: "Scope Doc Dashboard",
  description: "Internal scope document management portal"
};

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  return (
    <html lang="en">
      <body>
        <nav>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <Link href="/projects">Scope Doc</Link>
            <span style={{ fontSize: "0.7rem", color: "#6b7280" }}>v{APP_VERSION}</span>
          </div>
          <div className="nav-links">
            <Link href="/roadmap" style={{ color: "#fbbf24" }}>🚧 In Progress</Link>
            <Link href="/docs" style={{ color: "#a5b4fc" }}>📖 Documentation</Link>
            <Link href="/projects" style={{ color: "#60a5fa" }}>📁 Projects</Link>
            {user && <Link href="/settings" style={{ color: "#34d399" }}>⚙️ Settings</Link>}
            {user ? (
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginLeft: "0.5rem" }}>
                <span style={{ color: "#9ca3af" }}>{user.email}</span>
                <LogoutButton />
              </div>
            ) : (
              <Link href="/login">Sign in</Link>
            )}
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}

