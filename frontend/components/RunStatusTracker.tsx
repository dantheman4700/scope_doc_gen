"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import type { Artifact, RunStep, RunSummary } from "@/types/backend";

interface RunStatusTrackerProps {
  runId: string;
  initialRun: RunSummary;
  initialSteps: RunStep[];
  initialArtifacts: Artifact[];
}

const TERMINAL_STATUSES = new Set(["success", "failed"]);

export function RunStatusTracker({ runId, initialRun, initialSteps, initialArtifacts }: RunStatusTrackerProps) {
  const [run, setRun] = useState<RunSummary>(initialRun);
  const [steps, setSteps] = useState<RunStep[]>(initialSteps);
  const [artifacts, setArtifacts] = useState<Artifact[]>(initialArtifacts);
  const [isPolling, setIsPolling] = useState<boolean>(!TERMINAL_STATUSES.has(initialRun.status));
  const [error, setError] = useState<string | null>(null);
  const [previewArtifactId, setPreviewArtifactId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string>("");
  const [previewContentType, setPreviewContentType] = useState<string>("");
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPolling) {
      return;
    }

    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const [runResponse, stepsResponse, artifactsResponse] = await Promise.all([
          fetch(`/api/runs/${runId}`),
          fetch(`/api/runs/${runId}/steps`),
          fetch(`/api/runs/${runId}/artifacts`)
        ]);

        if (cancelled) {
          return;
        }

        if (!runResponse.ok) {
          throw new Error(`Status query failed: ${runResponse.status}`);
        }

        const runData = (await runResponse.json()) as RunSummary;
        const stepsData = stepsResponse.ok ? ((await stepsResponse.json()) as RunStep[]) : [];
        const artifactsData = artifactsResponse.ok ? ((await artifactsResponse.json()) as Artifact[]) : [];

        setRun(runData);
        setSteps(stepsData ?? []);
        setArtifacts(artifactsData ?? []);
        setError(null);

        if (TERMINAL_STATUSES.has(runData.status)) {
          setIsPolling(false);
        }
      } catch (err) {
        console.error(err);
        setError((err as Error).message);
      }
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [isPolling, runId]);

  const statusChip = useMemo(() => {
    const status = run.status.toLowerCase();
    if (status === "running") {
      return { label: "In progress", className: "chip chip--running" };
    }
    if (status === "success") {
      return { label: "Completed", className: "chip chip--success" };
    }
    if (status === "failed") {
      return { label: "Failed", className: "chip chip--failed" };
    }
    if (status === "pending") {
      return { label: "Queued", className: "chip chip--pending" };
    }
    return { label: run.status, className: "chip" };
  }, [run.status]);

  const previewArtifact = useMemo(() => {
    if (!previewArtifactId) {
      return null;
    }
    return artifacts.find((artifact) => artifact.id === previewArtifactId) ?? null;
  }, [artifacts, previewArtifactId]);

  useEffect(() => {
    if (!previewArtifact) {
      setPreviewContent("");
      setPreviewContentType("");
      setPreviewError(null);
      setIsPreviewLoading(false);
      return;
    }

    const artifactId = previewArtifact.id;

    let cancelled = false;
    async function loadPreview() {
      setIsPreviewLoading(true);
      setPreviewError(null);
      try {
        const response = await fetch(`/artifacts/${artifactId}/download`, {
          credentials: "include"
        });
        if (!response.ok) {
          throw new Error(`Preview failed: ${response.status}`);
        }
        const contentType = response.headers.get("content-type") ?? "";
        if (!contentType.includes("text") && !contentType.includes("json")) {
          throw new Error(`Unsupported content type: ${contentType || "unknown"}`);
        }
        let text = await response.text();
        if (contentType.includes("application/json")) {
          try {
            const parsed = JSON.parse(text);
            text = JSON.stringify(parsed, null, 2);
          } catch {
            // leave as raw text
          }
        }
        if (!cancelled) {
          setPreviewContentType(contentType);
          setPreviewContent(text);
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewError((err as Error).message);
          setPreviewContent("");
        }
      } finally {
        if (!cancelled) {
          setIsPreviewLoading(false);
        }
      }
    }

    loadPreview();
    return () => {
      cancelled = true;
    };
  }, [previewArtifact]);

  return (
    <div className="run-tracker">
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
        </div>
        <div className="run-tracker__actions">
          {error ? <p className="error-text">{error}</p> : null}
          <button
            className="btn-secondary"
            type="button"
            onClick={() => setIsPolling(true)}
            disabled={isPolling}
          >
            {isPolling ? "Polling…" : "Refresh"}
          </button>
        </div>
      </section>

      {run.error ? <p className="error-text">{run.error}</p> : null}

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

      <section>
        <h2>Artifacts</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Kind</th>
              <th>Created</th>
              <th>Meta</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.length === 0 ? (
              <tr>
                <td colSpan={4}>No artifacts recorded.</td>
              </tr>
            ) : (
              artifacts.map((artifact) => (
                <tr key={artifact.id} className={previewArtifactId === artifact.id ? "table-row--active" : undefined}>
                  <td>{artifact.kind}</td>
                  <td>{formatDate(artifact.created_at)}</td>
                  <td>{summarizeMeta(artifact.meta)}</td>
                  <td className="artifact-actions">
                    <button
                      className="btn-secondary"
                      type="button"
                      onClick={() => setPreviewArtifactId(artifact.id)}
                    >
                      View
                    </button>
                    <a className="btn-primary" href={`/artifacts/${artifact.id}/download`}>
                      Download
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {previewArtifact ? (
        <section className="artifact-preview">
          <div className="artifact-preview__header">
            <h3>Preview: {previewArtifact.kind}</h3>
            <span>{previewArtifact.path}</span>
          </div>
          <p className="artifact-preview__meta">
            <span>Created: {formatDate(previewArtifact.created_at)}</span>
            <span>Content type: {previewContentType || "unknown"}</span>
          </p>
          <details className="artifact-preview__meta-detail">
            <summary>Metadata</summary>
            <pre>{JSON.stringify(previewArtifact.meta, null, 2)}</pre>
          </details>
          {isPreviewLoading ? (
            <p>Loading preview…</p>
          ) : previewError ? (
            <p className="error-text">{previewError}</p>
          ) : previewContent ? (
            <div className="preview-pane">
              {shouldRenderMarkdown(previewArtifact, previewContentType) ? (
                <ReactMarkdown>{previewContent}</ReactMarkdown>
              ) : (
                <pre>{previewContent}</pre>
              )}
            </div>
          ) : (
            <p>No preview available.</p>
          )}
        </section>
      ) : null}
    </div>
  );
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString();
  } catch (err) {
    return value;
  }
}

function summarizeMeta(meta: Record<string, unknown>): string {
  if (!meta || Object.keys(meta).length === 0) {
    return "—";
  }
  const summary = JSON.stringify(meta);
  return summary.length > 80 ? `${summary.slice(0, 77)}…` : summary;
}

function shouldRenderMarkdown(artifact: Artifact, contentType: string): boolean {
  if (contentType.includes("markdown")) {
    return true;
  }
  if (contentType.includes("text")) {
    return artifact.path.endsWith(".md") || artifact.path.endsWith(".markdown");
  }
  return false;
}

export default RunStatusTracker;

