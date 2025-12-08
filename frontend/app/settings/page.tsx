"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

interface TeamSettings {
  team_id?: string;
  scope_prompt?: string | null;
  pso_prompt?: string | null;
  image_prompt?: string | null;
  pso_image_prompt?: string | null;
  enable_solution_image?: boolean;
  enable_pso_image?: boolean;
  scope_template_id?: string | null;
  pso_template_id?: string | null;
  vector_similar_limit?: number;
  enable_oneshot_research?: boolean;
  enable_oneshot_vector?: boolean;
  research_mode_default?: string;
  image_size?: string;
}

interface Team {
  id: string;
  name: string;
  owner_id: string;
}

export default function SettingsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const [settings, setSettings] = useState<TeamSettings>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load teams on mount
  useEffect(() => {
    fetch("/api/teams")
      .then((res) => res.json())
      .then((data) => {
        setTeams(data || []);
        if (data && data.length > 0) {
          setSelectedTeamId(data[0].id);
        }
        setIsLoading(false);
      })
      .catch(() => {
        setTeams([]);
        setIsLoading(false);
      });
  }, []);

  // Load settings when team changes
  useEffect(() => {
    if (!selectedTeamId) return;
    
    setIsLoading(true);
    fetch(`/api/teams/${selectedTeamId}/settings`)
      .then((res) => res.json())
      .then((data) => {
        setSettings(data || {});
        setIsLoading(false);
      })
      .catch(() => {
        setSettings({});
        setIsLoading(false);
      });
  }, [selectedTeamId]);

  const handleSave = useCallback(async () => {
    if (!selectedTeamId) return;
    
    setIsSaving(true);
    setMessage(null);
    
    try {
      const response = await fetch(`/api/teams/${selectedTeamId}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      
      if (!response.ok) {
        throw new Error("Failed to save settings");
      }
      
      const data = await response.json();
      setSettings(data);
      setMessage({ type: "success", text: "Settings saved successfully" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to save" });
    } finally {
      setIsSaving(false);
    }
  }, [selectedTeamId, settings]);

  const updateSetting = <K extends keyof TeamSettings>(key: K, value: TeamSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  if (isLoading && teams.length === 0) {
    return (
      <div className="card" style={{ maxWidth: 800, margin: "0 auto" }}>
        <h1>Team Settings</h1>
        <p>Loading...</p>
      </div>
    );
  }

  if (teams.length === 0) {
    return (
      <div className="card" style={{ maxWidth: 800, margin: "0 auto" }}>
        <h1>Team Settings</h1>
        <p>You are not a member of any teams.</p>
        <Link href="/projects" className="btn-secondary">
          Back to Projects
        </Link>
      </div>
    );
  }

  return (
    <div className="card" style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Team Settings</h1>
        <Link href="/projects" className="btn-secondary">
          Back to Projects
        </Link>
      </div>

      {message && (
        <div className={message.type === "success" ? "success-text" : "error-text"}>
          {message.text}
        </div>
      )}

      <div className="form-field">
        <label htmlFor="team-select">Team</label>
        <select
          id="team-select"
          value={selectedTeamId}
          onChange={(e) => setSelectedTeamId(e.target.value)}
        >
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

      <section>
        <h2>Generation Defaults</h2>
        
        <div className="form-field">
          <label htmlFor="research-default">Default Research Mode</label>
          <select
            id="research-default"
            value={settings.research_mode_default || "quick"}
            onChange={(e) => updateSetting("research_mode_default", e.target.value)}
          >
            <option value="none">None</option>
            <option value="quick">Quick (Claude web search)</option>
            <option value="full">Full (Perplexity)</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="vector-limit">Vector Search Results Limit</label>
          <input
            id="vector-limit"
            type="number"
            min={1}
            max={10}
            value={settings.vector_similar_limit || 3}
            onChange={(e) => updateSetting("vector_similar_limit", parseInt(e.target.value) || 3)}
          />
          <small style={{ color: "#9ca3af" }}>Number of similar past scopes to use as context</small>
        </div>

        <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_oneshot_research ?? true}
              onChange={(e) => updateSetting("enable_oneshot_research", e.target.checked)}
            />
            Enable research for one-shot mode
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_oneshot_vector ?? true}
              onChange={(e) => updateSetting("enable_oneshot_vector", e.target.checked)}
            />
            Enable vector search for one-shot mode
          </label>
        </div>
      </section>

      <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

      <section>
        <h2>Templates</h2>
        
        <div className="form-field">
          <label htmlFor="scope-template">Scope Template (Google Doc ID)</label>
          <input
            id="scope-template"
            type="text"
            value={settings.scope_template_id || ""}
            onChange={(e) => updateSetting("scope_template_id", e.target.value || null)}
            placeholder="e.g., 1abc123..."
          />
          <small style={{ color: "#9ca3af" }}>Google Doc ID for the default scope template</small>
        </div>

        <div className="form-field">
          <label htmlFor="pso-template">PSO Template (Google Doc ID)</label>
          <input
            id="pso-template"
            type="text"
            value={settings.pso_template_id || ""}
            onChange={(e) => updateSetting("pso_template_id", e.target.value || null)}
            placeholder="e.g., 1abc123..."
          />
          <small style={{ color: "#9ca3af" }}>Google Doc ID for the PSO template</small>
        </div>
      </section>

      <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

      <section>
        <h2>Image Generation</h2>
        <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginTop: "-0.5rem" }}>
          Configure Nano Banana Pro (Gemini) image generation for scope documents.
        </p>

        <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_solution_image ?? false}
              onChange={(e) => updateSetting("enable_solution_image", e.target.checked)}
            />
            Enable solution images for scopes
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_pso_image ?? false}
              onChange={(e) => updateSetting("enable_pso_image", e.target.checked)}
            />
            Enable comparison images for PSO
          </label>
        </div>

        <div className="form-field">
          <label htmlFor="image-size">Image Size</label>
          <select
            id="image-size"
            value={settings.image_size || "1024x1024"}
            onChange={(e) => updateSetting("image_size", e.target.value)}
          >
            <option value="1024x1024">1024x1024</option>
            <option value="1792x1024">1792x1024 (Wide)</option>
            <option value="1024x1792">1024x1792 (Tall)</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="image-prompt">Scope Image Prompt</label>
          <textarea
            id="image-prompt"
            rows={4}
            value={settings.image_prompt || ""}
            onChange={(e) => updateSetting("image_prompt", e.target.value || null)}
            placeholder="Custom prompt for generating scope solution images..."
          />
          <small style={{ color: "#9ca3af" }}>Use {"{solution_text}"} as placeholder for the proposed solution content</small>
        </div>

        <div className="form-field">
          <label htmlFor="pso-image-prompt">PSO Image Prompt</label>
          <textarea
            id="pso-image-prompt"
            rows={4}
            value={settings.pso_image_prompt || ""}
            onChange={(e) => updateSetting("pso_image_prompt", e.target.value || null)}
            placeholder="Custom prompt for generating PSO comparison matrix images..."
          />
          <small style={{ color: "#9ca3af" }}>Use {"{solutions_text}"} as placeholder for the solution breakdown content</small>
        </div>
      </section>

      <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

      <section>
        <h2>Custom Prompts</h2>

        <div className="form-field">
          <label htmlFor="scope-prompt">Scope Generation Prompt (Additional)</label>
          <textarea
            id="scope-prompt"
            rows={4}
            value={settings.scope_prompt || ""}
            onChange={(e) => updateSetting("scope_prompt", e.target.value || null)}
            placeholder="Additional instructions to append to scope generation prompts..."
          />
        </div>

        <div className="form-field">
          <label htmlFor="pso-prompt">PSO Generation Prompt (Additional)</label>
          <textarea
            id="pso-prompt"
            rows={4}
            value={settings.pso_prompt || ""}
            onChange={(e) => updateSetting("pso_prompt", e.target.value || null)}
            placeholder="Additional instructions to append to PSO generation prompts..."
          />
        </div>
      </section>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1rem" }}>
        <button
          className="btn-primary"
          onClick={handleSave}
          disabled={isSaving || !selectedTeamId}
        >
          {isSaving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}

