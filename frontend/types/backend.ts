export interface Project {
  id: string;
  name: string;
  description?: string | null;
  flags: Record<string, unknown>;
  owner?: {
    id: string;
    email: string;
  } | null;
  team_id?: string | null;
  team?: {
    id: string;
    name: string;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: string;
  filename: string;
  size: number;
  media_type?: string | null;
  checksum: string;
  created_at: string;
  path: string;
  token_count: number;
  native_token_count: number;
  summary_token_count: number;
  is_summarized: boolean;
  summary_text?: string | null;
  is_too_large: boolean;
  pdf_page_count?: number | null;
  use_summary_for_generation: boolean;
}

export interface RunFeedback {
  uncertain_areas?: string[];
  low_confidence_sections?: string[];
  missing_information?: string[];
  notes?: string | null;
}

export interface RunQuestions {
  questions_for_expert?: string[];
  questions_for_client?: string[];
}

export interface RunSummary {
  id: string;
  project_id: string;
  status: string;
  run_mode: string;
  research_mode: string;
  template_type?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  result_path?: string | null;
  error?: string | null;
  params: Record<string, unknown>;
  instructions?: string | null;
  included_file_ids: string[];
  parent_run_id?: string | null;
  extracted_variables_artifact_id?: string | null;
  feedback?: RunFeedback | null;
  google_doc_url?: string | null;
  google_doc_id?: string | null;
  document_title?: string | null;
  questions_state?: {
    expert_answers?: Record<string, string>;
    client_answers?: Record<string, string>;
    expert_locked?: boolean;
    client_locked?: boolean;
    checked_expert?: number[];
    checked_client?: number[];
  } | null;
}

export interface RunStep {
  id: string;
  run_id: string;
  name: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  logs?: string | null;
}

export interface Artifact {
  id: string;
  run_id: string;
  kind: string;
  path: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  owner_id: string;
}

export interface SearchResult {
  embedding_id: string;
  project_id?: string | null;
  doc_kind: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

export interface RunVersion {
  id: string;
  run_id: string;
  version_number: number;
  markdown?: string | null;
  feedback?: RunFeedback | null;
  questions_for_expert?: string[] | null;
  questions_for_client?: string[] | null;
  graphic_path?: string | null;
  created_at: string;
  regen_context?: string | null;
  google_doc_url?: string | null;
  google_doc_id?: string | null;
}

export interface UserPreferences {
  default_team_id?: string | null;
}

