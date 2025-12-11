"use client";

import { useState, useCallback, useEffect } from "react";
import { Save, Copy, X, Loader2 } from "lucide-react";

interface MarkdownEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  content: string;
  version: number;
  runId: string;
  onSave: (content: string) => Promise<boolean>;
  onCopy: () => void;
}

// Simple markdown renderer that converts basic markdown to styled HTML
function renderMarkdown(markdown: string): string {
  let html = markdown
    // Escape HTML
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Headers
    .replace(/^### (.*)$/gm, '<h3 style="color:#10b981;margin:1em 0 0.5em;font-size:1.1em;">$1</h3>')
    .replace(/^## (.*)$/gm, '<h2 style="color:#60a5fa;margin:1.2em 0 0.5em;font-size:1.3em;">$1</h2>')
    .replace(/^# (.*)$/gm, '<h1 style="color:#a78bfa;margin:1.5em 0 0.5em;font-size:1.5em;">$1</h1>')
    // Bold and italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#f0f0f0;">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Lists
    .replace(/^- (.*)$/gm, '<li style="margin-left:1.5em;list-style:disc;">$1</li>')
    .replace(/^\d+\. (.*)$/gm, '<li style="margin-left:1.5em;list-style:decimal;">$1</li>')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre style="background:#1e1e2e;padding:0.75em;border-radius:4px;overflow-x:auto;margin:0.5em 0;"><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code style="background:#1e1e2e;padding:0.15em 0.3em;border-radius:3px;font-size:0.9em;">$1</code>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #374151;margin:1em 0;"/>')
    // Line breaks (double newline becomes paragraph break)
    .replace(/\n\n/g, '</p><p style="margin:0.5em 0;">')
    // Single newlines become <br>
    .replace(/\n/g, '<br/>');
  
  return `<p style="margin:0.5em 0;">${html}</p>`;
}

export function MarkdownEditorModal({
  isOpen,
  onClose,
  content,
  version,
  runId,
  onSave,
  onCopy,
}: MarkdownEditorModalProps) {
  const [editedContent, setEditedContent] = useState(content);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [renderedHtml, setRenderedHtml] = useState("");

  // Sync content when prop changes
  useEffect(() => {
    setEditedContent(content);
    setHasChanges(false);
  }, [content]);

  // Render markdown whenever edited content changes
  useEffect(() => {
    setRenderedHtml(renderMarkdown(editedContent));
  }, [editedContent]);

  const handleContentChange = useCallback((newContent: string) => {
    setEditedContent(newContent);
    setHasChanges(newContent !== content);
  }, [content]);

  const handleSave = useCallback(async () => {
    if (!hasChanges) return;
    
    setIsSaving(true);
    const success = await onSave(editedContent);
    setIsSaving(false);
    
    if (success) {
      setHasChanges(false);
    }
  }, [editedContent, hasChanges, onSave]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (hasChanges && !isSaving) {
          handleSave();
        }
      }
      if (e.key === "Escape") {
        onClose();
      }
    };
    
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, hasChanges, isSaving, handleSave, onClose]);

  const handleClose = useCallback(() => {
    if (hasChanges) {
      if (!confirm("You have unsaved changes. Close anyway?")) {
        return;
      }
    }
    onClose();
  }, [hasChanges, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.8)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000,
        padding: "1rem",
      }}
      onClick={handleClose}
    >
      <div
        className="card"
        style={{
          width: "95vw",
          maxWidth: "1600px",
          height: "90vh",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          padding: "1rem",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h2 style={{ margin: 0 }}>
              Edit Markdown (v{version})
            </h2>
            {hasChanges && (
              <span className="chip chip--warning" style={{ fontSize: "0.75rem" }}>
                Unsaved changes
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {/* Save button */}
            <button
              className="btn-primary"
              type="button"
              onClick={handleSave}
              disabled={!hasChanges || isSaving}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}
            >
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save as v{version}.{Math.floor(Math.random() * 9) + 1}
            </button>
            
            {/* Copy button */}
            <button
              className="btn-secondary"
              type="button"
              onClick={onCopy}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}
            >
              <Copy className="h-4 w-4" />
              Copy
            </button>
            
            {/* Close button */}
            <button
              className="btn-secondary"
              type="button"
              onClick={handleClose}
              style={{ padding: "0.5rem" }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Side-by-side content area */}
        <div
          style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.75rem",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          {/* Editor pane */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              borderRadius: "0.5rem",
              border: "1px solid #374151",
              background: "#0a0a12",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "0.5rem 0.75rem",
                background: "#1f2937",
                borderBottom: "1px solid #374151",
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#9ca3af",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              ✏️ Editor
            </div>
            <textarea
              value={editedContent}
              onChange={(e) => handleContentChange(e.target.value)}
              style={{
                flex: 1,
                width: "100%",
                padding: "1rem",
                background: "transparent",
                border: "none",
                color: "#e5e7eb",
                fontSize: "0.875rem",
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                lineHeight: 1.7,
                resize: "none",
                outline: "none",
              }}
              spellCheck={false}
              placeholder="Enter your markdown here..."
            />
          </div>

          {/* Preview pane */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              borderRadius: "0.5rem",
              border: "1px solid #374151",
              background: "#0f0f1a",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "0.5rem 0.75rem",
                background: "#1f2937",
                borderBottom: "1px solid #374151",
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#9ca3af",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              👁️ Preview
            </div>
            <div
              style={{
                flex: 1,
                overflow: "auto",
                padding: "1rem",
                color: "#d1d5db",
                fontSize: "0.9rem",
                lineHeight: 1.7,
              }}
              dangerouslySetInnerHTML={{ __html: renderedHtml }}
            />
          </div>
        </div>

        {/* Footer hint */}
        <div style={{ fontSize: "0.75rem", color: "#6b7280", display: "flex", justifyContent: "space-between", flexShrink: 0 }}>
          <span>
            Edit the markdown on the left. Preview updates in real-time on the right.
          </span>
          <span>
            Press Ctrl/Cmd+S to save • Esc to close
          </span>
        </div>
      </div>
    </div>
  );
}

export default MarkdownEditorModal;
