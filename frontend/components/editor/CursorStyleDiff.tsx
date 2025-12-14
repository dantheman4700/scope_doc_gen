"use client";

import React, { useMemo, useRef, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Check, X, ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { EditSuggestion } from "@/hooks/useRunChat";

interface CursorStyleDiffProps {
  content: string;
  pendingEdits: EditSuggestion[];
  currentEditIndex: number;
  onAccept: (edit: EditSuggestion) => void;
  onReject: (editId: string) => void;
  onNavigate: (index: number) => void;
  className?: string;
}

interface ContentSegment {
  type: "text" | "edit";
  content: string;
  edit?: EditSuggestion;
  editIndex?: number;
}

/**
 * Inline edit marker component shown within the rendered markdown
 */
function EditMarker({
  edit,
  editIndex,
  isHighlighted,
  onAccept,
  onReject,
  editRef,
}: {
  edit: EditSuggestion;
  editIndex: number;
  isHighlighted: boolean;
  onAccept: (edit: EditSuggestion) => void;
  onReject: (editId: string) => void;
  editRef: (el: HTMLDivElement | null) => void;
}) {
  return (
    <div
      ref={editRef}
      className={cn(
        "my-2 rounded-lg border-2 p-3",
        isHighlighted 
          ? "border-purple-500 bg-purple-50 dark:bg-purple-950/30 shadow-lg" 
          : "border-border bg-muted/30"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-2">
          {/* Original text (to be removed) */}
          <div>
            <div className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">
              Remove:
            </div>
            <div className="bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 p-2 rounded text-sm line-through">
              <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm dark:prose-invert max-w-none [&>*]:m-0">
                {edit.oldStr}
              </ReactMarkdown>
            </div>
          </div>
          
          {/* New text (to be inserted) */}
          <div>
            <div className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">
              Insert:
            </div>
            <div className="bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 p-2 rounded text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm dark:prose-invert max-w-none [&>*]:m-0">
                {edit.newStr}
              </ReactMarkdown>
            </div>
          </div>
          
          {edit.reason && (
            <div className="text-xs text-muted-foreground italic pt-1">
              Reason: {edit.reason}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1">
          <Button
            size="sm"
            variant="default"
            className="h-8 w-8 p-0 bg-green-600 hover:bg-green-700"
            onClick={() => onAccept(edit)}
            title="Accept change"
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="h-8 w-8 p-0"
            onClick={() => onReject(edit.id)}
            title="Reject change"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * Cursor-style inline diff viewer
 * Shows pending edits inline with rendered markdown content
 */
export function CursorStyleDiff({
  content,
  pendingEdits,
  currentEditIndex,
  onAccept,
  onReject,
  onNavigate,
  className,
}: CursorStyleDiffProps) {
  const editRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [highlightedEdit, setHighlightedEdit] = useState<number>(currentEditIndex);

  // Scroll to current edit when it changes
  useEffect(() => {
    const editEl = editRefs.current.get(currentEditIndex);
    if (editEl) {
      editEl.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedEdit(currentEditIndex);
    }
  }, [currentEditIndex]);

  // Parse content and insert edit markers
  const segments = useMemo((): ContentSegment[] => {
    if (pendingEdits.length === 0) {
      return [{ type: "text", content }];
    }

    const result: ContentSegment[] = [];
    let remainingContent = content;

    // Sort edits by their position in the content
    const sortedEdits = [...pendingEdits]
      .map((edit, idx) => ({ edit, originalIndex: idx }))
      .sort((a, b) => {
        const posA = content.indexOf(a.edit.oldStr);
        const posB = content.indexOf(b.edit.oldStr);
        return posA - posB;
      });

    for (const { edit, originalIndex } of sortedEdits) {
      const editPos = remainingContent.indexOf(edit.oldStr);
      
      if (editPos === -1) {
        // Edit not found in remaining content, skip
        continue;
      }

      // Add text before this edit
      if (editPos > 0) {
        result.push({
          type: "text",
          content: remainingContent.slice(0, editPos),
        });
      }

      // Add the edit block
      result.push({
        type: "edit",
        content: edit.oldStr,
        edit,
        editIndex: originalIndex,
      });

      // Update remaining content
      remainingContent = remainingContent.slice(editPos + edit.oldStr.length);
    }

    // Add any remaining text after all edits
    if (remainingContent) {
      result.push({
        type: "text",
        content: remainingContent,
      });
    }

    return result;
  }, [content, pendingEdits]);

  const totalEdits = pendingEdits.length;

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Navigation bar */}
      {totalEdits > 0 && (
        <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-purple-600">
              {totalEdits} pending edit{totalEdits > 1 ? "s" : ""}
            </span>
            {totalEdits > 1 && (
              <span className="text-xs text-muted-foreground">
                (Edit {currentEditIndex + 1} of {totalEdits})
              </span>
            )}
          </div>
          
          {totalEdits > 1 && (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => onNavigate(Math.max(0, currentEditIndex - 1))}
                disabled={currentEditIndex === 0}
              >
                <ChevronUp className="h-4 w-4" />
                <span className="ml-1 text-xs">Prev</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => onNavigate(Math.min(totalEdits - 1, currentEditIndex + 1))}
                disabled={currentEditIndex === totalEdits - 1}
              >
                <span className="mr-1 text-xs">Next</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Content with inline edits - rendered as markdown */}
      <div className="flex-1 overflow-y-auto p-6">
        <article className="prose dark:prose-invert mx-auto max-w-4xl prose-headings:mt-6 prose-headings:mb-4 prose-p:my-3 prose-li:my-1">
          {segments.map((segment, idx) => {
            if (segment.type === "text") {
              // Render text segments as markdown
              return (
                <ReactMarkdown 
                  key={idx} 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Ensure block elements are rendered properly
                    p: ({ children }) => <p className="my-3">{children}</p>,
                    h1: ({ children }) => <h1 className="mt-6 mb-4">{children}</h1>,
                    h2: ({ children }) => <h2 className="mt-6 mb-4">{children}</h2>,
                    h3: ({ children }) => <h3 className="mt-5 mb-3">{children}</h3>,
                    ul: ({ children }) => <ul className="my-3">{children}</ul>,
                    ol: ({ children }) => <ol className="my-3">{children}</ol>,
                  }}
                >
                  {segment.content}
                </ReactMarkdown>
              );
            }

            // Render edit blocks as inline diff panels
            const edit = segment.edit!;
            const editIdx = segment.editIndex!;
            const isHighlighted = editIdx === highlightedEdit;

            return (
              <EditMarker
                key={idx}
                edit={edit}
                editIndex={editIdx}
                isHighlighted={isHighlighted}
                onAccept={onAccept}
                onReject={onReject}
                editRef={(el) => {
                  if (el) editRefs.current.set(editIdx, el);
                }}
              />
            );
          })}
        </article>
      </div>

      {/* Quick actions bar */}
      {totalEdits > 0 && (
        <div className="flex items-center justify-end gap-2 border-t border-border bg-muted/30 px-4 py-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              // Reject all edits
              pendingEdits.forEach(edit => onReject(edit.id));
            }}
            className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950"
          >
            <X className="mr-1 h-4 w-4" />
            Reject All
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => {
              // Accept all edits
              pendingEdits.forEach(edit => onAccept(edit));
            }}
            className="bg-green-600 hover:bg-green-700"
          >
            <Check className="mr-1 h-4 w-4" />
            Accept All
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * A simpler inline diff block for use in chat messages or elsewhere
 */
export function InlineEditBlock({
  edit,
  onAccept,
  onReject,
  compact = false,
}: {
  edit: EditSuggestion;
  onAccept: () => void;
  onReject: () => void;
  compact?: boolean;
}) {
  const isPending = edit.status === "pending";

  return (
    <div
      className={cn(
        "rounded-md border p-2",
        isPending && "border-purple-500/50 bg-purple-50/50 dark:bg-purple-950/20",
        edit.status === "applied" && "border-green-500/50 bg-green-50/50 dark:bg-green-950/20",
        edit.status === "staged" && "border-blue-500/50 bg-blue-50/50 dark:bg-blue-950/20",
        edit.status === "rejected" && "border-red-500/50 bg-red-50/50 dark:bg-red-950/20 opacity-60"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* Old text */}
          <div className="text-xs text-muted-foreground mb-1">Remove:</div>
          <pre className={cn(
            "text-xs bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 p-1.5 rounded overflow-x-auto whitespace-pre-wrap",
            compact ? "max-h-12" : "max-h-24"
          )}>
            {compact && edit.oldStr.length > 50 
              ? edit.oldStr.slice(0, 50) + "..." 
              : edit.oldStr}
          </pre>
          
          {/* New text */}
          <div className="text-xs text-muted-foreground mt-2 mb-1">Insert:</div>
          <pre className={cn(
            "text-xs bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 p-1.5 rounded overflow-x-auto whitespace-pre-wrap",
            compact ? "max-h-12" : "max-h-24"
          )}>
            {compact && edit.newStr.length > 50 
              ? edit.newStr.slice(0, 50) + "..." 
              : edit.newStr}
          </pre>

          {edit.reason && (
            <div className="text-xs text-muted-foreground mt-2 italic">
              {edit.reason}
            </div>
          )}
        </div>

        {/* Actions */}
        {isPending && (
          <div className="flex flex-col gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0 text-green-600 hover:bg-green-100 hover:text-green-700"
              onClick={onAccept}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0 text-red-600 hover:bg-red-100 hover:text-red-700"
              onClick={onReject}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {edit.status === "applied" && (
          <span className="text-xs text-green-600 font-medium">Applied</span>
        )}
        {edit.status === "staged" && (
          <span className="text-xs text-blue-600 font-medium">Staged</span>
        )}
        {edit.status === "rejected" && (
          <span className="text-xs text-red-600 font-medium">Rejected</span>
        )}
      </div>
    </div>
  );
}
