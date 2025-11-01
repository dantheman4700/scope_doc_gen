"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { RunSummary } from "@/types/backend";

interface QuickRegenModalProps {
  projectId: string;
  run: RunSummary;
  onClose: () => void;
  onCreated?: (run: RunSummary) => void;
}

interface FetchError {
  detail?: string;
  message?: string;
}

export function QuickRegenModal({ projectId, run, onClose, onCreated }: QuickRegenModalProps) {
  const router = useRouter();
  const [changes, setChanges] = useState<string>("");
  const [vectorStoreEnabled, setVectorStoreEnabled] = useState<boolean>(() => {
    const params = (run.params ?? {}) as Record<string, unknown>;
    const value = params.enable_vector_store;
    return typeof value === "boolean" ? value : true;
  });
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const changeText = changes.trim();
    if (!changeText) {
      setError("Describe what you want to change");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const params = (run.params ?? {}) as Record<string, unknown>;
    const payload = {
      parent_run_id: run.id,
      run_mode: "fast",
      research_mode: typeof params.research_mode === "string" ? (params.research_mode as string) : run.research_mode,
      instructions: run.instructions ?? undefined,
      enable_vector_store: vectorStoreEnabled,
      enable_web_search: typeof params.enable_web_search === "boolean" ? (params.enable_web_search as boolean) : true,
      included_file_ids: run.included_file_ids ?? [],
      what_to_change: changeText
    };

    try {
      const response = await fetch(`/api/projects/${projectId}/runs`, {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as FetchError;
        const detail = payload.detail ?? payload.message ?? "Quick regeneration failed";
        throw new Error(detail);
      }

      const newRun = (await response.json()) as RunSummary;
      if (onCreated) {
        onCreated(newRun);
      }
      router.push(`/runs/${newRun.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Quick regeneration failed";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="card" style={{ maxWidth: 520, width: "100%", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h2 style={{ margin: 0 }}>Quick regenerate scope</h2>
        <p style={{ color: "#6b7280" }}>
          Update the previously extracted variables without reprocessing all documents. Describe the adjustments you want to
          make and the system will apply them to the stored variables from run <code>{run.id}</code>.
        </p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="form-field">
            <label htmlFor="quick-regenerate-changes">What should change?</label>
            <textarea
              id="quick-regenerate-changes"
              name="changes"
              value={changes}
              onChange={(event) => setChanges(event.target.value)}
              rows={5}
              placeholder="Example: Update pricing for the enterprise tier to $12k/mo and extend the implementation timeline by two weeks."
            />
          </div>

          <div className="form-field">
            <label htmlFor="quick-regenerate-vector">Vector store</label>
            <select
              id="quick-regenerate-vector"
              name="vector_store"
              value={vectorStoreEnabled ? "enabled" : "disabled"}
              onChange={(event) => setVectorStoreEnabled(event.target.value === "enabled")}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>

          {error ? <p className="error-text">{error}</p> : null}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
            <button className="btn-secondary" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="btn-primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Starting…" : "Start quick regen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default QuickRegenModal;

