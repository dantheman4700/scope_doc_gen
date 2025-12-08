"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { Project, ProjectFile, RunSummary } from "@/types/backend";
import QuickRegenModal from "./QuickRegenModal";

const MODEL_TOKEN_LIMIT = 100_000;
const TOKEN_RECOMMENDED_MAX = Math.round(MODEL_TOKEN_LIMIT * 0.5);

interface ProjectWorkspaceProps {
  project: Project;
  initialFiles: ProjectFile[];
  initialRuns: RunSummary[];
}

interface FetchError {
  detail?: string;
  message?: string;
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return value;
  }
}

function statusChip(run: RunSummary): { label: string; className: string } {
  const status = run.status.toLowerCase();
  if (status === "running") return { label: "In progress", className: "chip chip--running" };
  if (status === "success") return { label: "Completed", className: "chip chip--success" };
  if (status === "failed") return { label: "Failed", className: "chip chip--failed" };
  if (status === "pending") return { label: "Queued", className: "chip chip--pending" };
  return { label: run.status, className: "chip" };
}

const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff"]);

function isImageFile(filename: string): boolean {
  const extension = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return IMAGE_EXTENSIONS.has(extension);
}

export function ProjectWorkspace({ project, initialFiles, initialRuns }: ProjectWorkspaceProps) {
  const router = useRouter();
  const [files, setFiles] = useState<ProjectFile[]>(initialFiles);
  const [runs, setRuns] = useState<RunSummary[]>(initialRuns);
  const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(
    () => new Set(initialFiles.map((file) => file.id))
  );
  const [quickRegenRun, setQuickRegenRun] = useState<RunSummary | null>(null);
  const [runMode, setRunMode] = useState<string>("oneshot");
  const [instructions, setInstructions] = useState<string>("");
  const [researchMode, setResearchMode] = useState<string>("quick");
  const [vectorStoreEnabled, setVectorStoreEnabled] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summarizingIds, setSummarizingIds] = useState<Set<string>>(new Set());
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [isPollingRuns, setIsPollingRuns] = useState<boolean>(true);
  const [templateId, setTemplateId] = useState<string>("");
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; mimeType: string; webViewLink: string }>>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState<boolean>(false);

  const selectedFiles = useMemo(
    () => files.filter((file) => selectedFileIds.has(file.id)),
    [files, selectedFileIds]
  );

  const totalTokens = useMemo(
    () => selectedFiles.reduce((sum, file) => sum + file.token_count, 0),
    [selectedFiles]
  );

  const toggleFile = useCallback((fileId: string) => {
    setSelectedFileIds((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  }, []);

  const toggleAllFiles = useCallback(() => {
    setSelectedFileIds((prev) => {
      if (prev.size === files.length) {
        return new Set();
      }
      return new Set(files.map((file) => file.id));
    });
  }, [files]);

  // Poll runs so the project page reflects latest statuses without manual refresh
  useEffect(() => {
    if (!isPollingRuns) return;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/projects/${project.id}/runs`, {
          cache: "no-store"
        });
        if (cancelled) return;
        if (!response.ok) return; // keep silent; next tick will retry
        const freshRuns = (await response.json()) as RunSummary[];
        setRuns(freshRuns);
      } catch {
        // ignore transient errors
      }
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [isPollingRuns, project.id]);

  // Fetch templates when one-shot mode is selected
  useEffect(() => {
    if (runMode === "oneshot" && templates.length === 0 && !isLoadingTemplates) {
      setIsLoadingTemplates(true);
      fetch(`/api/projects/${project.id}/runs/templates`)
        .then((response) => {
          if (!response.ok) {
            // Silently fail - templates are optional
            return [];
          }
          return response.json();
        })
        .then((data) => {
          setTemplates(data || []);
          if (data && data.length > 0 && !templateId) {
            // Auto-select first template
            setTemplateId(data[0].id);
          }
        })
        .catch(() => {
          // Silently fail - templates are optional
        })
        .finally(() => {
          setIsLoadingTemplates(false);
        });
    }
  }, [runMode, project.id, templates.length, isLoadingTemplates, templateId]);

  const handleSummarize = useCallback(
    async (fileId: string) => {
      setErrorMessage(null);
      setSummarizingIds((prev) => new Set(prev).add(fileId));
      try {
        const response = await fetch(`/api/projects/${project.id}/files/${fileId}/summarize`, {
          method: "POST"
        });
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as FetchError;
          const detail = payload.detail ?? payload.message ?? "Unable to summarize file";
          throw new Error(detail);
        }
        const updatedFile = (await response.json()) as ProjectFile;
        setFiles((prev) => prev.map((file) => (file.id === updatedFile.id ? updatedFile : file)));
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to summarize file";
        setErrorMessage(message);
      } finally {
        setSummarizingIds((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }
    },
    [project.id]
  );

  const handleToggleMode = useCallback(
    async (fileId: string) => {
      setErrorMessage(null);
      setTogglingIds((prev) => new Set(prev).add(fileId));
      try {
        const response = await fetch(`/api/projects/${project.id}/files/${fileId}/toggle-mode`, {
          method: "PATCH"
        });
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as FetchError;
          const detail = payload.detail ?? payload.message ?? "Unable to toggle file mode";
          throw new Error(detail);
        }
        const updatedFile = (await response.json()) as ProjectFile;
        setFiles((prev) => prev.map((file) => (file.id === updatedFile.id ? updatedFile : file)));
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to toggle file mode";
        setErrorMessage(message);
      } finally {
        setTogglingIds((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }
    },
    [project.id]
  );

  const handleCreateRun = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedFileIds.size === 0) {
      setErrorMessage("Select at least one file to include in the run");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const isOneshot = runMode === "oneshot";
    const payload = {
      run_mode: runMode,
      research_mode: researchMode,
      instructions: instructions.trim() || undefined,
      enable_vector_store: vectorStoreEnabled,
      enable_web_search: researchMode !== "none",
      included_file_ids: Array.from(selectedFileIds),
      template_id: isOneshot && templateId ? templateId : undefined,
    };

    try {
      const response = await fetch(`/api/projects/${project.id}/runs`, {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as FetchError;
        const detail = payload.detail ?? payload.message ?? "Unable to start run";
        throw new Error(detail);
      }

      const run = (await response.json()) as RunSummary;
      setRuns((prev) => [run, ...prev]);
      router.push(`/runs/${run.id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start run";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickRegenCreated = useCallback((newRun: RunSummary) => {
    setRuns((prev) => [newRun, ...prev]);
    setQuickRegenRun(null);
  }, []);

  return (
    <div className="project-workspace" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h1>{project.name}</h1>
            <p>{project.description ?? "No description provided."}</p>
          </div>
          <Link href={`/projects/${project.id}/upload`} className="btn-secondary" style={{ alignSelf: "flex-start" }}>
            Upload files
          </Link>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <span>
            Selected files: {selectedFiles.length} / {files.length}
          </span>
          <span>
            Tokens: <strong>{totalTokens.toLocaleString()}</strong> / {TOKEN_RECOMMENDED_MAX.toLocaleString()} (recommended)
          </span>
          {totalTokens > TOKEN_RECOMMENDED_MAX ? (
            <span className="chip chip--warning">Consider summarizing more files</span>
          ) : null}
        </div>
        {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
      </div>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
          <h2>Files</h2>
          <button className="btn-secondary" type="button" onClick={toggleAllFiles}>
            {selectedFileIds.size === files.length ? "Clear selection" : "Select all"}
          </button>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: "2rem" }}>
                  <input
                    type="checkbox"
                    checked={selectedFileIds.size === files.length && files.length > 0}
                    onChange={toggleAllFiles}
                    aria-label="Toggle all files"
                  />
                </th>
                <th>Filename</th>
                <th>Size</th>
                <th>Tokens</th>
                <th>Status</th>
                <th style={{ width: "220px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {files.length === 0 ? (
                <tr>
                  <td colSpan={6}>No files uploaded yet.</td>
                </tr>
              ) : (
                files.map((file) => {
                  const selected = selectedFileIds.has(file.id);
                  const summarizing = summarizingIds.has(file.id);
                  let statusLabel = "Ready";
                  if (file.is_too_large && file.is_summarized) {
                    statusLabel = "Summarized (large file)";
                  } else if (file.is_too_large) {
                    statusLabel = "Too large";
                  } else if (file.is_summarized) {
                    statusLabel = "Summarized";
                  }
                  const usingSummary = file.use_summary_for_generation;
                  const tokenModeLabel = usingSummary ? "Using summary" : "Using native";
                  const toggling = togglingIds.has(file.id);
                  const canToggle = file.is_summarized || file.is_too_large;
                  const toggleDisabled =
                    toggling || summarizing ||
                    (file.is_too_large && usingSummary) ||
                    (!usingSummary && !file.is_summarized);

                  return (
                    <tr key={file.id} className={selected ? "table-row--active" : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleFile(file.id)}
                          aria-label={`Toggle ${file.filename}`}
                        />
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          <span>{file.filename}</span>
                          {file.summary_text ? (
                            <small style={{ color: "#6b7280" }}>Summary available</small>
                          ) : null}
                        </div>
                      </td>
                      <td>{formatBytes(file.size)}</td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          <span>{file.token_count.toLocaleString()}</span>
                          <small style={{ color: "#6b7280" }}>{tokenModeLabel}</small>
                          {usingSummary && file.native_token_count ? (
                            <small style={{ color: "#6b7280" }}>
                              Native: {file.native_token_count.toLocaleString()}
                            </small>
                          ) : null}
                          {!usingSummary && file.is_summarized ? (
                            <small style={{ color: "#6b7280" }}>
                              Summary: {file.summary_token_count.toLocaleString()}
                            </small>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                          <span>{statusLabel}</span>
                          <span className="chip chip--info">{usingSummary ? "Summary mode" : "Native mode"}</span>
                        </div>
                      </td>
                      <td style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        {!isImageFile(file.filename) ? (
                          <button
                            className="btn-secondary"
                            type="button"
                            onClick={() => handleSummarize(file.id)}
                            disabled={summarizing || file.is_summarized}
                          >
                            {summarizing ? "Summarizing…" : file.is_summarized ? "Summarized" : "Summarize"}
                          </button>
                        ) : null}
                        {canToggle ? (
                          <button
                            className="btn-secondary"
                            type="button"
                            onClick={() => handleToggleMode(file.id)}
                            disabled={toggleDisabled}
                            title={
                              file.is_too_large && usingSummary
                                ? "Large files must use the summary"
                                : !file.is_summarized && !usingSummary
                                ? "Summarize file to enable"
                                : undefined
                            }
                          >
                            {toggling ? "Updating…" : usingSummary ? "Use native" : "Use summary"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h2>Start a run</h2>
        <form onSubmit={handleCreateRun} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="run-form__grid">
            <div className="form-field">
              <label htmlFor="run-mode">Run mode</label>
              <select
                id="run-mode"
                name="run_mode"
                value={runMode}
                onChange={(event) => {
                  setRunMode(event.target.value);
                  if (event.target.value !== "oneshot") {
                    setTemplateId("");
                  }
                }}
              >
                <option value="oneshot">One shot (template + docs)</option>
                <option value="full" disabled title="Full mode temporarily disabled">Full (ingest + extraction) — Coming soon</option>
              </select>
            </div>
            {runMode === "oneshot" && (
              <div className="form-field">
                <label htmlFor="template">Template</label>
                <select
                  id="template"
                  name="template"
                  value={templateId}
                  onChange={(event) => setTemplateId(event.target.value)}
                  disabled={isLoadingTemplates}
                >
                  {isLoadingTemplates ? (
                    <option value="">Loading templates...</option>
                  ) : templates.length === 0 ? (
                    <option value="">No templates available</option>
                  ) : (
                    <>
                      <option value="">Select a template...</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                {templates.length === 0 && !isLoadingTemplates && (
                  <small style={{ color: "#6b7280" }}>
                    Templates not configured. Using default template.
                  </small>
                )}
              </div>
            )}
            <div className="form-field">
              <label htmlFor="research-mode">Research</label>
              <select
                id="research-mode"
                name="research_mode"
                value={researchMode}
                onChange={(event) => setResearchMode(event.target.value)}
              >
                <option value="none">None</option>
                <option value="quick">Quick (Claude web search)</option>
                <option value="full">Full (Perplexity)</option>
              </select>
              <small style={{ color: "#6b7280" }}>
                {runMode === "oneshot" 
                  ? "Research APIs and services mentioned in docs"
                  : "Research integration points and APIs"}
              </small>
            </div>
            <div className="form-field">
              <label htmlFor="vector-store" title="Find similar past scopes to inform estimates">
                Vector Search
              </label>
              <select
                id="vector-store"
                name="vector_store"
                value={vectorStoreEnabled ? "enabled" : "disabled"}
                onChange={(event) => setVectorStoreEnabled(event.target.value === "enabled")}
              >
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
              <small style={{ color: "#6b7280" }}>
                Find similar past scopes to inform estimates
              </small>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="instructions">Instructions</label>
            <textarea
              id="instructions"
              name="instructions"
              placeholder="Key requirements, success metrics, out-of-scope items, stakeholders, etc."
              rows={5}
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
            />
            <small style={{ color: "#6b7280" }}>Stored with the project and reused on future runs unless you clear it.</small>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
            <button className="btn-primary" type="submit" disabled={isSubmitting || selectedFileIds.size === 0}>
              {isSubmitting ? "Starting…" : "Start run"}
            </button>
          </div>
        </form>
      </section>

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h2>Runs</h2>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Status</th>
                <th>Mode</th>
                <th>Doc Type</th>
                <th>Included files</th>
                <th style={{ maxWidth: "300px" }}>Instructions</th>
                <th style={{ width: "220px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7}>No runs yet.</td>
                </tr>
              ) : (
                runs.map((run) => {
                  const chip = statusChip(run);
                  const instructionText = run.instructions || "—";
                  const includedCount = Array.isArray(run.included_file_ids) ? run.included_file_ids.length : 0;
                  const canQuickRegen = run.status.toLowerCase() === "success";

                  return (
                    <tr key={run.id}>
                      <td>{formatDate(run.created_at)}</td>
                      <td>
                        <span className={chip.className}>{chip.label}</span>
                      </td>
                      <td>{run.run_mode}</td>
                      <td>{run.template_type || "—"}</td>
                      <td>{includedCount}</td>
                      <td style={{ maxWidth: "300px", whiteSpace: "normal", wordBreak: "break-word" }}>
                        {instructionText}
                      </td>
                      <td style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        <Link className="btn-secondary" href={`/runs/${run.id}`}>
                          View
                        </Link>
                        <button
                          className="btn-secondary"
                          type="button"
                          onClick={() => setQuickRegenRun(run)}
                          disabled={!canQuickRegen}
                        >
                          Quick regen
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {quickRegenRun ? (
        <QuickRegenModal
          projectId={project.id}
          run={quickRegenRun}
          onClose={() => setQuickRegenRun(null)}
          onCreated={handleQuickRegenCreated}
        />
      ) : null}
    </div>
  );
}

export default ProjectWorkspace;

