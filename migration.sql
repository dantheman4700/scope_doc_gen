[INFO] Initializing vector store with dimension 1536
[WARN] Vector store unavailable: connection is bad: connection to server at "2600:1f18:2e13:9d24:2bef:82ff:423c:d3f4", port 5432 failed: Network is unreachable
	Is the server running on that host and accepting TCP/IP connections?
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE projects (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    owner_id UUID, 
    name VARCHAR(200) NOT NULL, 
    description TEXT, 
    flags JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE project_files (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    project_id UUID NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    path TEXT NOT NULL, 
    size BIGINT NOT NULL, 
    media_type VARCHAR(120), 
    checksum VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    project_id UUID NOT NULL, 
    mode VARCHAR(20) NOT NULL, 
    research_mode VARCHAR(20) NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITHOUT TIME ZONE, 
    finished_at TIMESTAMP WITHOUT TIME ZONE, 
    params JSONB DEFAULT '{}'::jsonb NOT NULL, 
    error TEXT, 
    result_path TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE run_steps (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    run_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    started_at TIMESTAMP WITHOUT TIME ZONE, 
    finished_at TIMESTAMP WITHOUT TIME ZONE, 
    logs TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE TABLE artifacts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    run_id UUID NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    path TEXT NOT NULL, 
    meta JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE TABLE scope_embeddings (
    id UUID NOT NULL, 
    project_id UUID, 
    doc_kind VARCHAR(40) NOT NULL, 
    embedding VECTOR, 
    metadata JSONB, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE INDEX ix_projects_owner_id ON projects (owner_id);

CREATE INDEX ix_project_files_project_id ON project_files (project_id);

CREATE INDEX ix_runs_project_id ON runs (project_id);

CREATE INDEX ix_run_steps_run_id ON run_steps (run_id);

CREATE INDEX ix_artifacts_run_id ON artifacts (run_id);

CREATE INDEX ix_scope_embeddings_project_id ON scope_embeddings (project_id);

INSERT INTO alembic_version (version_num) VALUES ('0001_initial') RETURNING alembic_version.version_num;

-- Running upgrade 0001_initial -> 0002_file_run_metadata

ALTER TABLE project_files ADD COLUMN token_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE project_files ADD COLUMN is_summarized BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE project_files ADD COLUMN summary_text TEXT;

ALTER TABLE project_files ADD COLUMN is_too_large BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE project_files ADD COLUMN pdf_page_count INTEGER;

ALTER TABLE runs ADD COLUMN included_file_ids JSONB DEFAULT '[]'::jsonb NOT NULL;

ALTER TABLE runs ADD COLUMN instructions TEXT;

ALTER TABLE runs ADD COLUMN extracted_variables_artifact_id UUID;

ALTER TABLE runs ADD FOREIGN KEY(extracted_variables_artifact_id) REFERENCES artifacts (id) ON DELETE SET NULL;

ALTER TABLE runs ADD COLUMN parent_run_id UUID;

ALTER TABLE runs ADD FOREIGN KEY(parent_run_id) REFERENCES runs (id) ON DELETE SET NULL;

CREATE INDEX ix_runs_parent_run_id ON runs (parent_run_id);

CREATE INDEX ix_runs_extracted_vars_artifact_id ON runs (extracted_variables_artifact_id);

ALTER TABLE project_files ALTER COLUMN token_count DROP DEFAULT;

ALTER TABLE project_files ALTER COLUMN is_summarized DROP DEFAULT;

ALTER TABLE project_files ALTER COLUMN is_too_large DROP DEFAULT;

ALTER TABLE runs ALTER COLUMN included_file_ids DROP DEFAULT;

UPDATE alembic_version SET version_num='0002_file_run_metadata' WHERE alembic_version.version_num = '0001_initial';

COMMIT;

