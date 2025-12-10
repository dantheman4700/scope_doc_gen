"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type { ProjectFile, RunFeedback, RunQuestions, RunStep, RunSummary, RunVersion } from "@/types/backend";
import { useToast } from "@/components/ui/use-toast";

interface RunStatusTrackerProps {
  runId: string;
  initialRun: RunSummary;
  initialSteps: RunStep[];
}

const TERMINAL_STATUSES = new Set(["success", "failed"]);

export function RunStatusTracker({ runId, initialRun, initialSteps }: RunStatusTrackerProps) {
  const router = useRouter();
  const { toast } = useToast();
  const [run, setRun] = useState<RunSummary>(initialRun);
  const [steps, setSteps] = useState<RunStep[]>(initialSteps);
  const [isPolling, setIsPolling] = useState<boolean>(!TERMINAL_STATUSES.has(initialRun.status));
  const [error, setError] = useState<string | null>(null);
  
  // Helper functions for toast notifications
  const showSuccess = (message: string) => {
    toast({ title: "Success", description: message, variant: "default" });
  };
  const showError = (message: string) => {
    toast({ title: "Error", description: message, variant: "destructive" });
  };
  const [isDownloadingMd, setIsDownloadingMd] = useState<boolean>(false);
  const [isDownloadingDocx, setIsDownloadingDocx] = useState<boolean>(false);
  const [isExportingGdoc, setIsExportingGdoc] = useState<boolean>(false);
  const [existingGoogleDocUrl, setExistingGoogleDocUrl] = useState<string | null>(null);
  const [isEmbedding, setIsEmbedding] = useState<boolean>(false);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState<boolean>(false);
  const [isViewingMarkdown, setIsViewingMarkdown] = useState<boolean>(false);
  const [markdownContent, setMarkdownContent] = useState<string>("");
  const [isLoadingMarkdown, setIsLoadingMarkdown] = useState<boolean>(false);
  const [showQuickRegen, setShowQuickRegen] = useState<boolean>(false);
  const [expertAnswers, setExpertAnswers] = useState<Record<number, string>>({});
  const [clientAnswers, setClientAnswers] = useState<Record<number, string>>({});
  const [isSubmittingQuickRegen, setIsSubmittingQuickRegen] = useState<boolean>(false);
  const [quickRegenText, setQuickRegenText] = useState<string>("");
  const [regenJobId, setRegenJobId] = useState<string | null>(null);
  const [regenJobStatus, setRegenJobStatus] = useState<string | null>(null);
  const [completedRegens, setCompletedRegens] = useState<Array<{
    id: string;
    status: string;
    versionNumber?: number;
    finishedAt: string;
    error?: string;
  }>>([]);
  const [solutionGraphicUrl, setSolutionGraphicUrl] = useState<string | null>(null);
  const [isLoadingGraphic, setIsLoadingGraphic] = useState<boolean>(false);
  // Version management
  const [versions, setVersions] = useState<RunVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [isLoadingVersions, setIsLoadingVersions] = useState<boolean>(false);
  const [regenGraphic, setRegenGraphic] = useState<boolean>(false);
  const [extraResearch, setExtraResearch] = useState<boolean>(false);
  const [researchProvider, setResearchProvider] = useState<"claude" | "perplexity">("claude");
  // Included files do not change after run creation, so load once and never re-render them on poll
  const [includedFiles, setIncludedFiles] = useState<ProjectFile[]>([]);
  const [isLoadingIncludedFiles, setIsLoadingIncludedFiles] = useState<boolean>(false);
  const [includedLoaded, setIncludedLoaded] = useState<boolean>(false);

  // Recompute included IDs when run changes
  const includedFileIdSet = useMemo(() => new Set(run.included_file_ids ?? []), [run.included_file_ids]);

  useEffect(() => {
    if (!isPolling) return;

    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const [runResponse, stepsResponse] = await Promise.all([
          fetch(`/api/runs/${runId}`, { cache: "no-store" }),
          fetch(`/api/runs/${runId}/steps`, { cache: "no-store" })
        ]);

        if (cancelled) return;
        if (!runResponse.ok) throw new Error(`Status query failed: ${runResponse.status}`);

        const runData = (await runResponse.json()) as RunSummary;
        const stepsData = stepsResponse.ok ? ((await stepsResponse.json()) as RunStep[]) : [];

        // Always update run data - params may have changed (e.g., questions auto-generated)
        setRun(runData);
        setSteps(stepsData ?? []);
        setError(null);

        const statusLower = runData.status.toLowerCase();
        if (TERMINAL_STATUSES.has(statusLower)) {
          setIsPolling(false);
        }
      } catch (err) {
        console.error(err);
        setError((err as Error).message);
      }
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [isPolling, runId]);

  // Check for solution graphic when run is successful
  useEffect(() => {
    if (run.status.toLowerCase() !== "success" || solutionGraphicUrl) return;
    
    setIsLoadingGraphic(true);
    fetch(`/api/runs/${runId}/solution-graphic`)
      .then((res) => {
        if (res.ok) {
          return res.blob();
        }
        return null;
      })
      .then((blob) => {
        if (blob) {
          setSolutionGraphicUrl(URL.createObjectURL(blob));
        }
      })
      .catch(() => {
        // No graphic available, that's fine
      })
      .finally(() => setIsLoadingGraphic(false));
  }, [run.status, runId, solutionGraphicUrl]);

  const statusChip = useMemo(() => {
    const status = run.status.toLowerCase();
    if (status === "running") return { label: "In progress", className: "chip chip--running" };
    if (status === "success") return { label: "Completed", className: "chip chip--success" };
    if (status === "failed") return { label: "Failed", className: "chip chip--failed" };
    if (status === "pending") return { label: "Queued", className: "chip chip--pending" };
    return { label: run.status, className: "chip" };
  }, [run.status]);

  const feedback: RunFeedback | null = useMemo(() => {
    const direct = (run.feedback as RunFeedback | undefined) ?? null;
    const fromParams = (run.params?.feedback as RunFeedback | undefined) ?? null;
    return direct ?? fromParams ?? null;
  }, [run.feedback, run.params]);

  // Get questions - use version-specific questions when a version > 1 is selected
  const questions: RunQuestions | null = useMemo(() => {
    // If a version > 1 is selected, use that version's questions
    if (selectedVersion && selectedVersion > 1) {
      const version = versions.find(v => v.version_number === selectedVersion);
      if (version) {
        const expertQs = version.questions_for_expert || [];
        const clientQs = version.questions_for_client || [];
        if (expertQs.length === 0 && clientQs.length === 0) {
          return null;
        }
        return {
          questions_for_expert: expertQs,
          questions_for_client: clientQs,
        };
      }
    }
    // Fall back to run.params for v1 (original) or when no version selected
    const expertQuestions = (run.params?.questions_for_expert as string[] | undefined) ?? [];
    const clientQuestions = (run.params?.questions_for_client as string[] | undefined) ?? [];
    if (expertQuestions.length === 0 && clientQuestions.length === 0) {
      return null;
    }
    return {
      questions_for_expert: expertQuestions,
      questions_for_client: clientQuestions,
    };
  }, [run.params, selectedVersion, versions]);

  const canExport = run.status.toLowerCase() === "success";

  const handleDownload = async (kind: "md" | "docx") => {
    if (kind === "md") setIsDownloadingMd(true);
    if (kind === "docx") setIsDownloadingDocx(true);
    try {
      // Include version parameter in download URL
      const versionParam = selectedVersion ? `?version=${selectedVersion}` : "";
      const baseEndpoint = kind === "md" ? `/api/runs/${runId}/download-md` : `/api/runs/${runId}/download-docx`;
      const endpoint = `${baseEndpoint}${versionParam}`;
      const response = await fetch(endpoint);
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Download failed (${response.status})`;
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const fallbackName = `run-${run.id}${selectedVersion && selectedVersion > 1 ? `-v${selectedVersion}` : ""}.${kind}`;
      const resultName = run.result_path ? run.result_path.split("/").pop() ?? fallbackName : fallbackName;
      const filename =
        kind === "docx"
          ? resultName.replace(/\.md$/i, "") + (selectedVersion && selectedVersion > 1 ? `-v${selectedVersion}` : "") + ".docx"
          : /\.md$/i.test(resultName)
          ? resultName.replace(/\.md$/i, "") + (selectedVersion && selectedVersion > 1 ? `-v${selectedVersion}` : "") + ".md"
          : `${resultName}${selectedVersion && selectedVersion > 1 ? `-v${selectedVersion}` : ""}.md`;
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      const versionLabel = selectedVersion ? ` (v${selectedVersion})` : "";
      showSuccess(kind === "md" ? `Markdown downloaded${versionLabel}` : `DOCX downloaded${versionLabel}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Download failed";
      showError(message);
    } finally {
      if (kind === "md") setIsDownloadingMd(false);
      if (kind === "docx") setIsDownloadingDocx(false);
    }
  };

  const handleExportGoogleDoc = async (forceNew: boolean = false) => {
    setIsExportingGdoc(true);
    try {
      // Build URL with version parameter
      const params = new URLSearchParams();
      if (forceNew) params.set("force", "true");
      if (selectedVersion) params.set("version", String(selectedVersion));
      const queryString = params.toString();
      const url = `/api/runs/${runId}/export-google-doc${queryString ? `?${queryString}` : ""}`;
      
      const response = await fetch(url, { method: "POST" });
      const payload = (await response.json().catch(() => ({}))) as {
        doc_url?: string;
        doc_id?: string;
        status?: string;
        detail?: string;
        version?: number;
      };
      if (!response.ok) {
        const detail = payload.detail ?? `Export failed (${response.status})`;
        throw new Error(detail);
      }
      const docUrl = payload.doc_url;
      if (docUrl) {
        setExistingGoogleDocUrl(docUrl);
        window.open(docUrl, "_blank", "noopener,noreferrer");
        const versionInfo = payload.version ? ` (v${payload.version})` : "";
        showSuccess(payload.status === "existing" ? `Opened Google Doc${versionInfo}` : `Created new Google Doc${versionInfo}`);
      } else {
        showSuccess("Google Doc created");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Export to Google Docs failed";
      showError(message);
    } finally {
      setIsExportingGdoc(false);
    }
  };

  const handleOpenExistingGoogleDoc = () => {
    if (existingGoogleDocUrl) {
      window.open(existingGoogleDocUrl, "_blank", "noopener,noreferrer");
    }
  };

  const handleEmbed = async () => {
    setIsEmbedding(true);
    try {
      const response = await fetch(`/api/runs/${runId}/embed`, { method: "POST" });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Embedding failed (${response.status})`;
        throw new Error(detail);
      }
      showSuccess("Scope embedded in vector store");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Embedding failed";
      showError(message);
    } finally {
      setIsEmbedding(false);
    }
  };

  const handleGenerateQuestions = async () => {
    setIsGeneratingQuestions(true);
    try {
      const response = await fetch(`/api/runs/${runId}/generate-questions`, { method: "POST" });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Question generation failed (${response.status})`;
        throw new Error(detail);
      }
      const data = (await response.json()) as { questions_for_expert?: string[]; questions_for_client?: string[] };
      // Update run params locally to reflect the new questions
      setRun((prev) => ({
        ...prev,
        params: {
          ...prev.params,
          questions_for_expert: data.questions_for_expert || [],
          questions_for_client: data.questions_for_client || [],
        },
      }));
      showSuccess("Questions generated successfully");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Question generation failed";
      showError(message);
    } finally {
      setIsGeneratingQuestions(false);
    }
  };

  const handleViewMarkdown = async () => {
    setIsLoadingMarkdown(true);
    try {
      // Include version parameter when viewing markdown
      const versionParam = selectedVersion ? `?version=${selectedVersion}` : "";
      const response = await fetch(`/api/runs/${runId}/download-md${versionParam}`);
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Failed to load markdown (${response.status})`;
        throw new Error(detail);
      }
      const text = await response.text();
      setMarkdownContent(text);
      setIsViewingMarkdown(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load markdown";
      showError(message);
    } finally {
      setIsLoadingMarkdown(false);
    }
  };

  const handleCopyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(markdownContent);
      showSuccess("Markdown copied to clipboard");
    } catch {
      showError("Failed to copy to clipboard");
    }
  };

  // Fetch versions when run is successful
  useEffect(() => {
    if (run.status.toLowerCase() !== "success") return;
    
    // Always default to v1 (original) when first loading
    if (selectedVersion === null) {
      setSelectedVersion(1);
    }
    
    setIsLoadingVersions(true);
    fetch(`/api/runs/${runId}/versions`)
      .then((res) => {
        if (res.ok) return res.json();
        return [];
      })
      .then((data: RunVersion[]) => {
        setVersions(data);
      })
      .catch(() => {
        // No versions yet, that's fine
      })
      .finally(() => {
        setIsLoadingVersions(false);
      });
  }, [runId, run.status, selectedVersion]);

  const handleQuickRegenWithAnswers = async () => {
    // Combine all answers into a formatted string
    const expertQs = questions?.questions_for_expert || [];
    const clientQs = questions?.questions_for_client || [];
    
    let combinedAnswers = "";
    
    if (expertQs.length > 0) {
      combinedAnswers += "**Expert Question Answers:**\n";
      expertQs.forEach((q, idx) => {
        const answer = expertAnswers[idx]?.trim();
        if (answer) {
          combinedAnswers += `Q: ${q}\nA: ${answer}\n\n`;
        }
      });
    }
    
    if (clientQs.length > 0) {
      combinedAnswers += "**Client Question Answers:**\n";
      clientQs.forEach((q, idx) => {
        const answer = clientAnswers[idx]?.trim();
        if (answer) {
          combinedAnswers += `Q: ${q}\nA: ${answer}\n\n`;
        }
      });
    }
    
    if (!combinedAnswers.trim()) {
      showError("Please provide at least one answer");
      return;
    }
    
    setIsSubmittingQuickRegen(true);
    setRegenJobStatus("starting");
    
    // Call the regenerate endpoint to start a background job
    const payload = {
      answers: combinedAnswers,
      regen_graphic: regenGraphic,
      extra_research: extraResearch,
      research_provider: researchProvider,
    };
    
    try {
      const response = await fetch(`/api/runs/${runId}/regenerate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => ({}))) as { detail?: string; message?: string };
        throw new Error(errorPayload.detail ?? errorPayload.message ?? `Request failed (${response.status})`);
      }
      
      const result = (await response.json()) as { job_id: string; message: string };
      setRegenJobId(result.job_id);
      setRegenJobStatus("running");
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/runs/${runId}/regen-status/${result.job_id}`);
          if (!statusRes.ok) {
            clearInterval(pollInterval);
            setRegenJobStatus(null);
            setIsSubmittingQuickRegen(false);
            showError("Failed to get regen status");
            return;
          }
          
          const status = (await statusRes.json()) as {
            status: string;
            version_id?: string;
            version_number?: number;
            error?: string;
          };
          
          setRegenJobStatus(status.status);
          
          if (status.status === "success") {
            clearInterval(pollInterval);
            showSuccess(`Created version ${status.version_number}`);
            
            // Record completed regen for display in Steps table
            setCompletedRegens((prev) => [...prev, {
              id: result.job_id,
              status: "success",
              versionNumber: status.version_number,
              finishedAt: new Date().toISOString(),
            }]);
            
            setRegenJobId(null);
            setRegenJobStatus(null);
            setIsSubmittingQuickRegen(false);
            
            // Refresh versions list
            const versionsRes = await fetch(`/api/runs/${runId}/versions`);
            if (versionsRes.ok) {
              const newVersions = (await versionsRes.json()) as RunVersion[];
              setVersions(newVersions);
              if (status.version_number) {
                setSelectedVersion(status.version_number);
              }
            }
            
            // Clear the answers
            setExpertAnswers({});
            setClientAnswers({});
          } else if (status.status === "failed") {
            clearInterval(pollInterval);
            
            // Record failed regen for display in Steps table
            setCompletedRegens((prev) => [...prev, {
              id: result.job_id,
              status: "failed",
              finishedAt: new Date().toISOString(),
              error: status.error,
            }]);
            
            setRegenJobId(null);
            setRegenJobStatus(null);
            setIsSubmittingQuickRegen(false);
            showError(status.error || "Regeneration failed");
          }
        } catch {
          // Keep polling on transient errors
        }
      }, 2000);
      
      // Safety timeout after 10 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (regenJobStatus === "running") {
          setRegenJobStatus(null);
          setIsSubmittingQuickRegen(false);
          showError("Regeneration timed out");
        }
      }, 600000);
      
    } catch (err) {
      const message = err instanceof Error ? err.message : "Quick regeneration failed";
      showError(message);
      setRegenJobStatus(null);
      setIsSubmittingQuickRegen(false);
    }
  };

  useEffect(() => {
    if (!run.project_id || includedFileIdSet.size === 0) {
      setIncludedFiles([]);
      return;
    }

    let ignore = false;
    setIsLoadingIncludedFiles(true);

    fetch(`/api/projects/${run.project_id}/files/`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Unable to load project files (${response.status})`);
        }
        return response.json() as Promise<ProjectFile[]>;
      })
      .then((projectFiles) => {
        if (!ignore) {
          setIncludedFiles(projectFiles.filter((file) => includedFileIdSet.has(file.id)));
        }
      })
      .catch((fetchError) => {
        console.error("Failed to load included files", fetchError);
        if (!ignore) {
          setIncludedFiles([]);
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoadingIncludedFiles(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [run.project_id, includedFileIdSet]);

  return (
    <div className="run-tracker" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <section className="run-tracker__header">
        <div>
          <h1>Run {run.id}</h1>
          <p className="run-tracker__meta">
            <span className={statusChip.className}>{statusChip.label}</span>
            <span>Mode: {run.run_mode}</span>
            {run.template_type && <span>Template: {run.template_type}</span>}
            <span>Research: {run.research_mode}</span>
            {Boolean(run.params?.enable_vector_store) && <span>Vector Search: ✓</span>}
          </p>
          <p className="run-tracker__timestamps">
            <span>Created: {formatDate(run.created_at)}</span>
            <span>Started: {formatDate(run.started_at)}</span>
            <span>Finished: {formatDate(run.finished_at)}</span>
          </p>
          {run.parent_run_id ? (
            <p className="run-tracker__parent">
              Parent run:{" "}
              <Link className="link" href={`/runs/${run.parent_run_id}`}>
                {run.parent_run_id}
              </Link>
            </p>
          ) : null}
        </div>
        {/* Error state from polling */}
        {error ? <p className="error-text">{error}</p> : null}
        
        {/* Action Buttons - Clean Layout */}
        <div className="run-tracker__actions" style={{ 
          display: "flex", 
          flexWrap: "wrap", 
          gap: "0.75rem", 
          alignItems: "center",
          padding: "0.75rem 0",
          borderTop: "1px solid #374151"
        }}>
          {/* Version Selector - Always show v1, show other versions if available */}
          {canExport && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginRight: "0.5rem" }}>
              <span style={{ color: "#9ca3af", fontSize: "0.875rem", fontWeight: 500 }}>Version:</span>
              <select
                value={selectedVersion ?? 1}
                onChange={(e) => setSelectedVersion(Number(e.target.value))}
                style={{
                  padding: "0.375rem 0.75rem",
                  borderRadius: "0.375rem",
                  border: "1px solid #4f46e5",
                  background: "#1e1b4b",
                  color: "#a5b4fc",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {/* Always show v1 (Original) */}
                <option value={1}>v1 (Original)</option>
                {/* Show additional versions from API */}
                {versions
                  .filter(v => v.version_number > 1)
                  .sort((a, b) => a.version_number - b.version_number)
                  .map((v) => (
                    <option key={v.version_number} value={v.version_number}>
                      v{v.version_number}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {/* Divider */}
          {canExport && <span style={{ color: "#4b5563" }}>|</span>}

          {/* Google Docs Export - Primary with clear state indication */}
          <div style={{ display: "flex", gap: "0.25rem" }}>
            <button
              className="btn-primary"
              type="button"
              onClick={() => existingGoogleDocUrl ? handleOpenExistingGoogleDoc() : handleExportGoogleDoc(false)}
              disabled={!canExport || isExportingGdoc}
              style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}
              title={existingGoogleDocUrl ? "Open existing Google Doc" : "Export to Google Docs"}
            >
              {isExportingGdoc 
                ? "⏳ Exporting…" 
                : existingGoogleDocUrl 
                  ? `📄 Open Doc${selectedVersion ? ` (v${selectedVersion})` : ""}`
                  : `📄 Export${selectedVersion ? ` v${selectedVersion}` : ""} to Google Doc`}
            </button>
            {existingGoogleDocUrl && (
              <button
                className="btn-secondary"
                type="button"
                onClick={() => handleExportGoogleDoc(true)}
                disabled={!canExport || isExportingGdoc}
                title="Create a new Google Doc (re-export)"
                style={{ padding: "0.5rem", fontSize: "0.75rem" }}
              >
                🔄
              </button>
            )}
          </div>

          {/* Download Dropdown */}
          <select
            className="btn-secondary"
            style={{ 
              padding: "0.5rem 0.75rem", 
              cursor: "pointer",
              border: "1px solid #374151",
              borderRadius: "0.375rem",
            }}
            disabled={!canExport}
            onChange={(e) => {
              const value = e.target.value;
              e.target.value = "";
              if (value === "view") handleViewMarkdown();
              else if (value === "md") handleDownload("md");
              else if (value === "docx") handleDownload("docx");
            }}
            defaultValue=""
          >
            <option value="" disabled>📥 Download{selectedVersion ? ` v${selectedVersion}` : ""}</option>
            <option value="view">View Markdown</option>
            <option value="md">Download .md</option>
            <option value="docx">Download .docx</option>
          </select>

          {/* Vector Store - Clear label */}
          <button
            className="btn-secondary"
            type="button"
            onClick={handleEmbed}
            disabled={!canExport || isEmbedding}
            title="Save this scope to the vector store for future reference and search"
            style={{ fontSize: "0.875rem" }}
          >
            {isEmbedding ? "💾 Saving…" : "💾 Save to Vector Store"}
          </button>

          {/* Refresh */}
          <button 
            className="btn-secondary" 
            type="button" 
            onClick={() => setIsPolling(true)} 
            disabled={isPolling}
            title="Refresh status"
            style={{ padding: "0.5rem" }}
          >
            {isPolling ? "⏳" : "🔄"}
          </button>
        </div>
      </section>

      {run.error ? <p className="error-text">{run.error}</p> : null}

      {/* Solution Graphic */}
      {solutionGraphicUrl && (
        <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>Solution Graphic</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn-secondary"
                type="button"
                onClick={() => {
                  const modal = document.getElementById("graphic-zoom-modal");
                  if (modal) modal.style.display = "flex";
                }}
              >
                🔍 Zoom
              </button>
              <a 
                href={solutionGraphicUrl} 
                download={`solution_graphic_${runId}.png`}
                className="btn-secondary"
                style={{ textDecoration: "none" }}
              >
                Download
              </a>
            </div>
          </div>
          <div style={{ 
            display: "block",
            padding: "0", 
            background: "#0a0a14", 
            borderRadius: "0.5rem",
            overflow: "hidden"
          }}>
            <img 
              src={solutionGraphicUrl} 
              alt="Solution Architecture Graphic" 
              style={{ 
                display: "block",
                width: "100%",
                height: "auto",
                borderRadius: "0.5rem",
                cursor: "zoom-in"
              }}
              onClick={() => {
                const modal = document.getElementById("graphic-zoom-modal");
                if (modal) modal.style.display = "flex";
              }}
            />
          </div>
          {/* Zoom Modal */}
          <div 
            id="graphic-zoom-modal"
            style={{
              display: "none",
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.9)",
              justifyContent: "center",
              alignItems: "center",
              zIndex: 9999,
              cursor: "zoom-out",
              padding: "2rem"
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                e.currentTarget.style.display = "none";
              }
            }}
          >
            <img 
              src={solutionGraphicUrl} 
              alt="Solution Architecture Graphic (Full Size)" 
              style={{ 
                maxWidth: "95vw",
                maxHeight: "95vh",
                objectFit: "contain",
                borderRadius: "0.5rem",
                boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)"
              }}
            />
            <button
              style={{
                position: "absolute",
                top: "1rem",
                right: "1rem",
                background: "rgba(255,255,255,0.1)",
                border: "none",
                borderRadius: "0.5rem",
                padding: "0.5rem 1rem",
                color: "#fff",
                cursor: "pointer",
                fontSize: "1rem"
              }}
              onClick={() => {
                const modal = document.getElementById("graphic-zoom-modal");
                if (modal) modal.style.display = "none";
              }}
            >
              ✕ Close
            </button>
          </div>
        </section>
      )}
      {isLoadingGraphic && (
        <section className="card">
          <p className="muted">Loading solution graphic...</p>
        </section>
      )}

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <h2 style={{ margin: 0 }}>AI Feedback</h2>
        {feedback ? (
          <div className="feedback-grid" style={{ display: "grid", gap: "0.75rem" }}>
            <FeedbackList title="Uncertain areas" items={feedback.uncertain_areas} tone="warn" />
            <FeedbackList title="Low confidence" items={feedback.low_confidence_sections} tone="info" />
            <FeedbackList title="Missing information" items={feedback.missing_information} tone="neutral" />
            {feedback.notes ? <p className="muted">{feedback.notes}</p> : null}
          </div>
        ) : (
          <p className="muted">No feedback captured for this run.</p>
        )}
      </section>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Questions for Expert</h2>
          {canExport && !questions && (
            <button
              className="btn-secondary"
              type="button"
              onClick={handleGenerateQuestions}
              disabled={isGeneratingQuestions}
            >
              {isGeneratingQuestions ? "Generating…" : "Generate Questions"}
            </button>
          )}
        </div>
        <p className="muted" style={{ fontSize: "0.875rem", marginTop: "-0.25rem" }}>
          Technical clarifications for the solutions architect. Answer these to improve the scope.
        </p>
        {questions?.questions_for_expert && questions.questions_for_expert.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {questions.questions_for_expert.map((q, idx) => (
              <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <label style={{ fontWeight: 500, color: "#e5e7eb" }}>{idx + 1}. {q}</label>
                <textarea
                  placeholder="Your answer..."
                  value={expertAnswers[idx] || ""}
                  onChange={(e) => setExpertAnswers((prev) => ({ ...prev, [idx]: e.target.value }))}
                  rows={2}
                  style={{
                    width: "100%",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "0.375rem",
                    border: "1px solid #374151",
                    background: "#1f2937",
                    color: "#e5e7eb",
                    fontSize: "0.875rem",
                    resize: "vertical",
                    minHeight: "2.5rem",
                    fontFamily: "inherit",
                  }}
                />
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No expert questions generated yet.</p>
        )}
      </section>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <h2 style={{ margin: 0 }}>Questions for Client</h2>
        <p className="muted" style={{ fontSize: "0.875rem", marginTop: "-0.25rem" }}>
          Follow-up questions to ask the client. Record their answers here for context.
        </p>
        {questions?.questions_for_client && questions.questions_for_client.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {questions.questions_for_client.map((q, idx) => (
              <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <label style={{ fontWeight: 500, color: "#e5e7eb" }}>{idx + 1}. {q}</label>
                <textarea
                  placeholder="Client's answer..."
                  value={clientAnswers[idx] || ""}
                  onChange={(e) => setClientAnswers((prev) => ({ ...prev, [idx]: e.target.value }))}
                  rows={2}
                  style={{
                    width: "100%",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "0.375rem",
                    border: "1px solid #374151",
                    background: "#1f2937",
                    color: "#e5e7eb",
                    fontSize: "0.875rem",
                    resize: "vertical",
                    minHeight: "2.5rem",
                    fontFamily: "inherit",
                  }}
                />
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No client questions generated yet.</p>
        )}
      </section>

      {/* Quick Regen with Answers Button */}
      {questions && (questions.questions_for_expert?.length || questions.questions_for_client?.length) && (
        <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Regenerate with Answers</h2>
          <p className="muted" style={{ fontSize: "0.875rem", marginTop: "-0.25rem" }}>
            Create a new version of the scope using the answers you provided above.
          </p>
          
          {/* Regen options */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", padding: "0.75rem", background: "#1f2937", borderRadius: "0.375rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={regenGraphic}
                onChange={(e) => setRegenGraphic(e.target.checked)}
              />
              <span style={{ color: "#e5e7eb" }}>Regenerate Solution Graphic</span>
            </label>
            
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={extraResearch}
                onChange={(e) => setExtraResearch(e.target.checked)}
              />
              <span style={{ color: "#e5e7eb" }}>Extra Research</span>
            </label>
            
            {extraResearch && (
              <div style={{ marginLeft: "1.5rem" }}>
                <select
                  value={researchProvider}
                  onChange={(e) => setResearchProvider(e.target.value as "claude" | "perplexity")}
                  style={{
                    padding: "0.375rem 0.75rem",
                    borderRadius: "0.375rem",
                    border: "1px solid #374151",
                    background: "#111827",
                    color: "#e5e7eb",
                    fontSize: "0.875rem",
                  }}
                >
                  <option value="claude">Claude Web Search</option>
                  <option value="perplexity">Perplexity Deep Research</option>
                </select>
              </div>
            )}
          </div>
          
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              className="btn-primary"
              type="button"
              onClick={handleQuickRegenWithAnswers}
              disabled={isSubmittingQuickRegen}
            >
              {isSubmittingQuickRegen 
                ? regenJobStatus === "running" 
                  ? "🔄 Regenerating (this may take a few minutes)…" 
                  : "Starting…"
                : "Create New Version"}
            </button>
            {regenJobStatus && (
              <span style={{ color: "#60a5fa", fontSize: "0.875rem" }}>
                Status: {regenJobStatus}
              </span>
            )}
          </div>
        </section>
      )}

      <section className="run-tracker__metadata">
        <h2>Included files</h2>
        {includedFileIdSet.size === 0 ? (
          <p>No files were associated with this run.</p>
        ) : isLoadingIncludedFiles ? (
          <p>Loading file details…</p>
        ) : includedFiles.length > 0 ? (
          <ul>
            {includedFiles.map((file) => (
              <li key={file.id}>
                {file.filename} <small style={{ color: "#6b7280" }}>({file.token_count.toLocaleString()} tokens)</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>Files included in this run are no longer available.</p>
        )}
      </section>

      <section>
        <h2>Steps</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Step</th>
              <th>Status</th>
              <th>Started</th>
              <th>Finished</th>
            </tr>
          </thead>
          <tbody>
            {steps.length === 0 && !regenJobId ? (
              <tr>
                <td colSpan={4}>Step data unavailable.</td>
              </tr>
            ) : (
              <>
                {steps.map((step) => (
                  <tr key={step.id}>
                    <td>{step.name}</td>
                    <td>{step.status}</td>
                    <td>{formatDate(step.started_at)}</td>
                    <td>{formatDate(step.finished_at)}</td>
                  </tr>
                ))}
                {/* Completed regen jobs */}
                {completedRegens.map((regen, idx) => (
                  <tr key={`regen-${regen.id}`} style={{ background: regen.status === "success" ? "#064e3b" : "#7f1d1d" }}>
                    <td>
                      {regen.status === "success" ? "✅" : "❌"} Regenerated Version {regen.versionNumber || "?"}
                    </td>
                    <td>
                      <span style={{ color: regen.status === "success" ? "#10b981" : "#ef4444" }}>
                        {regen.status}
                      </span>
                    </td>
                    <td>—</td>
                    <td>{formatDate(regen.finishedAt)}</td>
                  </tr>
                ))}
                {/* Active regen job */}
                {regenJobId && (
                  <tr style={{ background: "#1e3a5f" }}>
                    <td>🔄 Regenerating Version</td>
                    <td>
                      <span style={{ 
                        display: "inline-flex", 
                        alignItems: "center", 
                        gap: "0.5rem",
                        color: regenJobStatus === "success" ? "#10b981" : regenJobStatus === "failed" ? "#ef4444" : "#60a5fa"
                      }}>
                        {regenJobStatus === "running" && "⏳ "}
                        {regenJobStatus || "pending"}
                      </span>
                    </td>
                    <td>{formatDate(new Date().toISOString())}</td>
                    <td>—</td>
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>
      </section>

      {/* Markdown Viewer Modal */}
      {isViewingMarkdown && (
        <div
          className="modal-backdrop"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
            padding: "2rem",
          }}
          onClick={() => setIsViewingMarkdown(false)}
        >
          <div
            className="card"
            style={{
              maxWidth: "900px",
              width: "100%",
              maxHeight: "90vh",
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
              padding: "1.5rem",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0 }}>Markdown Preview{selectedVersion ? ` (v${selectedVersion})` : ""}</h2>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn-secondary" type="button" onClick={handleCopyMarkdown}>
                  Copy to Clipboard
                </button>
                <button className="btn-secondary" type="button" onClick={() => setIsViewingMarkdown(false)}>
                  Close
                </button>
              </div>
            </div>
            <div
              style={{
                flex: 1,
                overflow: "auto",
                background: "#0f0f1a",
                borderRadius: "0.5rem",
                padding: "1rem",
                border: "1px solid #374151",
              }}
            >
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: "0.875rem", lineHeight: 1.6, color: "#e5e7eb", fontFamily: "monospace" }}>
                {markdownContent}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Quick Regen Modal */}
      {showQuickRegen && (
        <div
          className="modal-backdrop"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
            padding: "2rem",
          }}
          onClick={() => setShowQuickRegen(false)}
        >
          <div
            className="card"
            style={{
              maxWidth: "600px",
              width: "100%",
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
              padding: "1.5rem",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ margin: 0 }}>Quick Regenerate</h2>
            <p style={{ color: "#9ca3af", margin: 0 }}>
              Make adjustments to this scope without reprocessing all documents.
            </p>
            
            {questions?.questions_for_expert && questions.questions_for_expert.length > 0 && (
              <div>
                <h3 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Expert Questions to Address</h3>
                <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.875rem", color: "#d1d5db" }}>
                  {questions.questions_for_expert.slice(0, 3).map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="form-field">
              <label htmlFor="quick-regen-text">Answers / Additional Context</label>
              <textarea
                id="quick-regen-text"
                value={quickRegenText}
                onChange={(e) => setQuickRegenText(e.target.value)}
                rows={4}
                placeholder="Provide answers to the expert questions above, or describe what changes you'd like to make..."
                style={{ width: "100%" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button className="btn-secondary" type="button" onClick={() => setShowQuickRegen(false)}>
                Cancel
              </button>
              <Link
                className="btn-primary"
                href={`/projects/${run.project_id}?quickRegen=${run.id}&context=${encodeURIComponent(quickRegenText)}`}
              >
                Start Quick Regen
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FeedbackList({
  title,
  items,
  tone = "neutral"
}: {
  title: string;
  items?: string[] | null;
  tone?: "warn" | "info" | "neutral";
}) {
  if (!items || items.length === 0) {
    return null;
  }
  const toneClass =
    tone === "warn" ? "chip chip--warning" : tone === "info" ? "chip chip--info" : "chip";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span className={toneClass}>{title}</span>
            </div>
      <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
        {items.map((item, idx) => (
          <li key={idx}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    // Ensure UTC is correctly parsed - if no timezone indicator, treat as UTC
    let dateStr = value;
    if (!dateStr.endsWith("Z") && !dateStr.includes("+") && !dateStr.includes("-", 10)) {
      dateStr = value + "Z";
    }
    return new Date(dateStr).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short"
    });
  } catch (err) {
    return value;
  }
}

export default RunStatusTracker;

