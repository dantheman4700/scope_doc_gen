"use client";

import React, { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { 
  Send, 
  Loader2, 
  Check, 
  X, 
  Sparkles,
  AlertCircle,
  Trash2,
  Search,
  Calculator,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { ChatMessage, EditSuggestion, ToolCall } from "@/hooks/useRunChat";
import ReactMarkdown from "react-markdown";

interface ChatSidebarProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  pendingEdits: EditSuggestion[];
  onSendMessage: (message: string) => void;
  onApplyEdit: (edit: EditSuggestion) => void;
  onRejectEdit: (editId: string) => void;
  onClearMessages: () => void;
  className?: string;
}

function EditSuggestionCard({
  edit,
  onApply,
  onReject,
}: {
  edit: EditSuggestion;
  onApply: () => void;
  onReject: () => void;
}) {
  const isPending = edit.status === "pending";
  
  return (
    <div className={cn(
      "rounded-md border p-3 text-xs",
      isPending && "border-blue-500/50 bg-blue-50 dark:bg-blue-950/30",
      edit.status === "applied" && "border-green-500/50 bg-green-50 dark:bg-green-950/30",
      edit.status === "rejected" && "border-red-500/50 bg-red-50 dark:bg-red-950/30 opacity-60",
    )}>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium text-muted-foreground">Suggested Edit</span>
        {isPending && (
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0 text-green-600 hover:text-green-700"
              onClick={onApply}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0 text-red-600 hover:text-red-700"
              onClick={onReject}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        {edit.status === "applied" && (
          <span className="text-green-600">Applied</span>
        )}
        {edit.status === "rejected" && (
          <span className="text-red-600">Rejected</span>
        )}
      </div>
      
      <div className="space-y-2">
        <div>
          <span className="text-muted-foreground">Remove:</span>
          <pre className="mt-1 overflow-x-auto rounded bg-red-100 p-2 text-red-800 dark:bg-red-900/50 dark:text-red-200">
            {edit.oldStr.length > 100 ? edit.oldStr.slice(0, 100) + "..." : edit.oldStr}
          </pre>
        </div>
        <div>
          <span className="text-muted-foreground">Insert:</span>
          <pre className="mt-1 overflow-x-auto rounded bg-green-100 p-2 text-green-800 dark:bg-green-900/50 dark:text-green-200">
            {edit.newStr.length > 100 ? edit.newStr.slice(0, 100) + "..." : edit.newStr}
          </pre>
        </div>
        {edit.reason && (
          <div className="text-muted-foreground italic">
            {edit.reason}
          </div>
        )}
      </div>
    </div>
  );
}

function MessageContent({ message, pendingEdits, onApplyEdit, onRejectEdit }: {
  message: ChatMessage;
  pendingEdits: EditSuggestion[];
  onApplyEdit: (edit: EditSuggestion) => void;
  onRejectEdit: (editId: string) => void;
}) {
  const editCalls = message.toolCalls?.filter(tc => tc.name === "str_replace_edit") || [];
  const ambiguityCalls = message.toolCalls?.filter(tc => tc.name === "highlight_ambiguity") || [];
  const researchCalls = message.toolCalls?.filter(tc => tc.name === "deep_research") || [];
  const calculatorCalls = message.toolCalls?.filter(tc => tc.name === "calculate") || [];
  
  return (
    <div className="space-y-2">
      {/* Research indicators */}
      {researchCalls.map(tc => (
        <div key={tc.id} className="rounded-md border border-blue-500/50 bg-blue-50 p-3 text-xs dark:bg-blue-950/30">
          <div className="flex items-center gap-2">
            <Search className={cn(
              "h-4 w-4 text-blue-600",
              tc.status === "pending" && "animate-pulse"
            )} />
            <div className="flex-1">
              <span className="font-medium text-blue-700 dark:text-blue-400">
                {tc.status === "pending" ? "Researching..." : "Research Complete"}
              </span>
              <p className="text-blue-600 dark:text-blue-300 mt-0.5">
                {(tc.input as { query?: string }).query}
              </p>
            </div>
            {tc.status === "pending" && (
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            )}
          </div>
        </div>
      ))}

      {/* Calculator indicators */}
      {calculatorCalls.map(tc => {
        const input = tc.input as { expression?: string; description?: string; result?: number | string };
        return (
          <div key={tc.id} className="rounded-md border border-purple-500/50 bg-purple-50 p-3 text-xs dark:bg-purple-950/30">
            <div className="flex items-center gap-2">
              <Calculator className="h-4 w-4 text-purple-600" />
              <div className="flex-1">
                <span className="font-medium text-purple-700 dark:text-purple-400">
                  Calculation
                </span>
                <p className="text-purple-600 dark:text-purple-300 font-mono mt-0.5">
                  {input.expression}
                  {input.result !== undefined && (
                    <span className="ml-2 font-bold">= {input.result}</span>
                  )}
                </p>
                {input.description && (
                  <p className="text-muted-foreground italic mt-1">
                    {input.description}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {message.content && (
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      )}
      
      {/* Edit suggestions */}
      {editCalls.map(tc => {
        const edit = pendingEdits.find(e => e.id === tc.id);
        if (!edit) return null;
        return (
          <EditSuggestionCard
            key={tc.id}
            edit={edit}
            onApply={() => onApplyEdit(edit)}
            onReject={() => onRejectEdit(edit.id)}
          />
        );
      })}
      
      {/* Ambiguity highlights */}
      {ambiguityCalls.map(tc => (
        <div key={tc.id} className="rounded-md border border-yellow-500/50 bg-yellow-50 p-3 text-xs dark:bg-yellow-950/30">
          <div className="mb-1 flex items-center gap-1 font-medium text-yellow-700 dark:text-yellow-400">
            <AlertCircle className="h-3.5 w-3.5" />
            Ambiguity Detected
          </div>
          <p className="text-yellow-800 dark:text-yellow-200">
            {(tc.input as { concern?: string }).concern}
          </p>
          {(tc.input as { suggestion?: string }).suggestion && (
            <p className="mt-1 text-muted-foreground italic">
              Suggestion: {(tc.input as { suggestion?: string }).suggestion}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export function ChatSidebar({
  messages,
  isStreaming,
  error,
  pendingEdits,
  onSendMessage,
  onApplyEdit,
  onRejectEdit,
  onClearMessages,
  className,
}: ChatSidebarProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    
    onSendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className={cn("flex h-full flex-col", className)}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
            <Sparkles className="mb-3 h-8 w-8 text-purple-500" />
            <p className="mb-1 font-medium">AI Document Assistant</p>
            <p className="text-xs">
              Ask questions about the document or request edits.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map(message => (
              <div
                key={message.id}
                className={cn(
                  "rounded-lg p-3",
                  message.role === "user" 
                    ? "ml-4 bg-primary text-primary-foreground" 
                    : "mr-4 bg-muted"
                )}
              >
                <MessageContent
                  message={message}
                  pendingEdits={pendingEdits}
                  onApplyEdit={onApplyEdit}
                  onRejectEdit={onRejectEdit}
                />
              </div>
            ))}
            {isStreaming && messages[messages.length - 1]?.role === "assistant" && !messages[messages.length - 1]?.content && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-3 mb-2 rounded-md border border-red-500/50 bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950/30 dark:text-red-400">
          <div className="flex items-center gap-1">
            <AlertCircle className="h-3.5 w-3.5" />
            {error}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border p-3">
        {messages.length > 0 && (
          <div className="mb-2 flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-muted-foreground"
              onClick={onClearMessages}
            >
              <Trash2 className="mr-1 h-3 w-3" />
              Clear
            </Button>
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the document or request edits..."
            className="min-h-[60px] resize-none text-sm"
            disabled={isStreaming}
          />
          <Button
            type="submit"
            size="icon"
            className="shrink-0"
            disabled={!input.trim() || isStreaming}
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
