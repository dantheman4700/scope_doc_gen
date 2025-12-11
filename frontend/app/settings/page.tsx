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

interface RoadmapItem {
  text: string;
  completed: boolean;
}

interface RoadmapSection {
  category: string;
  items: RoadmapItem[];
}

interface RoadmapConfig {
  sections: RoadmapSection[];
}

// Default roadmap items to pre-populate editor
const DEFAULT_ROADMAP_ITEMS: RoadmapSection[] = [
  { category: "UI/UX", items: [
    { text: "Refresh/cache bugs", completed: false },
    { text: "Revert SSR", completed: false },
    { text: "Navigation improvements", completed: false },
    { text: "Component alignment", completed: false },
    { text: "Fluid UX", completed: false }
  ]},
  { category: "Image Generation", items: [
    { text: "Auto-insert into DOCX/Google Docs", completed: false },
    { text: "Standardized graphics", completed: false },
    { text: "Brand matching", completed: false }
  ]},
  { category: "Google Docs Export", items: [
    { text: "Integrate markgdoc for complex markdown", completed: true },
    { text: "Inline editing of created Google Docs for quick regen", completed: false },
    { text: "OAuth to allow all Google users (not just test users)", completed: false }
  ]},
  { category: "Auto-outreach", items: [
    { text: "Slack integration for expert responses", completed: false },
    { text: "Email for client questions", completed: false }
  ]},
  { category: "Document Ingestion", items: [
    { text: "Fix token counting for complex files", completed: false },
    { text: "Increase recommended limits", completed: false },
    { text: "Multi-turn/Sonnet 4.5 1M mode", completed: false }
  ]},
  { category: "Admin", items: [
    { text: "Team/org settings control panel", completed: true },
    { text: "Improved settings", completed: false },
    { text: "Improved permissions hierarchies", completed: false }
  ]},
  { category: "Account", items: [
    { text: "Password reset option", completed: false }
  ]},
  { category: "API", items: [
    { text: "Full API with keys for external integration", completed: false }
  ]},
  { category: "Vector Store", items: [
    { text: "Validate full history pipeline", completed: false },
    { text: "Embeddings viewer/editor", completed: false },
    { text: "Easy past doc uploads", completed: false }
  ]},
  { category: "Questions", items: [
    { text: "Improved visuals", completed: false },
    { text: "Per-question response forms", completed: false },
    { text: "Confidence scoring", completed: false }
  ]},
  { category: "Chatbot", items: [
    { text: "Per-project chatbot experience", completed: false },
    { text: "Per-team chatbot experience", completed: false }
  ]},
  { category: "Multi-Scope", items: [
    { text: "Generate multiple scopes at once from the same inputs", completed: false }
  ]},
  { category: "PSO → Scope", items: [
    { text: "Reference previous PSO as source for scope generation", completed: false }
  ]},
  { category: "Auto-detect", items: [
    { text: "High-confidence solutions with quick-start buttons for scoping", completed: false }
  ]}
];

