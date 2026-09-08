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

### Azure quickstart

```bash
az group create --name wildlife-rg --location eastus

az vm create \
  --resource-group wildlife-rg \
  --name wildlife-vm \
  --image Ubuntu2204 \
  --size Standard_B4ms \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --os-disk-size-gb 40

az vm open-port --resource-group wildlife-rg --name wildlife-vm --port 80 --priority 1001
az vm open-port --resource-group wildlife-rg --name wildlife-vm --port 443 --priority 1002

az vm show -d --resource-group wildlife-rg --name wildlife-vm --query publicIps -o tsv
```
`Standard_B4ms` (4 vCPU, 16GB RAM, burstable/cost-efficient) comfortably
clears the minimum spec above; use a non-burstable size (e.g.
`Standard_D4s_v5`) instead if the ML inference load is sustained rather than
bursty. Point your domain's DNS at the IP printed by the last command, then
SSH in and install Docker:
```bash
ssh azureuser@<public-ip>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in for the group change to take effect
```

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
cp .env.prod.example .env.prod   # then edit .env.prod with real values
```

Use `.env.prod.example` -- **not** the dev `.env` -- as the starting point.
Generate fresh secrets and OAuth credentials for production rather than
reusing dev values (dev's `SECRET_KEY` and Google OAuth client are for local
use only and should never sign a production session). At minimum, fill in:
- `SECRET_KEY` -- a real random value (`openssl rand -hex 32`), never the dev default
- `POSTGRES_PASSWORD`, `MONGO_INITDB_ROOT_PASSWORD` -- strong values
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- separate production OAuth
  credentials if Google sign-in is wanted; add
  `https://api.yourdomain.com/auth/google/callback` as an authorized redirect
  URI in Google Cloud Console
- `APP_DOMAIN`, `API_DOMAIN`, `FRONTEND_URL`, `NEXT_PUBLIC_API_URL`, `CORS_ORIGINS`
  -- your real domains

`.env.prod` is gitignored (along with every other `.env*` file except the
`.env.example` templates) -- it never gets committed.

## 4. Build and start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend alembic upgrade head
```

The backend's production image (torch, transformers, ultralytics, ...) takes
a few minutes to build from scratch. To skip that on the VM, pull the
prebuilt image instead -- `.github/workflows/docker-publish.yml` publishes it
to GHCR on every push to `main`:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod pull backend
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
(`--build` still builds the frontend, which has no heavy ML deps and is
fast; `pull` only affects services with a published `image:`, so it leaves
`frontend` alone.) If the GHCR package is private, `docker login ghcr.io`
first with a token that has `read:packages` scope.

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
Every service uses the `json-file` log driver with `max-size: 10m, max-file: 3`
(see the `x-logging` anchor at the top of `docker-compose.prod.yml`), so log
disk usage on a long-running VM stays bounded automatically.
