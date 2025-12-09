"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface RoadmapItem {
  text: string;
  completed?: boolean;
}

interface RoadmapSection {
  category: string;
  items: RoadmapItem[];
}

// Default roadmap items (fallback when no custom config exists)
const DEFAULT_ROADMAP_ITEMS: RoadmapSection[] = [
  {
    category: "UI/UX",
    items: [
      { text: "Refresh/cache bugs", completed: false },
      { text: "Revert SSR", completed: false },
      { text: "Navigation improvements", completed: false },
      { text: "Component alignment", completed: false },
      { text: "Fluid UX", completed: false }
    ]
  },
  {
    category: "Image Generation",
    items: [
      { text: "Auto-insert into DOCX/Google Docs", completed: false },
      { text: "Standardized graphics", completed: false },
      { text: "Brand matching", completed: false }
    ]
  },
  {
    category: "Google Docs Export",
    items: [
      { text: "Integrate markgdoc for complex markdown", completed: true },
      { text: "Inline editing of created Google Docs for quick regen", completed: false },
      { text: "OAuth to allow all Google users (not just test users)", completed: false }
    ]
  },
  {
    category: "Auto-outreach",
    items: [
      { text: "Slack integration for expert responses", completed: false },
      { text: "Email for client questions", completed: false }
    ]
  },
  {
    category: "Document Ingestion",
    items: [
      { text: "Fix token counting for complex files", completed: false },
      { text: "Increase recommended limits", completed: false },
      { text: "Multi-turn/Sonnet 4.5 1M mode", completed: false }
    ]
  },
  {
    category: "Admin",
    items: [
      { text: "Team/org settings control panel", completed: true },
      { text: "Improved settings", completed: false },
      { text: "Improved permissions hierarchies", completed: false }
    ]
  },
  {
    category: "Account",
    items: [
      { text: "Password reset option", completed: false }
    ]
  },
  {
    category: "API",
    items: [
      { text: "Full API with keys for external integration", completed: false }
    ]
  },
  {
    category: "Vector Store",
    items: [
      { text: "Validate full history pipeline", completed: false },
      { text: "Embeddings viewer/editor", completed: false },
      { text: "Easy past doc uploads", completed: false }
    ]
  },
  {
    category: "Questions",
    items: [
      { text: "Improved visuals", completed: false },
      { text: "Per-question response forms", completed: false },
      { text: "Confidence scoring", completed: false }
    ]
  },
  {
    category: "Chatbot",
    items: [
      { text: "Per-project chatbot experience", completed: false },
      { text: "Per-team chatbot experience", completed: false }
    ]
  },
  {
    category: "Multi-Scope",
    items: [
      { text: "Generate multiple scopes at once from the same inputs", completed: false }
    ]
  },
  {
    category: "PSO → Scope",
    items: [
      { text: "Reference previous PSO as source for scope generation", completed: false }
    ]
  },
  {
    category: "Auto-detect",
    items: [
      { text: "High-confidence solutions with quick-start buttons for scoping", completed: false }
    ]
  }
];

export default function RoadmapPage() {
  const [sections, setSections] = useState<RoadmapSection[]>(DEFAULT_ROADMAP_ITEMS);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fetch global roadmap (shared across all teams)
    fetch("/api/system/roadmap")
      .then((res) => res.json())
      .then((data) => {
        if (data?.sections && data.sections.length > 0) {
          setSections(data.sections);
        }
        // If empty, keep the defaults
        setIsLoading(false);
      })
      .catch(() => {
        // On error, keep defaults
        setIsLoading(false);
      });
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", maxWidth: "900px", margin: "0 auto" }}>
      <div className="card">
        <h1>🚧 Items in Progress</h1>
        <p style={{ color: "#9ca3af" }}>
          Features and improvements currently being worked on for the Scope Document Generator.
        </p>
      </div>

      {isLoading ? (
        <div className="card">
          <p>Loading roadmap...</p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
          {sections.map((section) => (
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
                  <li key={idx} style={item.completed ? { textDecoration: "line-through", color: "#6b7280" } : undefined}>
                    {item.completed && <span style={{ marginRight: "0.25rem" }}>✓</span>}
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ textAlign: "center" }}>
        <Link href="/projects" className="btn-primary" style={{ textDecoration: "none" }}>
          ← Back to Projects
        </Link>
      </div>
    </div>
  );
}
