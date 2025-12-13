"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ThreePanelLayout } from "@/components/editor/ThreePanelLayout";
import { FileExplorer } from "@/components/editor/FileExplorer";
import { ChatSidebar } from "@/components/editor/ChatSidebar";
import { MarkdownEditor } from "@/components/editor/MarkdownEditor";
import { FilePreviewModal } from "@/components/editor/FilePreviewModal";
import { useRunChat, EditSuggestion } from "@/hooks/useRunChat";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface RunData {
  id: string;
  project_id: string;
  status: string;
  template_type?: string;
}

interface VersionData {
  id: string;
  version_number: number;
  markdown?: string;
}

interface ArtifactData {
  id: string;
  kind: string;
  path: string;
  content?: string;
}

export default function EditorPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const runId = params.runId as string;

  // State
  const [run, setRun] = useState<RunData | null>(null);
  const [versions, setVersions] = useState<VersionData[]>([]);
  const [documentContent, setDocumentContent] = useState("");
  const [currentVersion, setCurrentVersion] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [inputFiles, setInputFiles] = useState<Array<{ id: string; name: string; type: "input"; mediaType?: string; path?: string }>>([]);
  const [previewFile, setPreviewFile] = useState<{ id: string; name: string; mediaType?: string; path?: string } | null>(null);

  // Chat hook
  const {
    messages,
    isStreaming,
    error,
    pendingEdits,
    sendMessage,
    applyEdit,
    rejectEdit,
    clearMessages,
  } = useRunChat({
    runId,
    documentContent,
    version: currentVersion,
    onEditSuggestion: (edit) => {
      toast({
        title: "Edit Suggested",
        description: `AI suggested an edit: "${edit.reason || 'text replacement'}"`,
      });
    },
    onDocumentUpdate: (newContent) => {
      setDocumentContent(newContent);
      toast({
        title: "Edit Applied",
        description: "Document updated successfully",
      });
    },
  });

  // Load run data
  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        // Load run info
        const runRes = await fetch(`/api/runs/${runId}`);
        if (!runRes.ok) throw new Error("Failed to load run");
        const runData = await runRes.json();
        setRun(runData);

        // Load versions
        const versionsRes = await fetch(`/api/runs/${runId}/versions`);
        if (versionsRes.ok) {
          const versionsData = await versionsRes.json();
          setVersions(versionsData);
        }

        // Load original document (v1)
        const artifactRes = await fetch(`/api/runs/${runId}/artifact?kind=rendered_doc`);
        if (artifactRes.ok) {
          const text = await artifactRes.text();
          setDocumentContent(text);
        }

        // Load input files for project
        if (runData.project_id) {
          const filesRes = await fetch(`/api/projects/${runData.project_id}/files`);
          if (filesRes.ok) {
            const filesData = await filesRes.json();
            setInputFiles(filesData.map((f: { id: string; filename: string; media_type?: string; path?: string }) => ({
              id: f.id,
              name: f.filename,
              type: "input" as const,
              mediaType: f.media_type,
              path: f.path,
            })));
          }
        }
      } catch (err) {
        console.error("Failed to load editor data:", err);
        toast({
          title: "Error",
          description: "Failed to load document",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    }

    loadData();
  }, [runId, toast]);

  // Handle version change
  const handleVersionSelect = useCallback(async (version: number) => {
    setCurrentVersion(version);
    
    if (version === 1) {
      // Load original artifact
      const res = await fetch(`/api/runs/${runId}/artifact?kind=rendered_doc`);
      if (res.ok) {
        const text = await res.text();
        setDocumentContent(text);
      }
    } else {
      // Load version markdown
      const versionData = versions.find(v => v.version_number === version);
      if (versionData?.markdown) {
        setDocumentContent(versionData.markdown);
      }
    }
  }, [runId, versions]);

  // Handle save
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`/api/runs/${runId}/save-markdown`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          markdown: documentContent,
          version: currentVersion,
        }),
      });

      if (!res.ok) throw new Error("Failed to save");
      
      const result = await res.json();
      toast({
        title: "Saved",
        description: result.message || `Saved as v${result.version_number}`,
      });

      // Refresh versions
      const versionsRes = await fetch(`/api/runs/${runId}/versions`);
      if (versionsRes.ok) {
        const versionsData = await versionsRes.json();
        setVersions(versionsData);
        if (result.version_number) {
          setCurrentVersion(result.version_number);
        }
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to save document",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  }, [runId, documentContent, currentVersion, toast]);

  // Handle apply edit
  const handleApplyEdit = useCallback(async (edit: EditSuggestion) => {
    const success = await applyEdit(edit);
    if (!success) {
      toast({
        title: "Edit Failed",
        description: "Could not apply the suggested edit",
        variant: "destructive",
      });
    }
  }, [applyEdit, toast]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center gap-4 border-b border-border bg-background px-4 py-2">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </Button>
        <div className="flex-1">
          <h1 className="text-sm font-medium">
            {run?.template_type || "Document"} Editor
          </h1>
          <p className="text-xs text-muted-foreground">
            Run {runId.slice(0, 8)}... • v{currentVersion}
          </p>
        </div>
      </div>

      {/* Three panel layout */}
      <div className="flex-1 overflow-hidden">
        <ThreePanelLayout
          leftPanel={
            <FileExplorer
              inputFiles={inputFiles}
              versions={versions.map(v => ({
                id: v.id,
                name: `Version ${v.version_number}`,
                type: "version" as const,
                version: v.version_number,
              }))}
              currentVersion={currentVersion}
              onFileSelect={(file) => {
                setPreviewFile({
                  id: file.id,
                  name: file.name,
                  mediaType: file.mediaType,
                  path: file.path,
                });
              }}
              onVersionSelect={handleVersionSelect}
            />
          }
          centerPanel={
            <MarkdownEditor
              content={documentContent}
              onChange={setDocumentContent}
              onSave={handleSave}
              isSaving={isSaving}
              pendingEdits={pendingEdits}
              onApplyEdit={handleApplyEdit}
              onRejectEdit={rejectEdit}
            />
          }
          rightPanel={
            <ChatSidebar
              messages={messages}
              isStreaming={isStreaming}
              error={error}
              pendingEdits={pendingEdits}
              onSendMessage={sendMessage}
              onApplyEdit={handleApplyEdit}
              onRejectEdit={rejectEdit}
              onClearMessages={clearMessages}
            />
          }
        />
      </div>

      {/* File Preview Modal */}
      <FilePreviewModal
        file={previewFile}
        projectId={run?.project_id || ""}
        onClose={() => setPreviewFile(null)}
      />
    </div>
  );
}
