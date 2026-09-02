# Wildlife Population Intelligence System

An AI-powered platform for wildlife researchers, conservation officers, forest department officers, and admins to monitor species, populations, and habitat health.

## Project Structure

This is a monorepo containing the following components:

- `/backend`: FastAPI Python application. Organized by domain modules (e.g. `health`, `auth`, `surveys`).
- `/frontend`: Next.js (App Router) React application with Tailwind CSS.
- `/infra`: Infrastructure configuration files, including environment templates.
- `/docs`: Documentation for the project.

## Prerequisites

- Docker and Docker Compose

## Quick Start

The entire stack (Frontend, Backend, PostgreSQL with PostGIS, and MongoDB) can be run locally using Docker Compose.

1. **Configure Environment Variables**:
   Copy the example environment file from the infra directory:
   ```bash
   cp infra/.env.example .env
   ```
   *(Or copy it manually in your file explorer.)*

2. **Start the Services**:
   Run the following command from the project root:
   ```bash
   docker compose up --build
   ```

3. **Access the Services**:
   - **Frontend**: [http://localhost:3000](http://localhost:3000)
   - **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

## Architecture

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: Node.js 20+, Next.js, React, Tailwind CSS
- **Primary Database**: PostgreSQL + PostGIS (for spatial data)
- **Secondary Database**: MongoDB (for unstructured data/logs)

## Running Tests

Backend pure-function tests need no database and run anywhere:
```bash
docker compose exec backend pytest tests/ -m "not integration" -q
```
Backend integration tests (API endpoints via FastAPI's TestClient) need a
live Postgres+PostGIS database:
```bash
docker compose exec postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB> -c "CREATE DATABASE <POSTGRES_DB>_test;"
docker compose exec backend pytest tests/ -m integration -q
```
Frontend:
```bash
cd frontend
npm test          # Jest + React Testing Library
npx tsc --noEmit  # typecheck
npm run lint
npm run build     # production build
```
See `.github/workflows/ci.yml` for how these all run together in CI.

## Production Deployment

See [`docs/deployment.md`](docs/deployment.md) for a full guide to deploying
`docker-compose.prod.yml` (production-built images, no bind mounts, automatic
TLS via Caddy) to any Docker-capable VM.
