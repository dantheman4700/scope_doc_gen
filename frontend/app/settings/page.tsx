"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

// Default settings values
const DEFAULT_SETTINGS: TeamSettings = {
  research_mode_default: "quick",
  vector_similar_limit: 3,
  enable_oneshot_research: true,
  enable_oneshot_vector: true,
  enable_solution_image: true,
  enable_pso_image: true,
  image_resolution: "4K",
  image_aspect_ratio: "auto",
  scope_template_id: "1GTrMfUm0fswd_OMc7HAvERSmJpiEsgw9nY6JMQOFvI4",
  pso_template_id: "1q25z5wUxsvaFC1oVHZ8QlLXPIB0j0eWubKn_aFINjAo",
  scope_prompt: null,
  pso_prompt: null,
  image_prompt: null,
  pso_image_prompt: null,
};

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
  image_resolution?: string;
  image_aspect_ratio?: string;
}

interface Team {
  id: string;
  name: string;
  owner_id: string;
}

interface GoogleConnectionStatus {
  connected: boolean;
  email: string | null;
  can_export: boolean;
}

// Inner component that uses searchParams
function SettingsContent() {
  const searchParams = useSearchParams();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>("");
  const [settings, setSettings] = useState<TeamSettings>(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [googleStatus, setGoogleStatus] = useState<GoogleConnectionStatus | null>(null);
  const [isConnectingGoogle, setIsConnectingGoogle] = useState(false);

  // Check for Google OAuth callback messages
  useEffect(() => {
    if (searchParams.get("google_connected") === "true") {
      setMessage({ type: "success", text: "Google account connected successfully!" });
      // Refresh google status
      fetch("/api/google-oauth/status")
        .then((res) => res.json())
        .then(setGoogleStatus)
        .catch(() => {});
    } else if (searchParams.get("google_error")) {
      setMessage({ type: "error", text: `Google connection failed: ${searchParams.get("google_error")}` });
    }
  }, [searchParams]);

  // Load teams and Google status on mount
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
    
    // Load Google connection status
    fetch("/api/google-oauth/status")
      .then((res) => res.json())
      .then(setGoogleStatus)
      .catch(() => setGoogleStatus(null));
  }, []);

  // Load settings when team changes - merge with defaults
  useEffect(() => {
    if (!selectedTeamId) return;
    
    setIsLoading(true);
    fetch(`/api/teams/${selectedTeamId}/settings`)
      .then((res) => res.json())
      .then((data) => {
        // Merge fetched settings with defaults
        setSettings({ ...DEFAULT_SETTINGS, ...(data || {}) });
        setIsLoading(false);
      })
      .catch(() => {
        setSettings(DEFAULT_SETTINGS);
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
      setSettings({ ...DEFAULT_SETTINGS, ...data });
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
    <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* User Settings Card */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0 }}>👤 User Settings</h1>
          <Link href="/projects" className="btn-secondary">
            Back to Projects
          </Link>
        </div>

        {message && (
          <div className={message.type === "success" ? "success-text" : "error-text"}>
            {message.text}
          </div>
        )}

        <section>
          <h2>Google Account Connection</h2>
          <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginTop: "-0.5rem" }}>
            Connect your personal Google account to export scopes directly to your Google Drive.
          </p>

          <div style={{ 
            padding: "1rem", 
            background: googleStatus?.connected ? "#064e3b" : "#1f2937", 
            borderRadius: "0.5rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "1rem"
          }}>
            <div>
              {googleStatus?.connected ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#10b981" }}>
                    <span>✓</span>
                    <strong>Google Account Connected</strong>
                  </div>
                  {googleStatus.email && (
                    <small style={{ color: "#9ca3af" }}>{googleStatus.email}</small>
                  )}
                </>
              ) : (
                <>
                  <div style={{ color: "#9ca3af" }}>No Google account connected</div>
                  <small style={{ color: "#6b7280" }}>Connect to enable direct exports to your Drive</small>
                </>
              )}
            </div>

            {googleStatus?.connected ? (
              <button
                className="btn-secondary"
                onClick={async () => {
                  setIsConnectingGoogle(true);
                  try {
                    const res = await fetch("/api/google-oauth/disconnect", { method: "POST" });
                    if (res.ok) {
                      setGoogleStatus({ connected: false, email: null, can_export: false });
                      setMessage({ type: "success", text: "Google account disconnected" });
                    }
                  } catch {
                    setMessage({ type: "error", text: "Failed to disconnect" });
                  } finally {
                    setIsConnectingGoogle(false);
                  }
                }}
                disabled={isConnectingGoogle}
              >
                Disconnect
              </button>
            ) : (
              <button
                className="btn-primary"
                onClick={async () => {
                  setIsConnectingGoogle(true);
                  try {
                    const res = await fetch("/api/google-oauth/connect");
                    const data = await res.json();
                    if (data.authorization_url) {
                      window.location.href = data.authorization_url;
                    }
                  } catch {
                    setMessage({ type: "error", text: "Failed to initiate connection" });
                    setIsConnectingGoogle(false);
                  }
                }}
                disabled={isConnectingGoogle}
              >
                {isConnectingGoogle ? "Connecting..." : "Connect Google Account"}
              </button>
            )}
          </div>
        </section>
      </div>

      {/* Team Settings Card */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <h1 style={{ margin: 0 }}>🏢 Team Settings</h1>

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
            value={settings.research_mode_default}
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
            value={settings.vector_similar_limit}
            onChange={(e) => updateSetting("vector_similar_limit", parseInt(e.target.value) || 3)}
          />
          <small style={{ color: "#9ca3af" }}>Number of similar past scopes to use as context</small>
        </div>

        <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_oneshot_research}
              onChange={(e) => updateSetting("enable_oneshot_research", e.target.checked)}
            />
            Enable research for one-shot mode
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_oneshot_vector}
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
              checked={settings.enable_solution_image}
              onChange={(e) => updateSetting("enable_solution_image", e.target.checked)}
            />
            Enable solution images for scopes
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={settings.enable_pso_image}
              onChange={(e) => updateSetting("enable_pso_image", e.target.checked)}
            />
            Enable comparison images for PSO
          </label>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div className="form-field">
            <label htmlFor="image-resolution">Resolution</label>
            <select
              id="image-resolution"
              value={settings.image_resolution}
              onChange={(e) => updateSetting("image_resolution", e.target.value)}
            >
              <option value="1K">1K</option>
              <option value="2K">2K</option>
              <option value="4K">4K</option>
            </select>
          </div>

          <div className="form-field">
            <label htmlFor="image-aspect-ratio">Aspect Ratio</label>
            <select
              id="image-aspect-ratio"
              value={settings.image_aspect_ratio}
              onChange={(e) => updateSetting("image_aspect_ratio", e.target.value)}
            >
              <option value="auto">Auto</option>
              <option value="1:1">1:1 (Square)</option>
              <option value="16:9">16:9 (Wide)</option>
              <option value="9:16">9:16 (Tall)</option>
              <option value="4:3">4:3</option>
              <option value="3:4">3:4</option>
            </select>
          </div>
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
          {isSaving ? "Saving..." : "Save Team Settings"}
        </button>
      </div>
      </div>
    </div>
  );
}

// Wrapper component with Suspense boundary for useSearchParams
export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="card" style={{ maxWidth: 800, margin: "0 auto" }}>
        <h1>Team Settings</h1>
        <p>Loading...</p>
      </div>
    }>
      <SettingsContent />
    </Suspense>
  );
}
