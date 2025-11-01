"use client";

import { useCallback, useMemo, useState } from "react";
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

export function ProjectWorkspace({ project, initialFiles, initialRuns }: ProjectWorkspaceProps) {
  const router = useRouter();
  const [files, setFiles] = useState<ProjectFile[]>(initialFiles);
  const [runs, setRuns] = useState<RunSummary[]>(initialRuns);
  const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(
    () => new Set(initialFiles.map((file) => file.id))
  );
  const [quickRegenRun, setQuickRegenRun] = useState<RunSummary | null>(null);
  const [instructions, setInstructions] = useState<string>("");
  const [researchMode, setResearchMode] = useState<string>("quick");
  const [vectorStoreEnabled, setVectorStoreEnabled] = useState<boolean>(true);
  const [saveIntermediate, setSaveIntermediate] = useState<boolean>(true);
  const [forceResummarize, setForceResummarize] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [summarizingIds, setSummarizingIds] = useState<Set<string>>(new Set());

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

  const handleUseRunAsTemplate = useCallback(
    (run: RunSummary) => {
      if (run.instructions) {
        setInstructions(run.instructions);
      }
      if (Array.isArray(run.included_file_ids) && run.included_file_ids.length > 0) {
        setSelectedFileIds(new Set(run.included_file_ids));
      }

      const params = (run.params ?? {}) as Record<string, unknown>;
      const researchModeParam = params.research_mode;
      if (typeof researchModeParam === "string") {
        setResearchMode(researchModeParam);
      } else {
        setResearchMode(run.research_mode);
      }

      const enableVectorStoreParam = params.enable_vector_store;
      if (typeof enableVectorStoreParam === "boolean") {
        setVectorStoreEnabled(enableVectorStoreParam);
      }

      const saveIntermediateParam = params.save_intermediate;
      if (typeof saveIntermediateParam === "boolean") {
        setSaveIntermediate(saveIntermediateParam);
      }

      const forceResummarizeParam = params.force_resummarize;
      if (typeof forceResummarizeParam === "boolean") {
        setForceResummarize(forceResummarizeParam);
      }
    },
    []
  );

  const handleCreateRun = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedFileIds.size === 0) {
      setErrorMessage("Select at least one file to include in the run");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const payload = {
      run_mode: "full",
      research_mode: researchMode,
      force_resummarize: forceResummarize,
      save_intermediate: saveIntermediate,
      instructions: instructions.trim() || undefined,
      enable_vector_store: vectorStoreEnabled,
      enable_web_search: researchMode !== "none",
      included_file_ids: Array.from(selectedFileIds)
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
                <th style={{ width: "140px" }}>Actions</th>
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
                      <td>{file.token_count.toLocaleString()}</td>
                      <td>{statusLabel}</td>
                      <td style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          className="btn-secondary"
                          type="button"
                          onClick={() => handleSummarize(file.id)}
                          disabled={summarizing || file.is_summarized}
                        >
                          {summarizing ? "Summarizing…" : file.is_summarized ? "Summarized" : "Summarize"}
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

      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h2>Start a run</h2>
        <form onSubmit={handleCreateRun} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="run-form__grid">
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
            </div>
            <div className="form-field">
              <label htmlFor="vector-store">Vector store</label>
              <select
                id="vector-store"
                name="vector_store"
                value={vectorStoreEnabled ? "enabled" : "disabled"}
                onChange={(event) => setVectorStoreEnabled(event.target.value === "enabled")}
              >
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="save-intermediate">Save intermediate variables</label>
              <select
                id="save-intermediate"
                name="save_intermediate"
                value={saveIntermediate ? "yes" : "no"}
                onChange={(event) => setSaveIntermediate(event.target.value === "yes")}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="force-summarize">Force resummarize inputs</label>
              <select
                id="force-summarize"
                name="force_resummarize"
                value={forceResummarize ? "yes" : "no"}
                onChange={(event) => setForceResummarize(event.target.value === "yes")}
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
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
                <th>Included files</th>
                <th>Instructions</th>
                <th style={{ width: "220px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={6}>No runs yet.</td>
                </tr>
              ) : (
                runs.map((run) => {
                  const chip = statusChip(run);
                  const instructionPreview = run.instructions
                    ? `${run.instructions.slice(0, 120)}${run.instructions.length > 120 ? "…" : ""}`
                    : "—";
                  const includedCount = Array.isArray(run.included_file_ids) ? run.included_file_ids.length : 0;
                  const canQuickRegen = run.status.toLowerCase() === "success";

                  return (
                    <tr key={run.id}>
                      <td>{formatDate(run.created_at)}</td>
                      <td>
                        <span className={chip.className}>{chip.label}</span>
                      </td>
                      <td>{run.run_mode}</td>
                      <td>{includedCount}</td>
                      <td>{instructionPreview}</td>
                      <td style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        <Link className="btn-secondary" href={`/runs/${run.id}`}>
                          View
                        </Link>
                        <button
                          className="btn-secondary"
                          type="button"
                          onClick={() => handleUseRunAsTemplate(run)}
                        >
                          Use as template
                        </button>
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

