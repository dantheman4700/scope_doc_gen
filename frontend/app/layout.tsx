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
              <div><strong style={{ color: "#d1d5db" }}>Google Docs:</strong> Integrate markgdoc for complex markdown, per-user OAuth connection</div>
              <div><strong style={{ color: "#d1d5db" }}>Auto-outreach:</strong> Slack for expert responses, email for client questions</div>
              <div><strong style={{ color: "#d1d5db" }}>Ingestion:</strong> Fix token counting for complex files, increase recommended limits, multi-turn/Sonnet 4.5 1M mode</div>
              <div><strong style={{ color: "#d1d5db" }}>Admin:</strong> Team/org settings control panel</div>
              <div><strong style={{ color: "#d1d5db" }}>API:</strong> Full API with keys for external integration</div>
              <div><strong style={{ color: "#d1d5db" }}>Vector Store:</strong> Validate full history pipeline, embeddings viewer/editor, easy past doc uploads</div>
              <div><strong style={{ color: "#d1d5db" }}>Questions:</strong> Improved visuals, per-question response forms, confidence scoring</div>
              <div><strong style={{ color: "#d1d5db" }}>Chatbot:</strong> Per-project and per-team chatbot experience</div>
              <div><strong style={{ color: "#d1d5db" }}>Multi-Scope:</strong> Generate multiple scopes at once from the same inputs</div>
              <div><strong style={{ color: "#d1d5db" }}>PSO → Scope:</strong> Reference previous PSO as source for scope generation</div>
              <div><strong style={{ color: "#d1d5db" }}>Auto-detect:</strong> High-confidence solutions with quick-start buttons for scoping</div>
            </div>
          </div>
        )}
        <main>{children}</main>
      </body>
    </html>
  );
}

