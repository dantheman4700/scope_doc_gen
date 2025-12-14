"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { cn } from "@/lib/utils";
import { 
  Eye, 
  Edit3, 
  Save, 
  Loader2,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { EditSuggestion, AmbiguityHighlight } from "@/hooks/useRunChat";
import { CursorStyleDiff } from "./CursorStyleDiff";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AlertCircle } from "lucide-react";

/**
 * Component to render markdown with ambiguity highlights
 */
function HighlightedMarkdown({ 
  content, 
  highlights 
}: { 
  content: string; 
  highlights: AmbiguityHighlight[];
}) {
  // Build segments: alternating between normal text and highlighted text
  const segments = useMemo(() => {
    if (highlights.length === 0) {
      return [{ type: "text" as const, content }];
    }

    const result: Array<
      | { type: "text"; content: string }
      | { type: "highlight"; content: string; highlight: AmbiguityHighlight }
    > = [];
    
    let remaining = content;
    let lastIndex = 0;

    // Sort highlights by their position in the content
    const sortedHighlights = [...highlights].sort((a, b) => {
      const aIdx = content.indexOf(a.text);
      const bIdx = content.indexOf(b.text);
      return aIdx - bIdx;
    });

    for (const highlight of sortedHighlights) {
      const idx = remaining.indexOf(highlight.text);
      if (idx === -1) continue; // Text not found in remaining content

      // Add text before the highlight
      if (idx > 0) {
        result.push({ type: "text", content: remaining.slice(0, idx) });
      }

      // Add the highlighted segment
      result.push({ 
        type: "highlight", 
        content: highlight.text, 
        highlight 
      });

      // Update remaining
      remaining = remaining.slice(idx + highlight.text.length);
    }

    // Add any remaining text
    if (remaining) {
      result.push({ type: "text", content: remaining });
    }

    return result;
  }, [content, highlights]);

  return (
    <TooltipProvider>
      <div className="whitespace-pre-wrap">
        {segments.map((segment, idx) => {
          if (segment.type === "text") {
            return (
              <ReactMarkdown key={idx} remarkPlugins={[remarkGfm]}>
                {segment.content}
              </ReactMarkdown>
            );
          }

          // Highlighted segment with tooltip
          return (
            <Tooltip key={idx}>
              <TooltipTrigger asChild>
                <span className="bg-yellow-200 dark:bg-yellow-900/50 border-b-2 border-yellow-500 cursor-help px-0.5 rounded-sm inline">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Render inline to avoid block-level elements breaking the highlight
                      p: ({ children }) => <span>{children}</span>,
                    }}
                  >
                    {segment.content}
                  </ReactMarkdown>
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-sm">
                <div className="space-y-1">
                  <div className="flex items-center gap-1 font-medium text-yellow-700 dark:text-yellow-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    Ambiguity Detected
                  </div>
                  <p className="text-sm">{segment.highlight.concern}</p>
                  {segment.highlight.suggestion && (
                    <p className="text-xs text-muted-foreground italic">
                      Suggestion: {segment.highlight.suggestion}
                    </p>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}

interface MarkdownEditorProps {
  content: string;
  savedContent?: string; // The last saved/committed version for diff comparison
  stagedEdits?: EditSuggestion[]; // Currently staged edits
  onChange: (content: string) => void;
  onSave: () => void;
  isSaving?: boolean;
  pendingEdits?: EditSuggestion[];
  onApplyEdit?: (edit: EditSuggestion) => void;
  onRejectEdit?: (editId: string) => void;
  ambiguityHighlights?: AmbiguityHighlight[];
  className?: string;
  readOnly?: boolean;
}

export function MarkdownEditor({
  content,
  savedContent,
  stagedEdits = [],
  onChange,
  onSave,
  isSaving = false,
  pendingEdits = [],
  onApplyEdit,
  onRejectEdit,
  ambiguityHighlights = [],
  className,
  readOnly = false,
}: MarkdownEditorProps) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [localContent, setLocalContent] = useState(content);
  const [currentEditIndex, setCurrentEditIndex] = useState(0);
  
  // Compute hasChanges by comparing current content to saved
  const hasChanges = useMemo(() => {
    if (!savedContent) return localContent !== content;
    return localContent !== savedContent || stagedEdits.length > 0;
  }, [localContent, savedContent, content, stagedEdits]);

  // Filter for only pending edits
  const activePendingEdits = useMemo(() => {
    return pendingEdits.filter(e => e.status === "pending");
  }, [pendingEdits]);

  // Reset edit index when edits change
  useEffect(() => {
    if (currentEditIndex >= activePendingEdits.length) {
      setCurrentEditIndex(Math.max(0, activePendingEdits.length - 1));
    }
  }, [activePendingEdits.length, currentEditIndex]);

  // Sync content from props when it changes externally (e.g., version switch or staged edit applied)
  const isUserEditRef = React.useRef(false);
  
  useEffect(() => {
    if (!isUserEditRef.current) {
      setLocalContent(content);
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
  }, [onSave]);

  const handleRevert = useCallback(() => {
    const revertTo = savedContent || content;
    setLocalContent(revertTo);
    onChange(revertTo);
  }, [savedContent, content, onChange]);

  const handleAcceptEdit = useCallback((edit: EditSuggestion) => {
    onApplyEdit?.(edit);
    // Move to next edit if available
    if (currentEditIndex < activePendingEdits.length - 1) {
      setCurrentEditIndex(currentEditIndex + 1);
    }
  }, [onApplyEdit, currentEditIndex, activePendingEdits.length]);

  const handleRejectEdit = useCallback((editId: string) => {
    onRejectEdit?.(editId);
    // Stay on same index (next edit will shift into this position)
  }, [onRejectEdit]);

  // Pending edits count
  const pendingCount = activePendingEdits.length;
  const stagedCount = stagedEdits.length;

  return (
    <div className={cn("flex h-full flex-col", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-border">
            <Button
              variant={mode === "edit" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-none rounded-l-md border-r"
              onClick={() => setMode("edit")}
              disabled={readOnly}
            >
              <Edit3 className="mr-1 h-3.5 w-3.5" />
              Edit
            </Button>
            <Button
              variant={mode === "preview" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-none rounded-r-md"
              onClick={() => setMode("preview")}
            >
              <Eye className="mr-1 h-3.5 w-3.5" />
              Preview
            </Button>
          </div>
          
          {hasChanges && (
            <span className="text-xs text-muted-foreground">
              Unsaved changes
              {stagedCount > 0 && (
                <span className="ml-1 text-blue-600">
                  ({stagedCount} staged)
                </span>
              )}
            </span>
          )}

          {pendingCount > 0 && (
            <span className="text-xs text-purple-600 font-medium">
              {pendingCount} edit{pendingCount > 1 ? "s" : ""} pending
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

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {mode === "edit" ? (
          <div className="h-full relative">
            <Textarea
              value={localContent}
              onChange={(e) => handleContentChange(e.target.value)}
              className="h-full resize-none rounded-none border-0 font-mono text-sm focus-visible:ring-0"
              placeholder="Start typing..."
              disabled={readOnly}
            />
            {/* Show pending edits indicator in edit mode */}
            {pendingCount > 0 && (
              <div className="absolute bottom-4 right-4 bg-purple-600 text-white text-xs px-2 py-1 rounded-full shadow-lg">
                {pendingCount} pending - switch to Preview to review
              </div>
            )}
          </div>
        ) : pendingCount > 0 ? (
          // Use CursorStyleDiff when there are pending edits
          <CursorStyleDiff
            content={localContent}
            pendingEdits={activePendingEdits}
            currentEditIndex={currentEditIndex}
            onAccept={handleAcceptEdit}
            onReject={handleRejectEdit}
            onNavigate={setCurrentEditIndex}
            className="h-full"
          />
        ) : (
          // Regular markdown preview when no pending edits
          <div className="h-full overflow-y-auto p-6">
            <article className="prose dark:prose-invert mx-auto max-w-4xl prose-headings:mt-8 prose-headings:mb-4 prose-p:my-4 prose-li:my-1 prose-pre:my-4 prose-ul:my-4 prose-ol:my-4">
              {ambiguityHighlights.length > 0 ? (
                <HighlightedMarkdown 
                  content={localContent} 
                  highlights={ambiguityHighlights} 
                />
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {localContent}
                </ReactMarkdown>
              )}
            </article>
          </div>
        )}
      </div>
    </div>
  );
}
