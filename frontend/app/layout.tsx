import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

import { getSessionUser } from "@/lib/auth";
import LogoutButton from "@/components/LogoutButton";

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
          <div>
            <Link href="/projects">Scope Doc</Link>
          </div>
          <div className="nav-links">
            <Link href="/projects">Projects</Link>
            {user && <Link href="/settings">Settings</Link>}
            {user ? (
              <>
                <span>{user.email}</span>
                <LogoutButton />
              </>
            ) : (
              <Link href="/login">Sign in</Link>
            )}
          </div>
        </nav>
        {/* Items in Progress Banner */}
        {user && (
          <div style={{ 
            margin: "0.75rem 1rem 0", 
            padding: "0.75rem 1rem", 
            background: "linear-gradient(135deg, #1e1e3f 0%, #2d2d5a 100%)", 
            border: "1px solid #4a4a8a",
            borderRadius: "0.5rem",
            fontSize: "0.85rem"
          }}>
            <span style={{ color: "#a5b4fc", fontWeight: 600 }}>🚧 In Progress:</span>
            <span style={{ color: "#9ca3af", marginLeft: "0.5rem" }}>
              UI/UX overhaul • Image generation • Export to Google Docs fixes • Slack auto-outreach
            </span>
          </div>
        )}
        <main>{children}</main>
      </body>
    </html>
  );
}

