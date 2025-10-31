"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { fetchProjects } from "@/lib/projects.client";
import { Project, SearchResult } from "@/types/backend";

export default function SearchPageClient() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);
  const [projects, setProjects] = useState<Project[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchProjects()
      .then((data) => {
        if (!cancelled) {
          setProjects(data);
        }
      })
      .catch((err) => {
        console.error("Failed to load projects", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setHasSearched(true);

    try {
      const requestPayload: Record<string, unknown> = {
        query,
        top_k: topK
      };
      if (projectId) {
        requestPayload.project_id = projectId;
      }
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(requestPayload)
      });

      if (!response.ok) {
        if (response.status === 401) {
          window.location.assign("/login");
          return;
        }
        const errorBody = await response.json().catch(() => ({}));
        setError(errorBody?.detail ?? "Search failed");
        setBusy(false);
        return;
      }

      const data = await response.json();
      setResults(data.results ?? []);
      setBusy(false);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search scope library"
          required
        />
        <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
          <option value="">All projects</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <label className="search-form__topk">
          Top K
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          />
        </label>
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>
      {error ? <p style={{ color: "#dc2626" }}>{error}</p> : null}
      <div className="search-results">
        {busy ? (
          <p>Searching…</p>
        ) : results.length === 0 ? (
          <p>{hasSearched ? "No matches found." : "Run a query to search your scope library."}</p>
        ) : (
          results.map((result) => <SearchResultCard key={result.embedding_id} result={result} projects={projects} />)
        )}
      </div>
    </div>
  );
}

function SearchResultCard({ result, projects }: { result: SearchResult; projects: Project[] }) {
  const projectName = useMemo(() => {
    if (result.metadata?.project_name && typeof result.metadata.project_name === "string") {
      return result.metadata.project_name;
    }
    if (!result.project_id) {
      return "Unknown project";
    }
    const project = projects.find((p) => p.id === result.project_id);
    return project?.name ?? result.project_id;
  }, [result, projects]);

  const runId = typeof result.metadata?.run_id === "string" ? result.metadata.run_id : null;
  const path = typeof result.metadata?.path === "string" ? result.metadata.path : null;
  const summary = summarizeMeta(result.metadata ?? {});
  const similarity = `${(result.similarity * 100).toFixed(2)}%`;

  return (
    <div className="search-result">
      <div className="search-result__header">
        <h3>{result.doc_kind}</h3>
        <span>{projectName}</span>
      </div>
      <p className="search-result__meta">
        <span>Similarity: {similarity}</span>
        {path ? <span>Path: {path}</span> : null}
      </p>
      <details className="search-result__details">
        <summary>Metadata</summary>
        <pre>{summary}</pre>
      </details>
      <div className="search-result__actions">
        {runId ? (
          <a className="btn-primary" href={`/runs/${runId}`}>
            View run
          </a>
        ) : null}
      </div>
    </div>
  );
}

function summarizeMeta(meta: Record<string, unknown>): string {
  if (!meta || Object.keys(meta).length === 0) {
    return "{}";
  }
  return JSON.stringify(meta, null, 2);
}

