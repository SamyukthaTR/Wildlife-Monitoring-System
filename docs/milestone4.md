# Milestone 4 — Analytics, Testing & Deployment

Executive dashboards, GIS visualization, PDF/Excel report export, an
integration test suite with CI, and a production-ready deployment stack,
built on top of the population/habitat/conservation intelligence Milestone 3
already computes.

**Evaluation criteria addressed**

| Criterion | Status |
|---|---|
| Fully deployed frontend and backend | Done locally (Docker Compose, dev and prod stacks both build and run) — no live cloud instance was provisioned in this session; see "Out of scope" below |
| Dashboards and reporting systems operational | Done — Executive Overview, Map View, PDF/Excel/CSV export across four report types |
| End-to-end wildlife monitoring workflow demonstrated | Done — upload → analysis → population/habitat/conservation intelligence → executive synthesis → export, all exercised by the integration test suite |

---

## 1. Reports & Export System

`backend/app/modules/reports/export.py`, `backend/app/modules/reports/router.py`

Two generic renderers (`render_pdf`, `render_xlsx`) work off the same
`(heading, content)` section list every report endpoint already builds for
its JSON response — no per-report-type formatting logic duplicated four
times. `render_pdf` uses `reportlab` (Platypus tables/paragraphs); `render_xlsx`
uses `openpyxl` (one sheet per section).

Four report endpoints, all supporting `format=json|csv|pdf|xlsx`:

```
GET /reports/monitoring        ?site_id=&survey_id=&format=
GET /reports/species-population?format=
GET /reports/habitat           ?site_id=&format=
GET /reports/conservation      ?site_id=&format=
```

`/reports/habitat` and `/reports/conservation` are new this milestone;
`/reports/monitoring` and `/reports/species-population` previously supported
only JSON/CSV. Every report still states its caveats (detection counts vs.
population size, ERA5 reanalysis vs. field sensors, etc.) inside the exported
file itself, not just the JSON response.

---

## 2. GIS Visualization Module

`frontend/src/components/SiteMap.tsx`, `frontend/src/app/map/page.tsx`

A Leaflet map (OpenStreetMap tiles, no API key) plotting every monitoring
site by its real coordinates, colored by ecosystem health band. All data
comes from three already-existing endpoints (`/monitoring/sites`,
`/ecosystem/health/sites`, `/habitat/sites`, `/conservation/priorities`)
combined client-side — no new backend computation. Loaded via
`next/dynamic({ ssr: false })` since Leaflet requires `window`.

No raster/satellite GIS (GDAL, Rasterio, NDVI) was added: this platform has
no satellite or drone imagery, a decision Milestone 3 made explicit and this
milestone does not revisit.

---

## 3. Executive Dashboard

`frontend/src/app/executive/page.tsx`

A cross-site synthesis view for Conservation Officer / Forest Department
Officer / Administrator roles: ecosystem health ranking, platform-wide
biodiversity snapshot, top conservation priorities, population trend
highlights (filtered to statistically significant trends only), and an
embedded map preview. Every number reuses an existing endpoint — this page
adds no new backend logic, only a management-level combination of what
already exists on the per-engine pages.

---

## 4. Testing & Validation

**Unit tests** (`backend/tests/test_*.py`, unmarked): the 60 pure-function
tests from Milestone 2/3 are unchanged and still run with zero database.

**Integration tests** (`backend/tests/test_api_*.py`, `@pytest.mark.integration`,
32 tests): a `conftest.py` fixture spins up a real Postgres+PostGIS test
database (`TEST_DATABASE_URL`, defaulting to `DATABASE_URL` with a `_test`
suffix), and each test exercises the actual FastAPI app via `TestClient` —
registration/login/role-enforcement, site/survey/device management, admin
user management, and all four report formats. 92 tests total, all passing.

**CI** (`.github/workflows/ci.yml`): three jobs — backend unit tests (no
services needed), backend integration tests (a `postgis/postgis` service
container), and frontend lint/typecheck/test/build.

**Frontend tests** (`frontend/src/**/*.test.tsx`, Jest + React Testing
Library): `ProtectedRoute` role-redirect behavior, `AuthContext` login/logout
state transitions, and the `api.ts` 401-refresh-and-retry interceptor logic.

**Security hardening**:
- Rate limiting (`slowapi`) on `/auth/login` and `/auth/register` only —
  brute-force mitigation without throttling normal API use.
- Security-headers middleware (`X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`).
- `CORS_ORIGINS` is now an env-driven comma-list (`core/config.py`), not a
  hardcoded `localhost:3000`.
- Manual role/auth-boundary checks throughout the integration suite (403 on
  wrong role, 401 on missing/invalid token, self-delete blocked for admins).
  No automated penetration-testing tool was run — this is scoped, manual
  boundary testing, stated as such rather than implied to be more.

**Performance**: `GET /observations` and `GET /users` gained optional
`limit`/`offset` query params, fully backward-compatible — omitted, they
behave exactly as before.

---

## 5. Deployment

`backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.prod.yml`,
`Caddyfile`, `docs/deployment.md`

Both Dockerfiles are now multi-stage: a `dev` stage (unchanged behavior —
docker-compose.yml's bind mount and `command:` override still drive local
development exactly as before) and a `prod` stage (code baked in, no
`--reload`/`npm run dev`, non-root user, Next.js `output: 'standalone'` for
a minimal image).

`docker-compose.prod.yml` adds: no bind mounts, `restart: unless-stopped`
everywhere, a healthcheck on the backend and Postgres, database ports **not**
published to the host, and a `caddy` reverse-proxy service providing
automatic Let's Encrypt TLS.

Both production images were built and smoke-tested locally in this session:
the frontend image builds, starts, and serves `/login` with a 200 in under
200ms; the backend image builds successfully (multi-stage, non-root,
`uvicorn --workers 2`, no reload).

`backend/app/core/logging.py` adds a shared `setup_logging()` and a
request-logging middleware (method, path, status, duration) — the project
previously had no centralized logging, only two files with ad hoc
`logging.getLogger` calls.

---

## 6. Out of scope for Milestone 4

Deliberately not claimed, for the same reason earlier milestones declined to
overstate what they'd built:

- **No live cloud instance was provisioned.** This session has no AWS/Azure/
  GCP credentials. What's delivered is a genuinely production-ready,
  cloud-agnostic Docker Compose stack plus a concrete step-by-step deployment
  guide (`docs/deployment.md`) — verified locally, not claimed as "deployed."
- **No satellite/raster GIS** (GDAL, Rasterio, NDVI) — consistent with
  Milestone 3's decision that no such imagery exists in this system.
- **No automated security-scanning tool** (e.g. OWASP ZAP, `pip-audit` wired
  into CI) — the security work here is targeted (rate limiting, headers,
  env-driven CORS) plus manual role/auth-boundary tests, not a full
  penetration test.
- **CI was authored and syntax-validated but not executed on GitHub** in this
  session (no GitHub Actions runner access here) — the workflow mirrors
  exactly the commands verified locally (same pytest/npm invocations that
  passed on this machine).
