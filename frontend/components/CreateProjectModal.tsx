"use client";

import { FormEvent, MouseEvent, useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface FormState {
  name: string;
  description: string;
  team_id: string | null;
}

interface Team {
  id: string;
  name: string;
}

export function CreateProjectModal() {
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState<FormState>({ name: "", description: "", team_id: null });
  const [error, setError] = useState<string | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsError, setTeamsError] = useState<string | null>(null);
  const [teamsLoading, setTeamsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      setTeamsLoading(true);
      setTeamsError(null);
      fetch("/api/teams", { cache: "no-store" })
        .then(async (res) => {
          if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            const detail = body?.detail || `Failed to load teams (${res.status})`;
            throw new Error(detail);
          }
          return res.json();
        })
        .then((data) => setTeams(Array.isArray(data) ? data : []))
        .catch((err: Error) => {
          console.error("Failed to load teams", err);
          setTeams([]);
          setTeamsError(err.message);
        })
        .finally(() => setTeamsLoading(false));
    }
  }, [isOpen]);

  function openModal() {
    setIsOpen(true);
  }

  function closeModal() {
    if (isSubmitting) {
      return;
    }
    setIsOpen(false);
    setForm({ name: "", description: "", team_id: null });
    setError(null);
  }

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) {
      closeModal();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const name = form.name.trim();
    const description = form.description.trim();
    const team_id = form.team_id;

    if (!name) {
      setError("Project name is required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          name,
          description: description || undefined,
          flags: {},
          team_id: team_id || undefined,
        })
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok || !payload?.id) {
        const detail = typeof payload?.detail === "string" ? payload.detail : "Unable to create project.";
        setError(detail);
        return;
      }

      closeModal();
      router.push(`/projects/${payload.id}`);
      router.refresh();
    } catch (err) {
      console.error(err);
      setError("Network error while creating project.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <button className="btn-primary" onClick={openModal} type="button">
        New project
      </button>

      {isOpen ? (
        <div className="modal-backdrop" onClick={handleBackdropClick} role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="create-project-heading">
            <form onSubmit={handleSubmit}>
              <h2 id="create-project-heading">Create project</h2>
              <div className="form-field">
                <label htmlFor="project-name">Name</label>
                <input
                  id="project-name"
                  name="name"
                  type="text"
                  maxLength={200}
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                  autoFocus
                  disabled={isSubmitting}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="project-description">Description</label>
                <textarea
                  id="project-description"
                  name="description"
                  rows={3}
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                  disabled={isSubmitting}
                />
              </div>
              {teams.length > 0 ? (
                <div className="form-field">
                  <label htmlFor="project-team">Team</label>
                  <select
                    id="project-team"
                    name="team"
                    value={form.team_id ?? ""}
                    onChange={(event) => setForm((prev) => ({ ...prev, team_id: event.target.value || null }))}
                    disabled={isSubmitting || teamsLoading}
                  >
                    <option value="">My projects (no team)</option>
                    {teams.map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                  </select>
                  {teamsError ? <small className="error-text">{teamsError}</small> : null}
                </div>
              ) : null}
              {error ? <p className="error-text">{error}</p> : null}
              <div className="modal-actions">
                <button className="btn-secondary" onClick={closeModal} type="button" disabled={isSubmitting}>
                  Cancel
                </button>
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating…" : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default CreateProjectModal;

