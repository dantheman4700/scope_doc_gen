import Link from "next/link";

export const metadata = {
  title: "Documentation · Scope Doc"
};

export default function DocsPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", maxWidth: "900px", margin: "0 auto" }}>
      <div className="card">
        <h1>📖 Documentation</h1>
        <p style={{ color: "#111827" }}>
          Welcome to the Scope Document Generator. This guide will help you understand how to use the system effectively.
        </p>
      </div>

      <div className="card">
        <h2>🚀 Quick Start</h2>
        <ol style={{ paddingLeft: "1.5rem", lineHeight: 1.8, color: "#111827" }}>
          <li><strong>Create a Project:</strong> Click &quot;New Project&quot; and give it a name and description.</li>
          <li><strong>Upload Documents:</strong> Add your discovery documents, meeting notes, requirements, etc.</li>
          <li><strong>Select Files:</strong> Choose which files to include in the scope generation.</li>
          <li><strong>Choose Template:</strong> Select &quot;Scope&quot; for full scopes or &quot;PSO&quot; for solution comparisons.</li>
          <li><strong>Configure Options:</strong> Set research mode, vector search, and other options.</li>
          <li><strong>Generate:</strong> Click &quot;Start Run&quot; and wait for the AI to generate your document.</li>
          <li><strong>Review &amp; Refine:</strong> Answer expert questions and use Quick Regen to improve.</li>
        </ol>
      </div>

      <div className="card">
        <h2>📄 Templates</h2>
        <div style={{ display: "grid", gap: "1rem" }}>
          <div style={{ padding: "1rem", background: "#1f2937", borderRadius: "0.5rem" }}>
            <h3 style={{ margin: "0 0 0.5rem 0", color: "#60a5fa" }}>Scope Document</h3>
            <p style={{ margin: 0, color: "#e5e7eb" }}>
              Full technical scope documents with proposed solutions, timeline, pricing, and implementation details.
              Best for client-facing project proposals.
            </p>
          </div>
          <div style={{ padding: "1rem", background: "#1f2937", borderRadius: "0.5rem" }}>
            <h3 style={{ margin: "0 0 0.5rem 0", color: "#a78bfa" }}>PSO (Potential Solutions Overview)</h3>
            <p style={{ margin: 0, color: "#e5e7eb" }}>
              Comparison documents evaluating multiple solution approaches. Includes comparison matrices
              and recommendations. Best for internal decision-making.
            </p>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>⚙️ Generation Options</h2>
        <table className="table" style={{ marginTop: "1rem" }}>
          <thead>
            <tr>
              <th>Option</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Research Mode</strong></td>
              <td style={{ color: "#111827" }}>
                <strong>None:</strong> No external research<br/>
                <strong>Quick:</strong> Claude web search for APIs/services<br/>
                <strong>Full:</strong> Perplexity deep research
              </td>
            </tr>
            <tr>
              <td><strong>Vector Search</strong></td>
              <td style={{ color: "#111827" }}>Search past scopes for similar projects to use as context for better estimates and solutions.</td>
            </tr>
            <tr>
              <td><strong>Save to Vector Store</strong></td>
              <td style={{ color: "#111827" }}>After generation, save the scope to the vector store for future similarity searches.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>🖼️ Solution Graphics</h2>
        <p style={{ color: "#111827" }}>
          When enabled in Settings, the system generates AI-powered architecture diagrams using Google&apos;s Gemini 
          (Nano Banana Pro). These graphics visualize your proposed solution and can be downloaded or zoomed.
        </p>
        <p style={{ color: "#111827", marginTop: "0.5rem" }}>
          Configure resolution (1K, 2K, 4K) and aspect ratio in team settings.
        </p>
      </div>

      <div className="card">
        <h2>❓ Expert &amp; Client Questions</h2>
        <p style={{ color: "#111827" }}>
          After generation, the AI automatically produces clarifying questions:
        </p>
        <ul style={{ paddingLeft: "1.5rem", color: "#111827", lineHeight: 1.8 }}>
          <li><strong>Expert Questions:</strong> Technical clarifications for the solutions architect</li>
          <li><strong>Client Questions:</strong> Follow-up questions to ask the client</li>
        </ul>
        <p style={{ color: "#111827", marginTop: "0.5rem" }}>
          Answer the expert questions in the text box and click &quot;Quick Regen with Answers&quot; to improve the scope.
        </p>
      </div>

      <div className="card">
        <h2>⚡ Quick Regen</h2>
        <p style={{ color: "#111827" }}>
          Use Quick Regen to refine an existing scope without re-running the full generation. 
          Provide answers to expert questions or additional context, and the AI will update the document accordingly.
        </p>
      </div>

      <div className="card">
        <h2>🔧 Settings</h2>
        <p style={{ color: "#111827" }}>
          Visit <Link href="/settings" className="link">Settings</Link> to configure team-level defaults:
        </p>
        <ul style={{ paddingLeft: "1.5rem", color: "#111827", lineHeight: 1.8 }}>
          <li>Default research mode</li>
          <li>Vector search results limit</li>
          <li>Image generation (enable/disable, resolution, aspect ratio)</li>
          <li>Custom prompts for scope and PSO generation</li>
          <li>Template IDs for Google Drive templates</li>
          <li>Google account connection for exports</li>
        </ul>
      </div>

      <div className="card">
        <h2>📤 Export to Google Docs</h2>
        <p style={{ color: "#111827" }}>
          Export your generated scopes directly to Google Docs. Connect your Google account in Settings 
          to enable personalized exports to your own Drive.
        </p>
        <p style={{ color: "#111827", marginTop: "0.5rem" }}>
          <strong>Note:</strong> Complex markdown formatting is being improved with markgdoc integration.
        </p>
      </div>

      <div className="card" style={{ textAlign: "center" }}>
        <Link href="/projects" className="btn-primary" style={{ textDecoration: "none" }}>
          ← Back to Projects
        </Link>
      </div>
    </div>
  );
}
