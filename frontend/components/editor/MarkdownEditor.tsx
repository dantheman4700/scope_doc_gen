"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { cn } from "@/lib/utils";
import { 
  Eye, 
  Edit3, 
  Save, 
  Loader2,
  Check,
  X,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { EditSuggestion } from "@/hooks/useRunChat";

interface MarkdownEditorProps {
  content: string;
  onChange: (content: string) => void;
  onSave: () => void;
  isSaving?: boolean;
  pendingEdits?: EditSuggestion[];
  onApplyEdit?: (edit: EditSuggestion) => void;
  onRejectEdit?: (editId: string) => void;
  className?: string;
  readOnly?: boolean;
}

export function MarkdownEditor({
  content,
  onChange,
  onSave,
  isSaving = false,
  pendingEdits = [],
  onApplyEdit,
  onRejectEdit,
  className,
  readOnly = false,
}: MarkdownEditorProps) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [localContent, setLocalContent] = useState(content);
  // Track the "saved" version to compare against for hasChanges
  const [savedContent, setSavedContent] = useState(content);
  
  // Compute hasChanges by comparing local to saved
  const hasChanges = localContent !== savedContent;

  // Sync content from props when it changes externally (e.g., version switch)
  // We use a ref to track if this is a user edit or external update
  const isUserEditRef = React.useRef(false);
  
  useEffect(() => {
    // Only reset if this is an external content change (not from user typing)
    if (!isUserEditRef.current) {
      setLocalContent(content);
      setSavedContent(content);
    }
    isUserEditRef.current = false;
  }, [content]);

  const handleContentChange = useCallback((value: string) => {
    isUserEditRef.current = true;
    setLocalContent(value);
    onChange(value);
  }, [onChange]);

  const handleSave = useCallback(() => {
    onSave();
    // After saving, update savedContent to match current content
    setSavedContent(localContent);
  }, [onSave, localContent]);

  const handleRevert = useCallback(() => {
    setLocalContent(savedContent);
    onChange(savedContent);
  }, [savedContent, onChange]);

  // Highlight pending edits in the preview
  const highlightedContent = useMemo(() => {
    if (pendingEdits.length === 0) return localContent;
    
    let result = localContent;
    for (const edit of pendingEdits) {
      if (edit.status === "pending" && result.includes(edit.oldStr)) {
        // Wrap the old string in a highlight marker
        result = result.replace(
          edit.oldStr,
          `<mark class="bg-yellow-200 dark:bg-yellow-800">${edit.oldStr}</mark>`
        );
      }
    }
    return result;
  }, [localContent, pendingEdits]);

  // Pending edits banner
  const pendingCount = pendingEdits.filter(e => e.status === "pending").length;

  return (
    <div className={cn("flex h-full flex-col", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-border">
            <Button
              variant={mode === "edit" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-r-none border-r"
              onClick={() => setMode("edit")}
              disabled={readOnly}
            >
              <Edit3 className="mr-1 h-3.5 w-3.5" />
              Edit
            </Button>
            <Button
              variant={mode === "preview" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-l-none"
              onClick={() => setMode("preview")}
            >
              <Eye className="mr-1 h-3.5 w-3.5" />
              Preview
            </Button>
          </div>
          
          {hasChanges && (
            <span className="text-xs text-muted-foreground">
              Unsaved changes
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {hasChanges && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRevert}
              disabled={isSaving}
            >
              <Undo2 className="mr-1 h-3.5 w-3.5" />
              Revert
            </Button>
          )}
          <Button
            variant="default"
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1 h-3.5 w-3.5" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Pending Edits Banner */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between border-b border-yellow-500/50 bg-yellow-50 px-4 py-2 text-sm dark:bg-yellow-950/30">
          <span className="text-yellow-800 dark:text-yellow-200">
            {pendingCount} pending edit{pendingCount > 1 ? "s" : ""} to review
          </span>
          <div className="flex gap-2">
            {pendingEdits.filter(e => e.status === "pending").map(edit => (
              <div key={edit.id} className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-xs text-green-600 hover:text-green-700"
                  onClick={() => onApplyEdit?.(edit)}
                >
                  <Check className="mr-1 h-3 w-3" />
                  Apply
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-xs text-red-600 hover:text-red-700"
                  onClick={() => onRejectEdit?.(edit.id)}
                >
                  <X className="mr-1 h-3 w-3" />
                  Reject
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {mode === "edit" ? (
          <Textarea
            value={localContent}
            onChange={(e) => handleContentChange(e.target.value)}
            className="h-full resize-none rounded-none border-0 font-mono text-sm focus-visible:ring-0"
            placeholder="Start typing..."
            disabled={readOnly}
          />
        ) : (
          <div className="h-full overflow-y-auto p-6">
            <article className="prose dark:prose-invert mx-auto max-w-4xl prose-headings:mt-8 prose-headings:mb-4 prose-p:my-4 prose-li:my-1 prose-pre:my-4 prose-ul:my-4 prose-ol:my-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {localContent}
              </ReactMarkdown>
            </article>
          </div>
        )}
      </div>
    </div>
  );
}
