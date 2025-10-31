# Supabase Smoke Test (Manual)

Use this checklist before deploying changes to production. The flow assumes the backend and frontend are running against Supabase providers.

## Prerequisites

- Supabase project with bucket and database configured (see `deployment.md`).
- Backend running locally or on staging with `AUTH_PROVIDER=supabase` and `STORAGE_PROVIDER=supabase`.
- Frontend configured with `NEXT_PUBLIC_SUPABASE_*` variables.

## Test Flow

1. **Sign in**
   - Navigate to `/login`.
   - Sign in with a Supabase-authenticated email/password.
   - Confirm the navbar shows the user email.

2. **Create a project**
   - Go to `/projects` → “Create project”.
   - Fill in name/description and submit.
   - The project should appear in the list.

3. **Upload inputs**
   - Click the project → “Upload files”.
  - Upload at least one markdown or text document.
   - Confirm upload list shows checksum/size.

4. **Launch a run**
   - Return to the project detail page.
   - Set run mode (full), research mode (quick), optionally enable vector store.
   - Start the run.
   - On the run detail page, watch status update until it finishes.

5. **Validate artifacts**
   - Ensure steps table shows each phase complete.
   - In the artifact list, click “View” to open inline preview.
   - Download the rendered scope; verify file contents locally.

6. **Supabase verification**
   - In the Supabase dashboard, confirm bucket contains:
     - `projects/<project-id>/input/...` for uploaded files.
     - `projects/<project-id>/outputs/...` and `artifacts/...` for generated assets.
   - Check the database tables (`projects`, `project_files`, `runs`, `artifacts`, `scope_embeddings`) contain records for the run.

7. **Search**
   - Go to `/search` and run a query that should hit the new scope.
   - Verify result card links to the run and displays metadata.

8. **Logout / Session**
   - Use the “Sign out” button in the navbar.
   - Confirm you are redirected to `/login` and protected pages prompt for sign-in.

Record any failures along with logs from the backend (`uvicorn`) and Supabase dashboard (Storage/API logs).

## Placeholder Automation

- File: `server/tests/test_smoke_placeholder.py`
- Purpose: provides a pytest skip marker indicating where automated smoke tests should live once we add e2e tooling (e.g., Playwright or integration scripts using Supabase APIs).
- Status: intentionally skipped to avoid false positives until Supabase secrets can be injected securely in CI.

