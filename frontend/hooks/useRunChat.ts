"use client";

import { useState, useCallback, useRef } from "react";

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
}

export interface EditSuggestion {
  id: string;
  oldStr: string;
  newStr: string;
  reason?: string;
  status: "pending" | "applied" | "rejected";
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
  sendMessage: (message: string) => Promise<void>;
  applyEdit: (edit: EditSuggestion) => Promise<boolean>;
  rejectEdit: (editId: string) => void;
  clearMessages: () => void;
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
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentDocRef = useRef(documentContent);
  
  // Keep doc ref updated
  currentDocRef.current = documentContent;

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
      const history = messages.map(m => ({
        role: m.role,
        content: m.content,
      }));
      
      const response = await fetch(`/api/runs/${runId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversation_history: history,
          document_content: currentDocRef.current,
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
  }, [runId, messages, version, onEditSuggestion]);

  const applyEdit = useCallback(async (edit: EditSuggestion): Promise<boolean> => {
    try {
      const response = await fetch(`/api/runs/${runId}/apply-edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_str: edit.oldStr,
          new_str: edit.newStr,
          document_content: currentDocRef.current,
          save_version: true,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Apply edit failed: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        // Update edit status
        setPendingEdits(prev => prev.map(e =>
          e.id === edit.id ? { ...e, status: "applied" as const } : e
        ));
        
        // Update message tool call status
        setMessages(prev => prev.map(m => ({
          ...m,
          toolCalls: m.toolCalls?.map(tc =>
            tc.id === edit.id ? { ...tc, status: "applied" as const } : tc
          ),
        })));
        
        // Notify parent of document update
        onDocumentUpdate?.(result.new_content);
        currentDocRef.current = result.new_content;
        
        return true;
      }
      
      return false;
    } catch (err) {
      setError((err as Error).message);
      return false;
    }
  }, [runId, onDocumentUpdate]);

  const rejectEdit = useCallback((editId: string) => {
    setPendingEdits(prev => prev.map(e =>
      e.id === editId ? { ...e, status: "rejected" as const } : e
    ));
    
    setMessages(prev => prev.map(m => ({
      ...m,
      toolCalls: m.toolCalls?.map(tc =>
        tc.id === editId ? { ...tc, status: "rejected" as const } : tc
      ),
    })));
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPendingEdits([]);
    setError(null);
    
    // Abort any ongoing request
    abortControllerRef.current?.abort();
  }, []);

  return {
    messages,
    isStreaming,
    error,
    pendingEdits,
    sendMessage,
    applyEdit,
    rejectEdit,
    clearMessages,
  };
}
