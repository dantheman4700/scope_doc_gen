"use client";

import { useState, useCallback } from "react";
import { Edit, Eye, Save, Copy, X, Loader2 } from "lucide-react";

interface MarkdownEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  content: string;
  version: number;
  runId: string;
  onSave: (content: string) => Promise<boolean>;
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
  const [editMode, setEditMode] = useState(false);
  const [editedContent, setEditedContent] = useState(content);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

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
      setEditMode(false);
    }
  }, [editedContent, hasChanges, onSave]);

  const handleToggleEdit = useCallback(() => {
    if (editMode && hasChanges) {
      // Prompt before discarding changes
      if (!confirm("You have unsaved changes. Discard them?")) {
        return;
      }
      setEditedContent(content);
      setHasChanges(false);
    }
    setEditMode(!editMode);
  }, [editMode, hasChanges, content]);

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
        background: "rgba(0,0,0,0.7)",
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
          maxWidth: "1000px",
          width: "100%",
          maxHeight: "95vh",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          padding: "1.25rem",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h2 style={{ margin: 0 }}>
              {editMode ? "Edit Markdown" : "Markdown Preview"} (v{version})
            </h2>
            {hasChanges && (
              <span className="chip chip--warning" style={{ fontSize: "0.75rem" }}>
                Unsaved changes
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {/* Mode toggle */}
            <button
              className={`btn-secondary ${editMode ? "" : "btn-active"}`}
              type="button"
              onClick={handleToggleEdit}
              title={editMode ? "Switch to preview" : "Switch to edit mode"}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}
            >
              {editMode ? <Eye className="h-4 w-4" /> : <Edit className="h-4 w-4" />}
              {editMode ? "Preview" : "Edit"}
            </button>
            
            {/* Save button - only in edit mode */}
            {editMode && (
              <button
                className="btn-primary"
                type="button"
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}
              >
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save
              </button>
            )}
            
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

        {/* Content area */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflow: "hidden",
            borderRadius: "0.5rem",
            border: "1px solid #374151",
            background: "#0f0f1a",
          }}
        >
          {editMode ? (
            <textarea
              value={editedContent}
              onChange={(e) => handleContentChange(e.target.value)}
              style={{
                width: "100%",
                height: "100%",
                minHeight: "60vh",
                padding: "1rem",
                background: "transparent",
                border: "none",
                color: "#e5e7eb",
                fontSize: "0.875rem",
                fontFamily: "monospace",
                lineHeight: 1.6,
                resize: "none",
                outline: "none",
              }}
              spellCheck={false}
            />
          ) : (
            <div style={{ height: "100%", overflow: "auto", padding: "1rem" }}>
              <pre
                style={{
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontSize: "0.875rem",
                  lineHeight: 1.6,
                  color: "#e5e7eb",
                  fontFamily: "monospace",
                }}
              >
                {editMode ? editedContent : content}
              </pre>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div style={{ fontSize: "0.75rem", color: "#6b7280", display: "flex", justifyContent: "space-between" }}>
          <span>
            {editMode
              ? "Edit the markdown directly. Changes will be saved as a sub-version."
              : "Click Edit to make changes to this document."}
          </span>
          {editMode && (
            <span>
              Press Ctrl+S to save (coming soon)
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default MarkdownEditorModal;

