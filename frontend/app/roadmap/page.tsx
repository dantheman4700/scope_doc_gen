import Link from "next/link";

export const metadata = {
  title: "Roadmap · Scope Doc"
};

const ROADMAP_ITEMS = [
  {
    category: "UI/UX",
    items: ["Refresh/cache bugs", "Revert SSR", "Navigation improvements", "Component alignment", "Fluid UX"]
  },
  {
    category: "Image Generation",
    items: ["Auto-insert into DOCX/Google Docs", "Standardized graphics", "Brand matching"]
  },
  {
    category: "Google Docs Export",
    items: ["Integrate markgdoc for complex markdown", "Inline editing of created Google Docs for quick regen"]
  },
  {
    category: "Auto-outreach",
    items: ["Slack integration for expert responses", "Email for client questions"]
  },
  {
    category: "Document Ingestion",
    items: ["Fix token counting for complex files", "Increase recommended limits", "Multi-turn/Sonnet 4.5 1M mode"]
  },
  {
    category: "Admin",
    items: ["Team/org settings control panel"]
  },
  {
    category: "API",
    items: ["Full API with keys for external integration"]
  },
  {
    category: "Vector Store",
    items: ["Validate full history pipeline", "Embeddings viewer/editor", "Easy past doc uploads"]
  },
  {
    category: "Questions",
    items: ["Improved visuals", "Per-question response forms", "Confidence scoring"]
  },
  {
    category: "Chatbot",
    items: ["Per-project chatbot experience", "Per-team chatbot experience"]
  },
  {
    category: "Multi-Scope",
    items: ["Generate multiple scopes at once from the same inputs"]
  },
  {
    category: "PSO → Scope",
    items: ["Reference previous PSO as source for scope generation"]
  },
  {
    category: "Auto-detect",
    items: ["High-confidence solutions with quick-start buttons for scoping"]
  }
];

export default function RoadmapPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", maxWidth: "900px", margin: "0 auto" }}>
      <div className="card">
        <h1>🚧 Items in Progress</h1>
        <p style={{ color: "#9ca3af" }}>
          Features and improvements currently being worked on for the Scope Document Generator.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
        {ROADMAP_ITEMS.map((section) => (
          <div 
            key={section.category} 
            className="card" 
            style={{ 
              padding: "1rem",
              background: "linear-gradient(135deg, #1e1e3f 0%, #2d2d5a 100%)",
              border: "1px solid #4a4a8a"
            }}
          >
            <h3 style={{ margin: "0 0 0.75rem 0", color: "#a5b4fc", fontSize: "1rem" }}>
              {section.category}
            </h3>
            <ul style={{ margin: 0, paddingLeft: "1.25rem", color: "#d1d5db", fontSize: "0.875rem", lineHeight: 1.7 }}>
              {section.items.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="card" style={{ textAlign: "center" }}>
        <Link href="/projects" className="btn-primary" style={{ textDecoration: "none" }}>
          ← Back to Projects
        </Link>
      </div>
    </div>
  );
}