// Helper to merge user items with defaults (preserves user additions, updates completed status)
function mergeRoadmapWithDefaults(apiData: RoadmapSection[]): RoadmapSection[] {
  // If API returned data with items, use it as-is
  if (apiData && apiData.length > 0) {
    return apiData;
  }
  // Otherwise return defaults
  return DEFAULT_ROADMAP_ITEMS;
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
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [roadmap, setRoadmap] = useState<RoadmapConfig>({ sections: [] });
  const [isLoadingRoadmap, setIsLoadingRoadmap] = useState(false);
  const [isSavingRoadmap, setIsSavingRoadmap] = useState(false);
  const [roadmapMessage, setRoadmapMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newItemTexts, setNewItemTexts] = useState<Record<number, string>>({});
  const [defaultTeamId, setDefaultTeamId] = useState<string>("");
  const [isSavingPreferences, setIsSavingPreferences] = useState(false);
  const [preferencesMessage, setPreferencesMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

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

  // Load teams, Google status, and user preferences on mount
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
    
    // Load user preferences
    fetch("/api/auth/preferences")
      .then((res) => res.json())
      .then((data) => {
        if (data?.default_team_id) {
          setDefaultTeamId(data.default_team_id);
        }
      })
      .catch(() => {});
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
    
    // Load global roadmap (shared across all teams)
    setIsLoadingRoadmap(true);
    fetch(`/api/system/roadmap`)
      .then((res) => res.json())
      .then((data) => {
        // If API returns empty or no sections, use defaults
        if (data?.sections && data.sections.length > 0) {
          setRoadmap(data);
        } else {
          setRoadmap({ sections: DEFAULT_ROADMAP_ITEMS });
        }
        setIsLoadingRoadmap(false);
      })
      .catch(() => {
        // On error, also pre-populate with defaults
        setRoadmap({ sections: DEFAULT_ROADMAP_ITEMS });
        setIsLoadingRoadmap(false);
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
          <h2>Default Team</h2>
          <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginTop: "-0.5rem" }}>
            Set your default team for creating new projects.
          </p>

          {preferencesMessage && (
            <div className={preferencesMessage.type === "success" ? "success-text" : "error-text"} style={{ marginBottom: "0.75rem" }}>
              {preferencesMessage.text}
            </div>
          )}

          <div className="form-field">
            <label htmlFor="default-team">Default Team</label>
            <select
              id="default-team"
              value={defaultTeamId}
              onChange={(e) => setDefaultTeamId(e.target.value)}
              disabled={teams.length === 0}
            >
              <option value="">No default (choose each time)</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn-primary"
            onClick={async () => {
              setIsSavingPreferences(true);
              setPreferencesMessage(null);

              try {
                const res = await fetch("/api/auth/preferences", {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    default_team_id: defaultTeamId || null,
                  }),
                });

                if (!res.ok) {
                  const data = await res.json();
                  // Handle both string and array error formats from FastAPI
                  let errorMessage = "Failed to save preferences";
                  if (data.detail) {
                    if (Array.isArray(data.detail)) {
                      // FastAPI validation error format: [{loc: [...], msg: "...", type: "..."}]
                      errorMessage = data.detail.map((e: { msg?: string; message?: string }) => e.msg || e.message || "Validation error").join(", ");
                    } else if (typeof data.detail === "string") {
                      errorMessage = data.detail;
                    } else if (typeof data.detail === "object") {
                      errorMessage = JSON.stringify(data.detail);
                    }
                  }
                  throw new Error(errorMessage);
                }

                setPreferencesMessage({ type: "success", text: "Preferences saved successfully" });
              } catch (error) {
                setPreferencesMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to save preferences" });
              } finally {
                setIsSavingPreferences(false);
              }
            }}
            disabled={isSavingPreferences}
          >
            {isSavingPreferences ? "Saving..." : "Save Preferences"}
          </button>
        </section>

        <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

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

        <hr style={{ border: "none", borderTop: "1px solid #374151", margin: "0.5rem 0" }} />

        <section>
          <h2>Change Password</h2>
          <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginTop: "-0.5rem" }}>
            Update your account password.
          </p>

          {passwordMessage && (
            <div className={passwordMessage.type === "success" ? "success-text" : "error-text"} style={{ marginBottom: "0.75rem" }}>
              {passwordMessage.text}
            </div>
          )}

          <div className="form-field">
            <label htmlFor="current-password">Current Password</label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
            />
          </div>

          <div className="form-field">
            <label htmlFor="new-password">New Password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
            />
          </div>

          <div className="form-field">
            <label htmlFor="confirm-password">Confirm New Password</label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
            />
          </div>

          <button
            className="btn-primary"
            onClick={async () => {
              if (!currentPassword || !newPassword || !confirmPassword) {
                setPasswordMessage({ type: "error", text: "All fields are required" });
                return;
              }
              if (newPassword !== confirmPassword) {
                setPasswordMessage({ type: "error", text: "New passwords do not match" });
                return;
              }
              if (newPassword.length < 8) {
                setPasswordMessage({ type: "error", text: "Password must be at least 8 characters" });
                return;
              }

              setIsChangingPassword(true);
              setPasswordMessage(null);

              try {
                const res = await fetch("/api/auth/change-password", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                  }),
                });

                if (!res.ok) {
                  const data = await res.json();
                  // Handle both string and array error formats from FastAPI
                  let errorMessage = "Failed to change password";
                  if (data.detail) {
                    if (Array.isArray(data.detail)) {
                      errorMessage = data.detail.map((e: { msg?: string; message?: string }) => e.msg || e.message || "Validation error").join(", ");
                    } else if (typeof data.detail === "string") {
                      errorMessage = data.detail;
                    }
                  }
                  throw new Error(errorMessage);
                }

                setPasswordMessage({ type: "success", text: "Password changed successfully" });
                setCurrentPassword("");
                setNewPassword("");
                setConfirmPassword("");
              } catch (error) {
                setPasswordMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to change password" });
              } finally {
                setIsChangingPassword(false);
              }
            }}
            disabled={isChangingPassword}
          >
            {isChangingPassword ? "Changing..." : "Change Password"}
          </button>
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

      {/* Roadmap Editor Card */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h1 style={{ margin: 0 }}>📋 Roadmap Editor</h1>
        <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginTop: "-0.5rem" }}>
          Edit the roadmap items shown on the In Progress page. Admin only.
        </p>

        {roadmapMessage && (
          <div className={roadmapMessage.type === "success" ? "success-text" : "error-text"}>
            {roadmapMessage.text}
          </div>
        )}

        {isLoadingRoadmap ? (
          <p>Loading roadmap...</p>
        ) : (
          <>
            {/* Existing Sections */}
            {roadmap.sections.map((section, sectionIdx) => (
              <div 
                key={sectionIdx} 
                style={{ 
                  padding: "1rem", 
                  background: "#1f2937", 
                  borderRadius: "0.5rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0, color: "#a5b4fc" }}>{section.category}</h3>
                  <button
                    className="btn-secondary"
                    style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                    onClick={() => {
                      const newSections = roadmap.sections.filter((_, i) => i !== sectionIdx);
                      setRoadmap({ sections: newSections });
                    }}
                  >
                    Remove Section
                  </button>
                </div>

                {/* Items in section */}
                {section.items.map((item, itemIdx) => (
                  <div key={itemIdx} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <input
                      type="checkbox"
                      checked={item.completed}
                      onChange={(e) => {
                        const newSections = [...roadmap.sections];
                        newSections[sectionIdx].items[itemIdx].completed = e.target.checked;
                        setRoadmap({ sections: newSections });
                      }}
                    />
                    <span style={{ 
                      flex: 1, 
                      color: item.completed ? "#6b7280" : "#e5e7eb",
                      textDecoration: item.completed ? "line-through" : "none"
                    }}>
                      {item.completed && "✓ "}{item.text}
                    </span>
                    <button
                      style={{ 
                        background: "transparent", 
                        border: "none", 
                        color: "#ef4444", 
                        cursor: "pointer",
                        padding: "0.25rem"
                      }}
                      onClick={() => {
                        const newSections = [...roadmap.sections];
                        newSections[sectionIdx].items = newSections[sectionIdx].items.filter((_, i) => i !== itemIdx);
                        setRoadmap({ sections: newSections });
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))}

                {/* Add new item to section */}
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    type="text"
                    placeholder="New item..."
                    value={newItemTexts[sectionIdx] || ""}
                    onChange={(e) => setNewItemTexts((prev) => ({ ...prev, [sectionIdx]: e.target.value }))}
                    style={{
                      flex: 1,
                      padding: "0.375rem 0.5rem",
                      borderRadius: "0.25rem",
                      border: "1px solid #374151",
                      background: "#111827",
                      color: "#e5e7eb",
                      fontSize: "0.875rem",
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && newItemTexts[sectionIdx]?.trim()) {
                        const newSections = [...roadmap.sections];
                        newSections[sectionIdx].items.push({ text: newItemTexts[sectionIdx].trim(), completed: false });
                        setRoadmap({ sections: newSections });
                        setNewItemTexts((prev) => ({ ...prev, [sectionIdx]: "" }));
                      }
                    }}
                  />
                  <button
                    className="btn-secondary"
                    style={{ padding: "0.375rem 0.5rem", fontSize: "0.75rem" }}
                    onClick={() => {
                      if (newItemTexts[sectionIdx]?.trim()) {
                        const newSections = [...roadmap.sections];
                        newSections[sectionIdx].items.push({ text: newItemTexts[sectionIdx].trim(), completed: false });
                        setRoadmap({ sections: newSections });
                        setNewItemTexts((prev) => ({ ...prev, [sectionIdx]: "" }));
                      }
                    }}
                  >
                    + Add
                  </button>
                </div>
              </div>
            ))}

            {/* Add new section */}
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <input
                type="text"
                placeholder="New category name..."
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                style={{
                  flex: 1,
                  padding: "0.5rem 0.75rem",
                  borderRadius: "0.375rem",
                  border: "1px solid #374151",
                  background: "#1f2937",
                  color: "#e5e7eb",
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newCategoryName.trim()) {
                    setRoadmap((prev) => ({
                      sections: [...prev.sections, { category: newCategoryName.trim(), items: [] }]
                    }));
                    setNewCategoryName("");
                  }
                }}
              />
              <button
                className="btn-secondary"
                onClick={() => {
                  if (newCategoryName.trim()) {
                    setRoadmap((prev) => ({
                      sections: [...prev.sections, { category: newCategoryName.trim(), items: [] }]
                    }));
                    setNewCategoryName("");
                  }
                }}
              >
                + Add Category
              </button>
            </div>

            {/* Save Roadmap Button */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.5rem" }}>
              <button
                className="btn-primary"
                onClick={async () => {
                  setIsSavingRoadmap(true);
                  setRoadmapMessage(null);
                  try {
                    const res = await fetch(`/api/system/roadmap`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(roadmap),
                    });
                    if (!res.ok) {
                      const data = await res.json();
                      throw new Error(data.detail || "Failed to save roadmap");
                    }
                    setRoadmapMessage({ type: "success", text: "Roadmap saved successfully (global)" });
                  } catch (error) {
                    setRoadmapMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to save" });
                  } finally {
                    setIsSavingRoadmap(false);
                  }
                }}
                disabled={isSavingRoadmap || !selectedTeamId}
              >
                {isSavingRoadmap ? "Saving..." : "Save Roadmap"}
              </button>
            </div>
          </>
        )}
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
