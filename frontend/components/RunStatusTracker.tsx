"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { ProjectFile, RunFeedback, RunStep, RunSummary } from "@/types/backend";

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

        setRun((prev) => (prev.status === runData.status ? prev : runData));
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
            <span>Research: {run.research_mode}</span>
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
            onClick={() => handleDownload("md")}
            disabled={!canExport || isDownloadingMd}
          >
            {isDownloadingMd ? "Preparing…" : "Download MD"}
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
            onClick={handleExportGoogleDoc}
            disabled={!canExport || isExportingGdoc}
          >
            {isExportingGdoc ? "Exporting…" : "Export to Google Docs"}
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={handleEmbed}
            disabled={!canExport || isEmbedding}
          >
            {isEmbedding ? "Embedding…" : "Add to vector store"}
          </button>
          <button className="btn-secondary" type="button" onClick={() => setIsPolling(true)} disabled={isPolling}>
            {isPolling ? "Polling…" : "Refresh"}
          </button>
        </div>
      </section>

      {run.error ? <p className="error-text">{run.error}</p> : null}

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

