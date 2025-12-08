"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { ProjectFile, RunFeedback, RunQuestions, RunStep, RunSummary } from "@/types/backend";

interface RunStatusTrackerProps {
  runId: string;
  initialRun: RunSummary;
  initialSteps: RunStep[];
}

const TERMINAL_STATUSES = new Set(["success", "failed"]);

export function RunStatusTracker({ runId, initialRun, initialSteps }: RunStatusTrackerProps) {
  const [run, setRun] = useState<RunSummary>(initialRun);
  const [steps, setSteps] = useState<RunStep[]>(initialSteps);
  const [isPolling, setIsPolling] = useState<boolean>(!TERMINAL_STATUSES.has(initialRun.status));
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isDownloadingMd, setIsDownloadingMd] = useState<boolean>(false);
  const [isDownloadingDocx, setIsDownloadingDocx] = useState<boolean>(false);
  const [isExportingGdoc, setIsExportingGdoc] = useState<boolean>(false);
  const [isEmbedding, setIsEmbedding] = useState<boolean>(false);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState<boolean>(false);
  const [isViewingMarkdown, setIsViewingMarkdown] = useState<boolean>(false);
  const [markdownContent, setMarkdownContent] = useState<string>("");
  const [isLoadingMarkdown, setIsLoadingMarkdown] = useState<boolean>(false);
  const [showQuickRegen, setShowQuickRegen] = useState<boolean>(false);
  const [expertAnswers, setExpertAnswers] = useState<string>("");
  const [solutionGraphicUrl, setSolutionGraphicUrl] = useState<string | null>(null);
  const [isLoadingGraphic, setIsLoadingGraphic] = useState<boolean>(false);
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

  const questions: RunQuestions | null = useMemo(() => {
    const expertQuestions = (run.params?.questions_for_expert as string[] | undefined) ?? [];
    const clientQuestions = (run.params?.questions_for_client as string[] | undefined) ?? [];
    if (expertQuestions.length === 0 && clientQuestions.length === 0) {
      return null;
    }
    return {
      questions_for_expert: expertQuestions,
      questions_for_client: clientQuestions,
    };
  }, [run.params]);

  const canExport = run.status.toLowerCase() === "success";

  const handleDownload = async (kind: "md" | "docx") => {
    setActionError(null);
    setActionMessage(null);
    if (kind === "md") setIsDownloadingMd(true);
    if (kind === "docx") setIsDownloadingDocx(true);
    try {
      const endpoint = kind === "md" ? `/api/runs/${runId}/download-md` : `/api/runs/${runId}/download-docx`;
      const response = await fetch(endpoint);
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Download failed (${response.status})`;
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const fallbackName = `run-${run.id}.${kind}`;
      const resultName = run.result_path ? run.result_path.split("/").pop() ?? fallbackName : fallbackName;
      const filename =
        kind === "docx"
          ? resultName.replace(/\.md$/i, "") + ".docx"
          : /\.md$/i.test(resultName)
          ? resultName
          : `${resultName}.md`;
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setActionMessage(kind === "md" ? "Markdown downloaded" : "DOCX downloaded");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Download failed";
      setActionError(message);
    } finally {
      if (kind === "md") setIsDownloadingMd(false);
      if (kind === "docx") setIsDownloadingDocx(false);
    }
  };

  const handleExportGoogleDoc = async () => {
    setActionError(null);
    setActionMessage(null);
    setIsExportingGdoc(true);
      try {
      const response = await fetch(`/api/runs/${runId}/export-google-doc`, { method: "POST" });
      const payload = (await response.json().catch(() => ({}))) as {
        doc_url?: string;
        doc_id?: string;
        status?: string;
        detail?: string;
      };
        if (!response.ok) {
        const detail = payload.detail ?? `Export failed (${response.status})`;
        throw new Error(detail);
        }
      const docUrl = payload.doc_url;
      if (docUrl) {
        window.open(docUrl, "_blank", "noopener,noreferrer");
        setActionMessage("Opened Google Doc");
      } else {
        setActionMessage("Google Doc created");
        }
      } catch (err) {
      const message = err instanceof Error ? err.message : "Export to Google Docs failed";
      setActionError(message);
      } finally {
      setIsExportingGdoc(false);
    }
  };

  const handleEmbed = async () => {
    setActionError(null);
    setActionMessage(null);
    setIsEmbedding(true);
    try {
      const response = await fetch(`/api/runs/${runId}/embed`, { method: "POST" });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail ?? `Embedding failed (${response.status})`;
        throw new Error(detail);
      }
      setActionMessage("Scope embedded in vector store");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Embedding failed";
      setActionError(message);
    } finally {
      setIsEmbedding(false);
    }
  };

  const handleGenerateQuestions = async () => {
    setActionError(null);
    setActionMessage(null);
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
      setActionMessage("Questions generated successfully");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Question generation failed";
      setActionError(message);
    } finally {
      setIsGeneratingQuestions(false);
    }
  };

  const handleViewMarkdown = async () => {
    setActionError(null);
    setIsLoadingMarkdown(true);
    try {
      const response = await fetch(`/api/runs/${runId}/download-md`);
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
      setActionError(message);
    } finally {
      setIsLoadingMarkdown(false);
    }
  };

  const handleCopyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(markdownContent);
      setActionMessage("Markdown copied to clipboard");
    } catch {
      setActionError("Failed to copy to clipboard");
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
        <div className="run-tracker__actions">
          {error ? <p className="error-text">{error}</p> : null}
          {actionError ? <p className="error-text">{actionError}</p> : null}
          {actionMessage ? <p className="success-text">{actionMessage}</p> : null}
          <button
            className="btn-secondary"
            type="button"
            onClick={handleViewMarkdown}
            disabled={!canExport || isLoadingMarkdown}
          >
            {isLoadingMarkdown ? "Loading…" : "View Markdown"}
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={() => handleDownload("md")}
            disabled={!canExport || isDownloadingMd}
          >
            {isDownloadingMd ? "Preparing…" : "Download Markdown"}
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={() => handleDownload("docx")}
            disabled={!canExport || isDownloadingDocx}
          >
            {isDownloadingDocx ? "Preparing…" : "Download DOCX"}
          </button>
          <button
            className="btn-secondary"
            type="button"
            disabled
            title="Currently recommended to export or view markdown and paste into a doc. Direct import has formatting issues being fixed."
            style={{ opacity: 0.5, cursor: "not-allowed" }}
          >
            Export to Google Docs
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={handleEmbed}
            disabled={!canExport || isEmbedding}
            title="Add this scope to the historical database for future reference"
          >
            {isEmbedding ? "Saving…" : "Save to Vector Store"}
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={() => setShowQuickRegen(true)}
            disabled={!canExport}
          >
            Quick Regen
          </button>
          <button className="btn-secondary" type="button" onClick={() => setIsPolling(true)} disabled={isPolling}>
            {isPolling ? "Polling…" : "Refresh"}
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
            display: "flex", 
            justifyContent: "center", 
            alignItems: "center",
            padding: "0.5rem", 
            background: "#0a0a14", 
            borderRadius: "0.5rem",
            minHeight: "400px",
            overflow: "hidden"
          }}>
            <img 
              src={solutionGraphicUrl} 
              alt="Solution Architecture Graphic" 
              style={{ 
                width: "100%",
                height: "auto",
                maxHeight: "70vh",
                objectFit: "contain",
                borderRadius: "0.375rem",
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
          Technical clarifications for the solutions architect designing this solution.
        </p>
        {questions?.questions_for_expert && questions.questions_for_expert.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {questions.questions_for_expert.map((q, idx) => (
              <li key={idx}>{q}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No expert questions generated yet.</p>
        )}
      </section>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <h2 style={{ margin: 0 }}>Questions for Client</h2>
        <p className="muted" style={{ fontSize: "0.875rem", marginTop: "-0.25rem" }}>
          Follow-up questions to ask the client to clarify requirements or fill gaps.
        </p>
        {questions?.questions_for_client && questions.questions_for_client.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {questions.questions_for_client.map((q, idx) => (
              <li key={idx}>{q}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No client questions generated yet.</p>
        )}
      </section>

      {/* Quick Regen with Expert Answers */}
      {questions && (questions.questions_for_expert?.length || questions.questions_for_client?.length) && (
        <section className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Provide Answers & Regenerate</h2>
          <p className="muted" style={{ fontSize: "0.875rem", marginTop: "-0.25rem" }}>
            Answer the expert questions above and click Quick Regen to improve the scope with your insights.
          </p>
          <textarea
            placeholder="Paste your answers to the expert questions here..."
            value={expertAnswers}
            onChange={(e) => setExpertAnswers(e.target.value)}
            rows={5}
            style={{
              width: "100%",
              padding: "0.75rem",
              borderRadius: "0.375rem",
              border: "1px solid #374151",
              background: "#1f2937",
              color: "#e5e7eb",
              fontSize: "0.875rem",
              resize: "vertical",
            }}
          />
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <Link
              href={`/projects/${run.project_id}?quickRegen=${run.id}&context=${encodeURIComponent(expertAnswers)}`}
              className="btn-primary"
              style={{ textDecoration: "none" }}
            >
              Quick Regen with Answers
            </Link>
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
            {steps.length === 0 ? (
              <tr>
                <td colSpan={4}>Step data unavailable.</td>
              </tr>
            ) : (
              steps.map((step) => (
                <tr key={step.id}>
                  <td>{step.name}</td>
                  <td>{step.status}</td>
                  <td>{formatDate(step.started_at)}</td>
                  <td>{formatDate(step.finished_at)}</td>
                </tr>
              ))
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
              <h2 style={{ margin: 0 }}>Markdown Preview</h2>
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
              <label htmlFor="expert-answers">Answers / Additional Context</label>
              <textarea
                id="expert-answers"
                value={expertAnswers}
                onChange={(e) => setExpertAnswers(e.target.value)}
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
                href={`/projects/${run.project_id}?quickRegen=${run.id}&context=${encodeURIComponent(expertAnswers)}`}
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
    return new Date(value).toLocaleString();
  } catch (err) {
    return value;
  }
}

export default RunStatusTracker;

