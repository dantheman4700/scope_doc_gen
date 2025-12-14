"use client";

import { useState, useCallback, useRef, useMemo, useEffect } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  timestamp: Date;
}

export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
  status: "pending" | "applied" | "rejected";
  result?: string;
}

export interface EditSuggestion {
  id: string;
  oldStr: string;
  newStr: string;
  reason?: string;
  status: "pending" | "staged" | "applied" | "rejected";
}

export interface AmbiguityHighlight {
  id: string;
  text: string;
  concern: string;
  suggestion?: string;
}

interface UseRunChatOptions {
  runId: string;
  documentContent: string;
  version?: number;
  onEditSuggestion?: (edit: EditSuggestion) => void;
  onDocumentUpdate?: (newContent: string) => void;
}

interface UseRunChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  pendingEdits: EditSuggestion[];
  stagedEdits: EditSuggestion[];
  stagedContent: string;
  ambiguityHighlights: AmbiguityHighlight[];
  sendMessage: (message: string) => Promise<void>;
  stageEdit: (edit: EditSuggestion) => void;
  unstageEdit: (editId: string) => void;
  rejectEdit: (editId: string) => void;
  clearStagedEdits: () => void;
  commitStagedEdits: () => void;
  clearMessages: () => void;
  // Legacy - for backward compatibility
  applyEdit: (edit: EditSuggestion) => Promise<boolean>;
}

/**
 * Apply a single edit to document content
 */
function applyEditToContent(content: string, oldStr: string, newStr: string): string {
  if (!content.includes(oldStr)) {
    return content;
  }
  return content.replace(oldStr, newStr);
}

/**
 * Apply all staged edits sequentially to produce the staged content
 */
function applyAllEdits(baseContent: string, edits: EditSuggestion[]): string {
  let result = baseContent;
  for (const edit of edits) {
    result = applyEditToContent(result, edit.oldStr, edit.newStr);
  }
  return result;
}

// Storage key for localStorage
const CHAT_STORAGE_KEY = (runId: string) => `scope-chat-${runId}`;

// Serializable version of ChatMessage (Date -> string)
interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  timestamp: string;
}

interface StoredChatState {
  messages: StoredChatMessage[];
  pendingEdits: EditSuggestion[];
}

