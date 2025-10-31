# Scope Doc Frontend

Internal dashboard for the scope document generator. Built with Next.js 14 (App
Router) targeting SSR deployment behind a reverse proxy.

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

Required environment variables:

- `NEXT_PUBLIC_API_BASE_URL` – Base URL of the FastAPI backend (e.g.
  `http://localhost:8000`).

Optional:

- `NEXT_PUBLIC_SESSION_COOKIE_NAME` – Override session cookie name if the
  backend does not use the default `scope_session`.

Create a `.env.local` file in this folder and define the variable before running
`next dev`.

The app expects the backend to issue cookie-based sessions from `/auth/login`
and `/auth/logout`.

