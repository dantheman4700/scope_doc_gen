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
            padding: "1rem 1.25rem", 
            background: "linear-gradient(135deg, #1e1e3f 0%, #2d2d5a 100%)", 
            border: "1px solid #4a4a8a",
            borderRadius: "0.5rem",
            fontSize: "0.8rem",
            lineHeight: 1.7
          }}>
            <div style={{ color: "#a5b4fc", fontWeight: 600, marginBottom: "0.5rem" }}>🚧 Items in Progress</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "0.5rem 1.5rem", color: "#9ca3af" }}>
              <div><strong style={{ color: "#d1d5db" }}>UI/UX:</strong> Refresh/cache bugs, revert SSR, navigation, component alignment, fluid UX</div>
              <div><strong style={{ color: "#d1d5db" }}>Image Gen:</strong> Auto-insert into DOCX/Google Docs, standardized graphics, brand matching</div>
              <div><strong style={{ color: "#d1d5db" }}>Google Docs:</strong> Fix markdown conversion bugs over API</div>
              <div><strong style={{ color: "#d1d5db" }}>Auto-outreach:</strong> Slack for expert responses, email for client questions</div>
              <div><strong style={{ color: "#d1d5db" }}>Ingestion:</strong> Fix token counting for complex files, increase recommended limits, multi-turn/Sonnet 4.5 1M mode</div>
              <div><strong style={{ color: "#d1d5db" }}>Admin:</strong> Team/org settings control panel</div>
              <div><strong style={{ color: "#d1d5db" }}>API:</strong> Full API with keys for external integration</div>
              <div><strong style={{ color: "#d1d5db" }}>Vector Store:</strong> Embeddings viewer/editor, easy past doc uploads</div>
              <div><strong style={{ color: "#d1d5db" }}>Questions:</strong> Improved visuals, per-question response forms, confidence scoring</div>
              <div><strong style={{ color: "#d1d5db" }}>Chatbot:</strong> Per-project and per-team chatbot experience</div>
            </div>
          </div>
        )}
        <main>{children}</main>
      </body>
    </html>
  );
}

