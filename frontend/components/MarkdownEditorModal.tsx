"use client";

import { useState, useCallback, useEffect } from "react";
import { Save, Copy, X, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  content: string;
  version: number;
  runId: string;
  onSave: (content: string) => Promise<{ success: boolean; sub_version?: number; version?: number }>;
  onCopy: () => void;
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
  const [currentSubVersion, setCurrentSubVersion] = useState<number>(0);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Sync content when prop changes
  useEffect(() => {
    setEditedContent(content);
    setHasChanges(false);
    setCurrentSubVersion(0);
    setSaveMessage(null);
  }, [content]);

  const handleContentChange = useCallback((newContent: string) => {
    setEditedContent(newContent);
    setHasChanges(newContent !== content);
    setSaveMessage(null);
  }, [content]);

  const handleSave = useCallback(async () => {
    if (!hasChanges) return;
    
    setIsSaving(true);
    setSaveMessage(null);
    
    try {
      const result = await onSave(editedContent);
      
      if (result.success) {
        const newSubVersion = result.sub_version ?? (currentSubVersion + 1);
        setCurrentSubVersion(newSubVersion);
        setHasChanges(false);
        setSaveMessage(`Saved as v${version}.${newSubVersion}`);
      }
    } catch (err) {
      setSaveMessage("Failed to save");
    } finally {
      setIsSaving(false);
    }
  }, [editedContent, hasChanges, onSave, version, currentSubVersion]);

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

  // Calculate next version string
  const nextSubVersion = currentSubVersion + 1;
  const versionDisplay = hasChanges 
    ? `v${version}.${nextSubVersion}` 
    : currentSubVersion > 0 
      ? `v${version}.${currentSubVersion}`
      : `v${version}`;

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
              Edit Markdown ({versionDisplay})
            </h2>
            {hasChanges && (
              <span className="chip chip--warning" style={{ fontSize: "0.75rem" }}>
                Unsaved changes
              </span>
            )}
            {saveMessage && (
              <span 
                className={saveMessage.includes("Failed") ? "chip chip--failed" : "chip chip--success"} 
                style={{ fontSize: "0.75rem" }}
              >
                {saveMessage}
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
              Save as v{version}.{nextSubVersion}
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
              Editor
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
              Preview
            </div>
            <div
              className="markdown-preview"
              style={{
                flex: 1,
                overflow: "auto",
                padding: "1rem",
                color: "#d1d5db",
                fontSize: "0.9rem",
                lineHeight: 1.7,
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {editedContent}
              </ReactMarkdown>
            </div>
          </div>
        </div>

        {/* Footer hint */}
        <div style={{ fontSize: "0.75rem", color: "#6b7280", display: "flex", justifyContent: "space-between", flexShrink: 0 }}>
          <span>
            Edit the markdown on the left. Preview updates in real-time on the right.
          </span>
          <span>
            Press Ctrl/Cmd+S to save | Esc to close
          </span>
        </div>
      </div>

      {/* Markdown preview styles */}
      <style jsx global>{`
        .markdown-preview h1 { font-size: 1.5em; font-weight: 600; margin: 1em 0 0.5em; color: #a78bfa; }
        .markdown-preview h2 { font-size: 1.3em; font-weight: 600; margin: 1em 0 0.5em; color: #60a5fa; }
        .markdown-preview h3 { font-size: 1.1em; font-weight: 600; margin: 1em 0 0.5em; color: #10b981; }
        .markdown-preview h4, .markdown-preview h5, .markdown-preview h6 { font-size: 1em; font-weight: 600; margin: 0.75em 0 0.5em; }
        .markdown-preview p { margin: 0.5em 0; }
        .markdown-preview ul, .markdown-preview ol { margin: 0.5em 0; padding-left: 1.5em; }
        .markdown-preview li { margin: 0.25em 0; }
        .markdown-preview strong { color: #f0f0f0; font-weight: 600; }
        .markdown-preview em { font-style: italic; }
        .markdown-preview code { 
          background: #1e1e2e; 
          padding: 0.15em 0.3em; 
          border-radius: 3px; 
          font-size: 0.9em; 
          font-family: 'JetBrains Mono', monospace;
        }
        .markdown-preview pre { 
          background: #1e1e2e; 
          padding: 0.75em; 
          border-radius: 4px; 
          overflow-x: auto; 
          margin: 0.5em 0;
        }
        .markdown-preview pre code { background: transparent; padding: 0; }
        .markdown-preview blockquote { 
          border-left: 3px solid #374151; 
          padding-left: 1em; 
          margin: 0.5em 0; 
          color: #9ca3af;
        }
        .markdown-preview hr { border: none; border-top: 1px solid #374151; margin: 1em 0; }
        .markdown-preview table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
        .markdown-preview th, .markdown-preview td { 
          border: 1px solid #374151; 
          padding: 0.5em; 
          text-align: left;
        }
        .markdown-preview th { background: #1f2937; font-weight: 600; }
        .markdown-preview a { color: #60a5fa; text-decoration: underline; }
        .markdown-preview a:hover { color: #93c5fd; }
      `}</style>
    </div>
  );
}

export default MarkdownEditorModal;
