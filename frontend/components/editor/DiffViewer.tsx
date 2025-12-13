"use client";

import React, { useMemo } from "react";
import { cn } from "@/lib/utils";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { EditSuggestion } from "@/hooks/useRunChat";

interface DiffLine {
  type: "unchanged" | "removed" | "added";
  content: string;
  lineNumber: number;
}

interface DiffViewerProps {
  original: string;
  modified: string;
  pendingEdits?: EditSuggestion[];
  onApplyEdit?: (edit: EditSuggestion) => void;
  onRejectEdit?: (editId: string) => void;
  className?: string;
}

function computeDiff(original: string, modified: string): DiffLine[] {
  const originalLines = original.split("\n");
  const modifiedLines = modified.split("\n");
  const result: DiffLine[] = [];
  
  let i = 0;
  let j = 0;
  let lineNum = 1;
  
  // Simple diff algorithm - for production, use a proper diff library
  while (i < originalLines.length || j < modifiedLines.length) {
    if (i >= originalLines.length) {
      // Remaining lines are additions
      result.push({
        type: "added",
        content: modifiedLines[j],
        lineNumber: lineNum++,
      });
      j++;
    } else if (j >= modifiedLines.length) {
      // Remaining lines are removals
      result.push({
        type: "removed",
        content: originalLines[i],
        lineNumber: lineNum++,
      });
      i++;
    } else if (originalLines[i] === modifiedLines[j]) {
      // Lines match
      result.push({
        type: "unchanged",
        content: originalLines[i],
        lineNumber: lineNum++,
      });
      i++;
      j++;
    } else {
      // Lines differ - check if it's a modification
      // Look ahead to see if original line appears later in modified
      let foundInModified = -1;
      for (let k = j + 1; k < Math.min(j + 5, modifiedLines.length); k++) {
        if (modifiedLines[k] === originalLines[i]) {
          foundInModified = k;
          break;
        }
      }
      
      if (foundInModified > 0) {
        // Lines before foundInModified are additions
        while (j < foundInModified) {
          result.push({
            type: "added",
            content: modifiedLines[j],
            lineNumber: lineNum++,
          });
          j++;
        }
      } else {
        // Check if modified line appears later in original
        let foundInOriginal = -1;
        for (let k = i + 1; k < Math.min(i + 5, originalLines.length); k++) {
          if (originalLines[k] === modifiedLines[j]) {
            foundInOriginal = k;
            break;
          }
        }
        
        if (foundInOriginal > 0) {
          // Lines before foundInOriginal are removals
          while (i < foundInOriginal) {
            result.push({
              type: "removed",
              content: originalLines[i],
              lineNumber: lineNum++,
            });
            i++;
          }
        } else {
          // Simple replacement
          result.push({
            type: "removed",
            content: originalLines[i],
            lineNumber: lineNum++,
          });
          result.push({
            type: "added",
            content: modifiedLines[j],
            lineNumber: lineNum++,
          });
          i++;
          j++;
        }
      }
    }
  }
  
  return result;
}

export function DiffViewer({
  original,
  modified,
  pendingEdits = [],
  onApplyEdit,
  onRejectEdit,
  className,
}: DiffViewerProps) {
  const diffLines = useMemo(() => computeDiff(original, modified), [original, modified]);
  
  const hasChanges = diffLines.some(line => line.type !== "unchanged");
  const pendingEdit = pendingEdits.find(e => e.status === "pending");
  
  return (
    <div className={cn("flex flex-col", className)}>
      {/* Header with actions */}
      {hasChanges && pendingEdit && (
        <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2">
          <span className="text-sm text-muted-foreground">
            Suggested changes
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-green-600 hover:bg-green-50 hover:text-green-700"
              onClick={() => onApplyEdit?.(pendingEdit)}
            >
              <Check className="mr-1 h-3.5 w-3.5" />
              Accept
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-red-600 hover:bg-red-50 hover:text-red-700"
              onClick={() => onRejectEdit?.(pendingEdit.id)}
            >
              <X className="mr-1 h-3.5 w-3.5" />
              Reject
            </Button>
          </div>
        </div>
      )}
      
      {/* Diff content */}
      <div className="overflow-auto">
        <pre className="text-sm">
          {diffLines.map((line, idx) => (
            <div
              key={idx}
              className={cn(
                "px-4 py-0.5 font-mono",
                line.type === "removed" && "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-200",
                line.type === "added" && "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-200",
              )}
            >
              <span className="mr-4 inline-block w-8 select-none text-right text-muted-foreground">
                {line.type === "removed" ? "-" : line.type === "added" ? "+" : " "}
              </span>
              {line.content}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

// Inline diff component for use within the editor
interface InlineDiffProps {
  oldText: string;
  newText: string;
  onAccept?: () => void;
  onReject?: () => void;
  className?: string;
}

export function InlineDiff({
  oldText,
  newText,
  onAccept,
  onReject,
  className,
}: InlineDiffProps) {
  return (
    <span className={cn("relative inline", className)}>
      {/* Removed text */}
      <span className="rounded bg-red-200 px-1 line-through dark:bg-red-900/50">
        {oldText}
      </span>
      {/* Arrow */}
      <span className="mx-1 text-muted-foreground">→</span>
      {/* Added text */}
      <span className="rounded bg-green-200 px-1 dark:bg-green-900/50">
        {newText}
      </span>
      {/* Actions */}
      {(onAccept || onReject) && (
        <span className="ml-2 inline-flex gap-1">
          {onAccept && (
            <button
              onClick={onAccept}
              className="rounded p-0.5 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/50"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
          )}
          {onReject && (
            <button
              onClick={onReject}
              className="rounded p-0.5 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/50"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </span>
      )}
    </span>
  );
}