export function useRunChat({
  runId,
  documentContent,
  version,
  onEditSuggestion,
  onDocumentUpdate,
}: UseRunChatOptions): UseRunChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingEdits, setPendingEdits] = useState<EditSuggestion[]>([]);
  const [stagedEdits, setStagedEdits] = useState<EditSuggestion[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentDocRef = useRef(documentContent);
  
  // Keep doc ref updated
  currentDocRef.current = documentContent;

  // Load chat state from localStorage on mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    
    try {
      const stored = localStorage.getItem(CHAT_STORAGE_KEY(runId));
      if (stored) {
        const parsed: StoredChatState = JSON.parse(stored);
        
        // Convert stored messages back to ChatMessage (string -> Date)
        const restoredMessages: ChatMessage[] = parsed.messages.map(m => ({
          ...m,
          timestamp: new Date(m.timestamp),
        }));
        
        setMessages(restoredMessages);
        setPendingEdits(parsed.pendingEdits || []);
      }
    } catch (err) {
      console.error("Failed to load chat state from localStorage:", err);
    }
    
    setIsInitialized(true);
  }, [runId]);

  // Save chat state to localStorage when messages change
  useEffect(() => {
    if (typeof window === "undefined" || !isInitialized) return;
    
    try {
      const toStore: StoredChatState = {
        messages: messages.map(m => ({
          ...m,
          timestamp: m.timestamp.toISOString(),
        })),
        pendingEdits,
      };
      
      localStorage.setItem(CHAT_STORAGE_KEY(runId), JSON.stringify(toStore));
    } catch (err) {
      console.error("Failed to save chat state to localStorage:", err);
    }
  }, [runId, messages, pendingEdits, isInitialized]);

  // Compute staged content by applying all staged edits to the document
  const stagedContent = useMemo(() => {
    if (stagedEdits.length === 0) return documentContent;
    return applyAllEdits(documentContent, stagedEdits);
  }, [documentContent, stagedEdits]);

  // Extract ambiguity highlights from all messages
  const ambiguityHighlights = useMemo<AmbiguityHighlight[]>(() => {
    const highlights: AmbiguityHighlight[] = [];
    for (const message of messages) {
      if (!message.toolCalls) continue;
      for (const tc of message.toolCalls) {
        if (tc.name === "highlight_ambiguity" && tc.input) {
          const input = tc.input as { text?: string; concern?: string; suggestion?: string };
          if (input.text && input.concern) {
            highlights.push({
              id: tc.id,
              text: input.text,
              concern: input.concern,
              suggestion: input.suggestion,
            });
          }
        }
      }
    }
    return highlights;
  }, [messages]);

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim()) return;
    
    setError(null);
    setIsStreaming(true);
    
    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    // Prepare assistant message placeholder
    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      toolCalls: [],
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, assistantMessage]);
    
    // Create abort controller
    abortControllerRef.current = new AbortController();
    
    try {
      // Build conversation history (exclude the placeholder)
      // Filter out messages with empty content to avoid Anthropic API errors
      const history = messages
        .filter(m => m.content && m.content.trim().length > 0)
        .map(m => ({
          role: m.role,
          content: m.content,
        }));
      
      // Send the staged content (with applied edits) to the AI
      const contentToSend = stagedEdits.length > 0 
        ? applyAllEdits(currentDocRef.current, stagedEdits)
        : currentDocRef.current;
      
      const response = await fetch(`/api/runs/${runId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversation_history: history,
          document_content: contentToSend,
          version,
          enable_web_search: false,
          use_perplexity: false,
        }),
        signal: abortControllerRef.current.signal,
      });
      
      if (!response.ok) {
        throw new Error(`Chat request failed: ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }
      
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Parse SSE events
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // Event type line - next data line will have the payload
            continue;
          }
          
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              
              if (data.content) {
                // Text delta
                setMessages(prev => prev.map(m => 
                  m.id === assistantId 
                    ? { ...m, content: m.content + data.content }
                    : m
                ));
              }
              
              if (data.name === "str_replace_edit" && data.input) {
                // Edit suggestion from AI
                const edit: EditSuggestion = {
                  id: data.id || `edit-${Date.now()}`,
                  oldStr: data.input.old_str || "",
                  newStr: data.input.new_str || "",
                  reason: data.input.reason,
                  status: "pending",
                };
                setPendingEdits(prev => [...prev, edit]);
                onEditSuggestion?.(edit);
                
                // Add tool call to message
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: edit.id,
                          name: "str_replace_edit",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }
              
              if (data.name === "highlight_ambiguity" && data.input) {
                // Ambiguity highlight
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: data.id || `ambig-${Date.now()}`,
                          name: "highlight_ambiguity",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }

              if (data.name === "deep_research" && data.input) {
                // Deep research tool call - show indicator in chat
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: data.id || `research-${Date.now()}`,
                          name: "deep_research",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }

              if (data.name === "calculate" && data.input) {
                // Calculator tool call
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: data.id || `calc-${Date.now()}`,
                          name: "calculate",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }
              
              if (data.name === "read_document" && data.input) {
                // Read document tool call
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: data.id || `read-${Date.now()}`,
                          name: "read_document",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }

              if (data.name === "search_workspace" && data.input) {
                // Workspace search tool call
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), {
                          id: data.id || `search-${Date.now()}`,
                          name: "search_workspace",
                          input: data.input,
                          status: "pending" as const,
                        }],
                      }
                    : m
                ));
              }

              // Handle tool_result events (update tool status to applied)
              if (data.result !== undefined && data.id) {
                setMessages(prev => prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: m.toolCalls?.map(tc =>
                          tc.id === data.id
                            ? { ...tc, status: "applied" as const, result: data.result }
                            : tc
                        ),
                      }
                    : m
                ));
              }
              
              if (data.message) {
                // Error message
                setError(data.message);
              }
              
            } catch {
              // Ignore parse errors for incomplete JSON
            }
          }
        }
      }
      
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // Request was cancelled
        return;
      }
      setError((err as Error).message);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [runId, messages, version, stagedEdits, onEditSuggestion]);

  /**
   * Stage an edit locally (move from pending to staged)
   * This does NOT save to backend - just prepares the edit for commit
   */
  const stageEdit = useCallback((edit: EditSuggestion) => {
    // Move from pending to staged
    setPendingEdits(prev => prev.map(e =>
      e.id === edit.id ? { ...e, status: "staged" as const } : e
    ));
    
    // Add to staged edits
    setStagedEdits(prev => [...prev, { ...edit, status: "staged" as const }]);
    
    // Update message tool call status
    setMessages(prev => prev.map(m => ({
      ...m,
      toolCalls: m.toolCalls?.map(tc =>
        tc.id === edit.id ? { ...tc, status: "applied" as const } : tc
      ),
    })));
    
    // Notify parent of staged content update
    const newContent = applyEditToContent(currentDocRef.current, edit.oldStr, edit.newStr);
    onDocumentUpdate?.(newContent);
  }, [onDocumentUpdate]);

  /**
   * Unstage an edit (move from staged back to pending)
   */
  const unstageEdit = useCallback((editId: string) => {
    const edit = stagedEdits.find(e => e.id === editId);
    if (!edit) return;
    
    // Remove from staged
    setStagedEdits(prev => prev.filter(e => e.id !== editId));
    
    // Move back to pending
    setPendingEdits(prev => prev.map(e =>
      e.id === editId ? { ...e, status: "pending" as const } : e
    ));
    
    // Update message tool call status
    setMessages(prev => prev.map(m => ({
      ...m,
      toolCalls: m.toolCalls?.map(tc =>
        tc.id === editId ? { ...tc, status: "pending" as const } : tc
      ),
    })));
  }, [stagedEdits]);

  /**
   * Reject an edit completely
   */
  const rejectEdit = useCallback((editId: string) => {
    setPendingEdits(prev => prev.map(e =>
      e.id === editId ? { ...e, status: "rejected" as const } : e
    ));
    
    // Also remove from staged if it was there
    setStagedEdits(prev => prev.filter(e => e.id !== editId));
    
    setMessages(prev => prev.map(m => ({
      ...m,
      toolCalls: m.toolCalls?.map(tc =>
        tc.id === editId ? { ...tc, status: "rejected" as const } : tc
      ),
    })));
  }, []);

  /**
   * Clear all staged edits (discard uncommitted changes - moves back to pending)
   */
  const clearStagedEdits = useCallback(() => {
    setStagedEdits([]);
    // Move all staged back to pending
    setPendingEdits(prev => prev.map(e =>
      e.status === "staged" ? { ...e, status: "pending" as const } : e
    ));
  }, []);

  /**
   * Commit all staged edits (after successful save - marks as applied and removes)
   * Call this after the backend save succeeds.
   */
  const commitStagedEdits = useCallback(() => {
    // Get IDs of staged edits
    const stagedIds = new Set(stagedEdits.map(e => e.id));
    
    // Clear staged edits
    setStagedEdits([]);
    
    // Mark as applied in pendingEdits (so they show as "Applied" in UI)
    // Then filter them out since they're now saved
    setPendingEdits(prev => prev.filter(e => !stagedIds.has(e.id)));
    
    // Update message tool call statuses to "applied"
    setMessages(prev => prev.map(m => ({
      ...m,
      toolCalls: m.toolCalls?.map(tc =>
        stagedIds.has(tc.id) ? { ...tc, status: "applied" as const } : tc
      ),
    })));
  }, [stagedEdits]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPendingEdits([]);
    setStagedEdits([]);
    setError(null);

    // Abort any ongoing request
    abortControllerRef.current?.abort();
    
    // Clear localStorage
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem(CHAT_STORAGE_KEY(runId));
      } catch (err) {
        console.error("Failed to clear chat state from localStorage:", err);
      }
    }
  }, [runId]);

  /**
   * Legacy applyEdit - now just calls stageEdit for backward compatibility
   * The actual save happens when the user clicks "Save" in the editor
   */
  const applyEdit = useCallback(async (edit: EditSuggestion): Promise<boolean> => {
    stageEdit(edit);
    return true;
  }, [stageEdit]);

  return {
    messages,
    isStreaming,
    error,
    pendingEdits,
    stagedEdits,
    stagedContent,
    ambiguityHighlights,
    sendMessage,
    stageEdit,
    unstageEdit,
    rejectEdit,
    clearStagedEdits,
    commitStagedEdits,
    clearMessages,
    applyEdit,
  };
}
