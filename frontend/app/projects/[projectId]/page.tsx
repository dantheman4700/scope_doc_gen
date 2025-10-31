import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { requireUser } from "@/lib/auth";
import { fetchProject, fetchProjectFiles, fetchProjectRuns } from "@/lib/projects.server";
import { apiFetchJson } from "@/lib/fetch";
import type { RunSummary } from "@/types/backend";

interface ProjectDetailPageProps {
  params: { projectId: string };
}

export const metadata = {
  title: "Project · Scope Doc"
};

export default async function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  await requireUser();
  const project = await fetchProject(params.projectId);
  if (!project) {
    notFound();
  }
  const projectId = project.id;

  const [files, runs] = await Promise.all([
    fetchProjectFiles(projectId),
    fetchProjectRuns(projectId)
  ]);

  async function startRun(formData: FormData) {
    "use server";

    const instructions = (formData.get("instructions") as string | null)?.trim();
    const projectIdentifier = (formData.get("project_identifier") as string | null)?.trim();

    const runMode = (formData.get("run_mode") as string) ?? "full";
    const researchMode = (formData.get("research_mode") as string) ?? "quick";
    const enableWebSearch = researchMode !== "none";

    const payload = {
      run_mode: runMode,
      research_mode: researchMode,
      force_resummarize: formData.get("force_resummarize") === "on",
      save_intermediate: formData.get("save_intermediate") === "on",
      enable_vector_store: true,
      enable_web_search: enableWebSearch,
      project_identifier: projectIdentifier || undefined,
      instructions: instructions || undefined
    };

    const response = await apiFetchJson<RunSummary>(`/projects/${projectId}/runs`, {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (response.status >= 400 || !response.data) {
      throw new Error("Unable to start run");
    }

    redirect(`/runs/${response.data.id}`);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <h1>{project.name}</h1>
            <p>{project.description ?? "No description provided."}</p>
          </div>
          <Link href={`/projects/${project.id}/upload`} className="btn-secondary" style={{ alignSelf: "flex-start" }}>
            Upload files
          </Link>
        </div>

        <form action={startRun} className="run-form">
          <div className="run-form__grid">
            <div className="form-field">
              <label htmlFor="project-identifier">Project identifier (optional)</label>
              <input id="project-identifier" name="project_identifier" type="text" placeholder="e.g. Client X · CRM Revamp" />
            </div>
            <div className="form-field">
              <label htmlFor="run-mode">Run mode</label>
              <select id="run-mode" name="run_mode" defaultValue="full">
                <option value="full">Full regeneration</option>
                <option value="fast">Fast (reuse cached summaries)</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="research-mode">Research</label>
              <select id="research-mode" name="research_mode" defaultValue="quick">
                <option value="none">None</option>
                <option value="quick">Quick (Claude web search)</option>
                <option value="full">Full (Perplexity)</option>
              </select>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="instructions">Instructions</label>
            <textarea
              id="instructions"
              name="instructions"
              rows={5}
              placeholder="Key requirements, success metrics, out-of-scope items, stakeholders, etc."
            />
            <small style={{ color: "#6b7280" }}>Stored with the project and reused on future runs unless you clear it.</small>
          </div>

          <div className="run-form__toggles">
            <label className="toggle">
              <input type="checkbox" name="save_intermediate" defaultChecked />
              <span>
                Save intermediate variables
                <small>Writes `extracted_variables.json` for review.</small>
              </span>
            </label>
            <label className="toggle">
              <input type="checkbox" name="force_resummarize" />
              <span>
                Force resummarize inputs
                <small>Ignores cached per-file summaries even in fast mode.</small>
              </span>
            </label>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
            <button className="btn-primary" type="submit">
              Start run
            </button>
          </div>
        </form>
      </div>

      <section className="card">
        <h2>Files</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Size</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {files.length === 0 ? (
              <tr>
                <td colSpan={3}>No files uploaded yet.</td>
              </tr>
            ) : (
              files.map((file) => (
                <tr key={file.id}>
                  <td>{file.filename}</td>
                  <td>{formatFileSize(file.size)}</td>
                  <td>{new Date(file.created_at).toLocaleString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Runs</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Started</th>
              <th>Status</th>
              <th>Mode</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={4}>No runs yet.</td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.id}>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>{run.status}</td>
                  <td>{run.run_mode}</td>
                  <td>
                    <Link href={`/runs/${run.id}`}>View details</Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

