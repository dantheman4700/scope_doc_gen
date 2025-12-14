"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ThreePanelLayout } from "@/components/editor/ThreePanelLayout";
import { FileExplorer } from "@/components/editor/FileExplorer";
import { ChatSidebar } from "@/components/editor/ChatSidebar";
import { MarkdownEditor } from "@/components/editor/MarkdownEditor";
import { FilePreviewModal } from "@/components/editor/FilePreviewModal";
import { useRunChat, EditSuggestion } from "@/hooks/useRunChat";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, AlertTriangle, GitCommit } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface RunData {
  id: string;
  project_id: string;
  status: string;
  template_type?: string;
  is_indexed?: boolean;
  indexed_chunks?: number;
}

interface VersionData {
  id: string;
  version_number: number;
  markdown?: string;
}

export default function EditorPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const runId = params.runId as string;

  // State
  const [run, setRun] = useState<RunData | null>(null);
  const [versions, setVersions] = useState<VersionData[]>([]);
  const [savedContent, setSavedContent] = useState(""); // Last saved/committed version
  const [localContent, setLocalContent] = useState(""); // User's local edits
  const [currentVersion, setCurrentVersion] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [inputFiles, setInputFiles] = useState<Array<{ id: string; name: string; type: "input"; mediaType?: string; path?: string }>>([]);
  const [previewFile, setPreviewFile] = useState<{ id: string; name: string; mediaType?: string; path?: string } | null>(null);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [pendingVersionSwitch, setPendingVersionSwitch] = useState<number | null>(null);
  
  // Indexing state
  const [isIndexed, setIsIndexed] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexedChunks, setIndexedChunks] = useState(0);

  // Chat hook
  const {
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
  } = useRunChat({
    runId,
    documentContent: localContent,
    version: currentVersion,
    onEditSuggestion: (edit) => {
      toast({
        title: "Edit Suggested",
        description: `AI suggested an edit: "${edit.reason || 'text replacement'}"`,
      });
    },
    onDocumentUpdate: (newContent) => {
      setLocalContent(newContent);
    },
  });

  // Compute effective content (local + staged edits)
  const effectiveContent = useMemo(() => {
    if (stagedEdits.length === 0) return localContent;
    return stagedContent;
  }, [localContent, stagedEdits, stagedContent]);

  // Check if there are unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    return localContent !== savedContent || stagedEdits.length > 0;
  }, [localContent, savedContent, stagedEdits]);

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

        // Fetch indexing status separately (lightweight endpoint)
        try {
          const indexRes = await fetch(`/api/runs/${runId}/index-status`);
          if (indexRes.ok) {
            const indexData = await indexRes.json();
            setIsIndexed(indexData.is_indexed || false);
            setIndexedChunks(indexData.indexed_chunks || 0);
          }
        } catch {
          // Silently ignore - not critical for editor function
        }

        // Load versions
        const versionsRes = await fetch(`/api/runs/${runId}/versions`);
        let versionsData: VersionData[] = [];
        if (versionsRes.ok) {
          versionsData = await versionsRes.json();
          setVersions(versionsData);
        }

        // Determine which version to load (latest or v1)
        let versionToLoad = 1;
        let contentToLoad = "";

        if (versionsData.length > 0) {
          // Find the latest version (highest version number)
          const latestVersion = Math.max(...versionsData.map((v: VersionData) => v.version_number));
          versionToLoad = latestVersion;
          
          // Load the latest version's content
          const latestVersionData = versionsData.find((v: VersionData) => v.version_number === latestVersion);
          if (latestVersionData?.markdown) {
            contentToLoad = latestVersionData.markdown;
          }
        }

        // If no version content found, or if versionToLoad is 1, load from artifact
        if (!contentToLoad || versionToLoad === 1) {
          const artifactRes = await fetch(`/api/runs/${runId}/artifact?kind=rendered_doc`);
          if (artifactRes.ok) {
            contentToLoad = await artifactRes.text();
          }
        }

        setCurrentVersion(versionToLoad);
        setSavedContent(contentToLoad);
        setLocalContent(contentToLoad);

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

  // Handle version change with unsaved changes check
  const handleVersionSelect = useCallback(async (version: number) => {
    if (hasUnsavedChanges) {
      setPendingVersionSwitch(version);
      setShowDiscardDialog(true);
      return;
    }
    
    await switchToVersion(version);
  }, [hasUnsavedChanges]);

  // Actually switch to a version - fetches fresh data to avoid stale state
  const switchToVersion = useCallback(async (version: number) => {
    setIsLoading(true);
    clearMessages();
    clearStagedEdits();
    
    try {
      // Fetch fresh versions data to avoid stale state
      const versionsRes = await fetch(`/api/runs/${runId}/versions`);
      const freshVersions: VersionData[] = versionsRes.ok ? await versionsRes.json() : [];
      setVersions(freshVersions);
      
      let contentToLoad = "";
      
      if (version === 1 || Math.floor(version) === 1 && !freshVersions.some(v => v.version_number === version)) {
        // Load original artifact for v1
        const res = await fetch(`/api/runs/${runId}/artifact?kind=rendered_doc`);
        if (res.ok) {
          contentToLoad = await res.text();
        }
      } else {
        // Find the version in fresh data
        const versionData = freshVersions.find(v => v.version_number === version);
        if (versionData?.markdown) {
          contentToLoad = versionData.markdown;
        } else {
          // Fallback to artifact if version not found
          const res = await fetch(`/api/runs/${runId}/artifact?kind=rendered_doc`);
          if (res.ok) {
            contentToLoad = await res.text();
          }
        }
      }
      
      setCurrentVersion(version);
      setSavedContent(contentToLoad);
      setLocalContent(contentToLoad);
    } catch (err) {
      console.error("Failed to switch version:", err);
      toast({
        title: "Error",
        description: "Failed to load version",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [runId, clearMessages, clearStagedEdits, toast]);

  // Confirm version switch (discard changes)
  const confirmVersionSwitch = useCallback(() => {
    if (pendingVersionSwitch !== null) {
      switchToVersion(pendingVersionSwitch);
      setPendingVersionSwitch(null);
    }
    setShowDiscardDialog(false);
  }, [pendingVersionSwitch, switchToVersion]);

  // Cancel version switch
  const cancelVersionSwitch = useCallback(() => {
    setPendingVersionSwitch(null);
    setShowDiscardDialog(false);
  }, []);

  // Handle commit - creates a new major version
  const handleCommit = useCallback(async () => {
    setIsSaving(true);
    try {
      const contentToSave = effectiveContent;
      const currentMajor = Math.floor(currentVersion);
      
      const res = await fetch(`/api/runs/${runId}/commit-version`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          markdown: contentToSave,
          base_version: currentMajor,
        }),
      });

      if (!res.ok) throw new Error("Failed to commit");
      
      const result = await res.json();
      toast({
        title: "Committed",
        description: result.message || `Committed as v${result.version_number}`,
      });

      // Update saved content to match what we just saved
      setSavedContent(contentToSave);
      setLocalContent(contentToSave);
      
      // Commit staged edits (marks as applied and removes from pending)
      commitStagedEdits();

      // Refresh versions and update current version
      const versionsRes = await fetch(`/api/runs/${runId}/versions`);
      if (versionsRes.ok) {
        const versionsData = await versionsRes.json();
        setVersions(versionsData);
        if (result.version_number) {
          setCurrentVersion(result.version_number);
        }
      }
    } catch (err) {
      // Fallback to regular save if commit endpoint doesn't exist
      await handleSave();
    } finally {
      setIsSaving(false);
    }
  }, [runId, effectiveContent, currentVersion, toast, commitStagedEdits]);

  // Handle save - saves as sub-version
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const contentToSave = effectiveContent;
      
      const res = await fetch(`/api/runs/${runId}/save-markdown`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          markdown: contentToSave,
          version: currentVersion,
        }),
      });

      if (!res.ok) throw new Error("Failed to save");
      
      const result = await res.json();
      toast({
        title: "Saved",
        description: result.message || `Saved as v${result.version_number}`,
      });

      // Update saved content to match what we just saved
      setSavedContent(contentToSave);
      setLocalContent(contentToSave);
      
      // Commit staged edits (marks as applied and removes from pending)
      commitStagedEdits();

      // Refresh versions and update current version
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
  }, [runId, effectiveContent, currentVersion, toast, commitStagedEdits]);

  // Handle apply edit - stages the edit locally without auto-saving
  // All staged edits will be saved together when user clicks Save/Commit
  const handleApplyEdit = useCallback(async (edit: EditSuggestion) => {
    const success = await applyEdit(edit);
    if (!success) {
      toast({
        title: "Edit Failed",
        description: "Could not apply the suggested edit",
        variant: "destructive",
      });
    }
    // Note: No toast on success - edits are staged silently
    // User will see "staged" indicator and save when ready
  }, [applyEdit, toast]);

  // Handle discard all changes
  const handleDiscardChanges = useCallback(() => {
    setLocalContent(savedContent);
    clearStagedEdits();
    toast({
      title: "Changes Discarded",
      description: "All unsaved changes have been discarded",
    });
  }, [savedContent, clearStagedEdits, toast]);

  // Handle version deletion
  const handleVersionDelete = useCallback(async (version: number) => {
    if (version === 1) {
      toast({
        title: "Cannot Delete",
        description: "The original version cannot be deleted",
        variant: "destructive",
      });
      return;
    }

    try {
      const res = await fetch(`/api/runs/${runId}/versions/${version}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("Failed to delete");

      toast({
        title: "Deleted",
        description: `Version ${version} has been deleted`,
      });

      // Refresh versions list
      const versionsRes = await fetch(`/api/runs/${runId}/versions`);
      if (versionsRes.ok) {
        const versionsData = await versionsRes.json();
        setVersions(versionsData);
      }

      // If we deleted the current version, switch to v1
      if (Math.abs(currentVersion - version) < 0.001) {
        await switchToVersion(1);
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to delete version",
        variant: "destructive",
      });
    }
  }, [runId, currentVersion, toast, switchToVersion]);

  // Handle workspace indexing
  const handleIndexWorkspace = useCallback(async () => {
    setIsIndexing(true);
    try {
      const res = await fetch(`/api/runs/${runId}/index-documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: currentVersion }),
      });

      if (!res.ok) throw new Error("Failed to index");

      const data = await res.json();
      setIsIndexed(true);
      setIndexedChunks(data.indexed_chunks || 0);
      
      toast({
        title: "Workspace Indexed",
        description: data.message || `Indexed ${data.indexed_chunks} chunks`,
      });
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to index workspace",
        variant: "destructive",
      });
    } finally {
      setIsIndexing(false);
    }
  }, [runId, currentVersion, toast]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Get current major version for display
  const currentMajorVersion = Math.floor(currentVersion);
  const isSubVersion = currentVersion !== currentMajorVersion;

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
            {isSubVersion && <span className="text-blue-500"> (sub-version)</span>}
            {hasUnsavedChanges && (
              <span className="ml-2 text-yellow-600">• Unsaved changes</span>
            )}
            {pendingEdits.filter(e => e.status === "pending").length > 0 && (
              <span className="ml-2 text-purple-600">
                • {pendingEdits.filter(e => e.status === "pending").length} pending edit{pendingEdits.filter(e => e.status === "pending").length > 1 ? 's' : ''}
              </span>
            )}
          </p>
        </div>
        
        {/* Discard button */}
        {hasUnsavedChanges && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDiscardChanges}
            className="text-muted-foreground"
          >
            Discard Changes
          </Button>
        )}
        
        {/* Commit button for major version */}
        {hasUnsavedChanges && (
          <Button
            variant="default"
            size="sm"
            onClick={handleCommit}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <GitCommit className="mr-1 h-4 w-4" />
            )}
            Commit v{currentMajorVersion + 1}
          </Button>
        )}
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
              onVersionDelete={handleVersionDelete}
              isIndexed={isIndexed}
              isIndexing={isIndexing}
              indexedChunks={indexedChunks}
              onIndexWorkspace={handleIndexWorkspace}
            />
          }
          centerPanel={
            <MarkdownEditor
              content={effectiveContent}
              savedContent={savedContent}
              stagedEdits={stagedEdits}
              onChange={setLocalContent}
              onSave={handleSave}
              isSaving={isSaving}
              pendingEdits={pendingEdits.filter(e => e.status === "pending")}
              onApplyEdit={handleApplyEdit}
              onRejectEdit={rejectEdit}
              ambiguityHighlights={ambiguityHighlights}
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

      {/* Discard Changes Dialog */}
      <AlertDialog open={showDiscardDialog} onOpenChange={setShowDiscardDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
              Unsaved Changes
            </AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Switching versions will discard all your changes.
              Are you sure you want to continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={cancelVersionSwitch}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={confirmVersionSwitch} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Discard Changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
