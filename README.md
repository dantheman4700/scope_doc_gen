# Scope Doc Generator Platform

Web application for generating detailed project scope documents by combining local document ingestion, optional research, and a guided template workflow.

## Overview

The legacy single-script tool has been reworked into a three-part system:

- **server/** (FastAPI) – authentication, project/run management, file uploads, vector search, background job orchestration, and storage.
- **server/core/** – shared orchestration engine (summaries, template rendering, research integrations).
- **frontend/** (Next.js + React) – dashboard for projects, runs, artifacts, and global search.

Everything runs locally (PostgreSQL + pgvector, filesystem storage) and is intended for an internal deployment.

## Key Features

- Project-scoped storage (inputs, runs, outputs, cache, artifacts).
- Run modes (`fast` reuse cached context, `full` regenerate summaries) with step tracking.
- Toggleable research (`none`, Claude “quick” search, Perplexity “full” research).
- Vector store indexing + similarity search for completed scopes.
- Background job registry with persisted run state.
- Cookie-based auth with Argon2 password hashing (single-user friendly).

## Prerequisites

- Python 3.8+
- Node.js 18+
- PostgreSQL 15+ with the `vector` extension
- `poetry` or `pip` (choose one workflow)

## Backend Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with:
#   ANTHROPIC_API_KEY=
#   PERPLEXITY_API_KEY=
#   DATABASE_DSN=postgresql://user:pass@localhost:5432/scope
#   SESSION_SECRET=<random string>

alembic upgrade head
uvicorn server.api:app --reload
```

The FastAPI app exposes REST endpoints at `http://localhost:8000`. See `frontend/lib/fetch.ts` for the expected base URL and routes.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Point your browser to `http://localhost:3000`. The app proxies API calls through Next.js route handlers (`frontend/app/api/*`).

## Directory Layout

```
.
├── server/
│   ├── core/           # orchestration engine shared by API and jobs
│   ├── routes/         # FastAPI routers (auth, projects, files, runs, search)
│   ├── services/       # job runner, vector store
│   ├── db/             # SQLAlchemy models and session helpers
│   ├── storage/        # filesystem layout helpers
│   ├── security/       # password & session utilities
│   └── api.py          # FastAPI application factory
├── frontend/           # Next.js dashboard
├── alembic/            # database migrations
├── template_scope.md   # markdown template rendered per run
├── temp_var_schema.json
├── variables.json
├── requirements.txt
└── README.md
```

All runtime data (uploads, cache, outputs) live under `data/` (configurable via `SCOPE_DATA_ROOT` in `.env`).

## Configuration

`server/core/config.py` centralizes environment-driven settings: API keys, session config, database DSN, data paths, research toggles, and rate-limit guidance. Update this file (or the `.env`) to customize defaults.

Key variables:

- `SCOPE_DATA_ROOT` – base directory for project data (defaults to `<repo>/data`).
- `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY` – required for Claude/Perplexity features.
- `DATABASE_DSN` – PostgreSQL connection string (used for both app data and historical scope embeddings).
- `SESSION_SECRET` – used to sign session cookies.
- `HISTORY_ENABLED` – optional toggle for historical reference scope retrieval (uses main database).

## Development Notes

- Use `alembic revision --autogenerate -m "message"` to add schema changes; migrations stay at the repo root for ease-of-use with the Alembic CLI.
- Background generation jobs run through `JobRegistry`; ensure the backend process stays running while runs are in progress.
- Run artifacts (Markdown render, extracted variables, context pack, logs) are persisted to disk and recorded in the `artifacts` table.
- Vector search is provided via the pgvector-backed `VectorStore`. Ensure `CREATE EXTENSION vector;` is enabled on the target database.

## Deployment Checklist

- Provision PostgreSQL (with `pgcrypto` and `vector`).
- Configure environment variables (`.env`, systemd `EnvironmentFile`, etc.).
- Run `alembic upgrade head` during deployment.
- Optionally front the FastAPI + Next.js apps with Nginx and systemd services (see upcoming deployment docs).

## Current Deployment (server) – subject to change

- **Locations:**
  - Production: `/opt/scope_doc_gen`
  - Development: `/home/dan/projects/scope_doc_gen`
  
- **Process manager:** systemd runs two units as user `dan`:
  - `scope-backend.service` → uvicorn on port 8010, env file `/opt/scope_doc_gen/server/.env`
  - `scope-frontend.service` → Next.js on port 3021, env file `/opt/scope_doc_gen/frontend/.env.local`

### Quick Deploy (using sync scripts)

```bash
# 1. Sync server/ and frontend/ code, rebuild frontend, restart services
./scripts/sync-all.sh

# 2. Sync files not covered by sync-all (alembic, requirements)
rsync -av --delete /home/dan/projects/scope_doc_gen/alembic/versions/ /opt/scope_doc_gen/alembic/versions/
cp /home/dan/projects/scope_doc_gen/requirements.txt /opt/scope_doc_gen/requirements.txt

# 3. Install new dependencies and run migrations
cd /opt/scope_doc_gen && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# 4. Restart services (sync-all does this, but do again after migration)
sudo systemctl restart scope-backend scope-frontend
```

**Note:** The `--delete` flag on rsync removes files in production that don't exist in dev. This prevents orphaned migration files from causing "multiple heads" errors in Alembic.

### Manual Deploy (without sync scripts)

1. Sync code to `/opt/scope_doc_gen` (git pull or rsync)
2. Backend deps: `. /opt/scope_doc_gen/venv/bin/activate && pip install -r requirements.txt`
3. Run migrations: `alembic upgrade head`
4. Frontend build: `cd /opt/scope_doc_gen/frontend && npm install && npm run build`
5. Restart: `sudo systemctl restart scope-backend scope-frontend`
6. Verify: `systemctl status scope-backend scope-frontend`

Services do not auto-reload; rebuild + restart required after changes.

## License

[Specify your license here]

## Support

For questions or issues, open an issue or contact the project maintainer directly.

