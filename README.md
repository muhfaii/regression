# Infera

A guided statistical-analysis app. Users upload a dataset (CSV, Excel, SPSS
`.sav`, or pasted text), prepare it (missing data, recoding, computed columns,
reverse scoring, merges), pick or get guided to a test, and get results with
assumption checks, APA-style interpretation, Word export and share links. A
chat assistant explains the results.

Live at <https://infera.byopre.com>.

## Architecture

```
browser ──► Cloudflare Worker (worker/) ──► static frontend (frontend/dist)
                    │
                    └── /api/* ──► FastAPI backend on Render (backend/)
                                        ├── Cloudflare D1 (users, conversations,
                                        │   session metadata, results, share links)
                                        └── Cloudflare R2 (session datasets, Parquet)
```

- **frontend/**: Vue 3 + TypeScript + Vite. Some analyses can run in the
  browser via Pyodide; the build copies `backend/analysis_modules` and
  `regassist/` into `frontend/src/pyodide-src/` for that. `src-tauri/` wraps
  the same frontend as a desktop app.
- **worker/**: serves the built frontend and proxies `/api/*` to the backend.
- **backend/**: FastAPI app. `routers/` are the HTTP endpoints,
  `analysis_modules/` the statistical tests, `services/` storage, auth, limits
  and the LLM client.
- **regassist/**: the regression engine (ingest, OLS/panel estimation,
  diagnostics, remediation, robust SEs) used by the backend.
- **migrations/**: D1 schema, applied with Wrangler.

Dataset sessions expire after 7 days without use.

## Local development

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22.

### Backend

```bash
uv sync --extra dev
```

The backend has no local database, so it talks to a real D1 database and R2
bucket. Set these env vars (a separate dev database and bucket is
recommended):

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Signs login tokens. **Required**; the app won't start without it. |
| `CF_ACCOUNT_ID` | Cloudflare account (D1 and R2). |
| `CF_D1_DATABASE_ID` | D1 database ID. |
| `CF_API_TOKEN` | Cloudflare API token with D1 edit access. |
| `R2_BUCKET` | R2 bucket for session datasets. |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | R2 API token (S3 credentials) for that bucket. |
| `LLM_API_KEY` | Optional. Enables the chat assistant. |
| `LLM_BASE_URL`, `LLM_MODEL` | Optional. OpenAI-compatible endpoint and model for chat. |

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Vite serves on <http://localhost:5173> and proxies `/api` to the backend on
port 8000. For the desktop app, run `npm run tauri:dev` instead.

## Tests

```bash
uv run pytest
```

```bash
cd frontend && npm test
```

The backend tests need no Cloudflare credentials: D1 is replaced with an
in-memory SQLite database built from `migrations/`, and R2 with an in-memory
fake. CI (`.github/workflows/ci.yml`) runs both suites plus the frontend
type-check and build on every pull request.

## Deployment

- **Worker + frontend**: `.github/workflows/deploy.yml` builds the frontend
  and deploys the Worker on every push to `main`. It needs the
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` repository secrets.
- **Backend**: Render builds the `Dockerfile` and deploys on push via its own
  GitHub integration (`render.yaml`). Set the backend env vars above on the
  Render service.
- **Database**: apply new migrations before deploying code that needs them:

  ```bash
  npx wrangler d1 migrations apply infera-db --remote
  ```
