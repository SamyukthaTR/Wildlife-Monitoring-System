# Production Deployment

This is a concrete, cloud-agnostic deployment guide for a single Docker-capable
VM (AWS EC2, Azure VM, DigitalOcean droplet, or any host with Docker). **No
live cloud instance was provisioned as part of building this** -- this
session had no cloud account credentials to do so. What's delivered instead
is a genuinely production-ready Docker Compose stack (`docker-compose.prod.yml`)
and these instructions, in the same spirit as the rest of this project: no
claim beyond what was actually verified. The stack itself was built and
smoke-tested locally (see `docs/milestone4.md`).

## 1. Provision a VM

Any VM with a public IP and Docker installed works. Minimum realistic spec for
this stack (Postgres + MongoDB + the ML-heavy backend): 4 vCPU, 8GB RAM, 40GB
disk. Install Docker + the Compose plugin per your provider's usual
instructions (`curl -fsSL https://get.docker.com | sh`, then `apt-get install
docker-compose-plugin` on Debian/Ubuntu-based images).

## 2. Point DNS at the VM

Create two DNS A records pointing at the VM's public IP:
- `app.yourdomain.com` -- the frontend
- `api.yourdomain.com` -- the backend

(A single-domain setup works too -- edit `Caddyfile` to route by path instead
of by host if you don't want two subdomains.)

## 3. Clone the repo and configure secrets

```bash
git clone <this-repo-url>
cd Wildlife-Monitoring-System
cp .env .env.prod   # then edit .env.prod with real values:
```

At minimum, replace in `.env.prod`:
- `SECRET_KEY` -- a real random value (`openssl rand -hex 32`), never the dev default
- `POSTGRES_PASSWORD`, `MONGO_INITDB_ROOT_PASSWORD` -- strong values
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- if Google sign-in is wanted; add
  `https://api.yourdomain.com/auth/google/callback` as an authorized redirect
  URI in Google Cloud Console
- `GOOGLE_REDIRECT_URI=https://api.yourdomain.com/auth/google/callback`
- `FRONTEND_URL=https://app.yourdomain.com`
- `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`
- `CORS_ORIGINS=https://app.yourdomain.com`
- `APP_DOMAIN=app.yourdomain.com`
- `API_DOMAIN=api.yourdomain.com`

## 4. Build and start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend alembic upgrade head
```

Caddy (the `caddy` service) automatically requests and renews Let's Encrypt
TLS certificates for `APP_DOMAIN`/`API_DOMAIN` the first time it starts, as
long as ports 80/443 are reachable from the internet and DNS already points
at the VM. No manual certificate handling is needed.

## 5. Verify

```bash
curl https://api.yourdomain.com/health
```
Then visit `https://app.yourdomain.com` in a browser and log in.

## 6. What's different from the dev stack

| | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|---|---|---|
| Backend | Bind-mounted code, `--reload`, single worker | Baked-in code, no reload, 2 workers, non-root user |
| Frontend | Bind-mounted code, `npm run dev` | Next.js standalone build, non-root user |
| Postgres/Mongo ports | Published to host (`5432`, `27017`) | Not published -- reachable only inside the compose network |
| TLS | None (localhost) | Automatic via Caddy |
| Restart policy | None on app services | `unless-stopped` everywhere |

## 7. Backups

Postgres data lives in the `postgres_data` named volume. A simple periodic
backup:
```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U <POSTGRES_USER> <POSTGRES_DB> > backup-$(date +%F).sql
```
Camera-trap/audio uploads live in the `wildlife_uploads` volume -- back that
up too if the raw files matter beyond what's already been analyzed.

## 8. Logs and monitoring

Every request is logged in a consistent format by `app/core/logging.py`
(method, path, status, duration). View them with:
```bash
docker compose -f docker-compose.prod.yml logs -f backend
```
Docker's default `json-file` log driver is used; add
`logging: {driver: json-file, options: {max-size: "10m", max-file: "3"}}`
per-service in `docker-compose.prod.yml` if disk usage from logs needs
bounding on a long-running VM.
