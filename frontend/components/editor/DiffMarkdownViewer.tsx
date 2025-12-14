"use client";

import React, { useMemo } from "react";
import { diffWords, Change } from "diff";
import { cn } from "@/lib/utils";

interface DiffMarkdownViewerProps {
  originalContent: string;
  modifiedContent: string;
  className?: string;
}

/**
 * Renders a side-by-side or inline diff view between original and modified content.
 * Shows additions in green, deletions in red with strikethrough.
 */
export function DiffMarkdownViewer({
  originalContent,
  modifiedContent,
  className,
}: DiffMarkdownViewerProps) {
  const diffResult = useMemo(() => {
    return diffWords(originalContent, modifiedContent);
  }, [originalContent, modifiedContent]);

  // Count changes for summary
  const { additions, deletions } = useMemo(() => {
    let additions = 0;
    let deletions = 0;
    for (const part of diffResult) {
      if (part.added) {
        additions += part.value.length;
      } else if (part.removed) {
        deletions += part.value.length;
      }
    }
    return { additions, deletions };
  }, [diffResult]);

  const hasChanges = additions > 0 || deletions > 0;

  if (!hasChanges) {
    return (
      <div className={cn("p-4 text-sm text-muted-foreground", className)}>
        No changes to display
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Summary bar */}
      <div className="flex items-center gap-4 border-b border-border bg-muted/30 px-4 py-2 text-xs">
        <span className="font-medium">Changes:</span>
        {additions > 0 && (
          <span className="text-green-600 dark:text-green-400">
            +{additions} chars
          </span>
        )}
        {deletions > 0 && (
          <span className="text-red-600 dark:text-red-400">
            -{deletions} chars
          </span>
        )}
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
          {diffResult.map((part, index) => (
            <DiffPart key={index} part={part} />
          ))}
        </pre>
      </div>
    </div>
  );
}

function DiffPart({ part }: { part: Change }) {
  if (part.added) {
    return (
      <span className="bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200">
        {part.value}
      </span>
    );
  }

  if (part.removed) {
    return (
      <span className="bg-red-100 text-red-800 line-through dark:bg-red-900/50 dark:text-red-200">
        {part.value}
      </span>
    );
  }

  // Unchanged text
  return <span>{part.value}</span>;
}

/**
 * A more compact inline diff that highlights just the changed portions
 * within the context of the document.
 */
interface InlineDiffProps {
  originalContent: string;
  modifiedContent: string;
  showLineNumbers?: boolean;
  className?: string;
}

export function InlineDiffView({
  originalContent,
  modifiedContent,
  showLineNumbers = false,
  className,
}: InlineDiffProps) {
  const diffResult = useMemo(() => {
    return diffWords(originalContent, modifiedContent);
  }, [originalContent, modifiedContent]);

  // Split into lines for line-by-line rendering
  const lines = useMemo(() => {
    const result: Array<{ lineNum: number; parts: Change[] }> = [];
    let currentLine: Change[] = [];
    let lineNum = 1;

    for (const part of diffResult) {
      const segments = part.value.split("\n");
      
      for (let i = 0; i < segments.length; i++) {
        const segment = segments[i];
        
        if (segment || i === 0) {
          currentLine.push({
            value: segment,
            added: part.added,
            removed: part.removed,
            count: part.count,
          });
        }
        
        // If not the last segment, this is a line break
        if (i < segments.length - 1) {
          result.push({ lineNum, parts: currentLine });
          currentLine = [];
          lineNum++;
        }
      }
    }

    // Push final line
    if (currentLine.length > 0) {
      result.push({ lineNum, parts: currentLine });
    }

    return result;
  }, [diffResult]);

  return (
    <div className={cn("font-mono text-sm", className)}>
      {lines.map((line, idx) => {
        const hasAddition = line.parts.some(p => p.added);
        const hasDeletion = line.parts.some(p => p.removed);
        
        return (
          <div
            key={idx}
            className={cn(
              "flex",
              hasAddition && !hasDeletion && "bg-green-50 dark:bg-green-950/20",
              hasDeletion && !hasAddition && "bg-red-50 dark:bg-red-950/20",
              hasAddition && hasDeletion && "bg-yellow-50 dark:bg-yellow-950/20"
            )}
          >
            {showLineNumbers && (
              <span className="w-12 flex-shrink-0 select-none border-r border-border px-2 py-0.5 text-right text-xs text-muted-foreground">
                {line.lineNum}
              </span>
            )}
            <span className="flex-1 px-2 py-0.5 whitespace-pre-wrap">
              {line.parts.map((part, partIdx) => (
                <DiffPart key={partIdx} part={part} />
              ))}
            </span>
          </div>
        );
      })}
    </div>
  );
}
