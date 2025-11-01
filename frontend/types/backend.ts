export interface Project {
  id: string;
  name: string;
  description?: string | null;
  flags: Record<string, unknown>;
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
  is_summarized: boolean;
  summary_text?: string | null;
  is_too_large: boolean;
  pdf_page_count?: number | null;
  use_summary_for_generation: boolean;
}

export interface RunSummary {
  id: string;
  project_id: string;
  status: string;
  run_mode: string;
  research_mode: string;
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

export interface SearchResult {
  embedding_id: string;
  project_id?: string | null;
  doc_kind: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

