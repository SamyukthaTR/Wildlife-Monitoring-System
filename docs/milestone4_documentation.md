# Wildlife Population Intelligence System — Milestone 4, Explained

Written in the same spirit as `docs/milestone1_2_documentation.md` and
`docs/milestone3_documentation.md`: what exists, where it lives, and how to
actually go see it working.

---

## The big picture

Milestones 1–3 built the platform, taught it to see and hear wildlife, and
turned detections into population/habitat/conservation intelligence.
Milestone 4 is about **making that intelligence usable and shippable**: one
combined view for decision-makers, a map, real downloadable reports, a real
test suite, and a real way to run this thing in production instead of just
on a laptop.

Five things, in order of "what a user actually clicks on":

1. **Executive Overview** — one page combining ecosystem health, top
   priorities, biodiversity, and population trends across every site.
2. **Map View** — every monitoring site plotted on a real map, colored by
   health.
3. **PDF/Excel reports** — every report page can now be downloaded as a
   proper PDF or Excel file, not just viewed as JSON/CSV.
4. **A real test suite** — 92 automated tests (60 unchanged from before, 32
   new ones that actually hit the API), plus a CI pipeline that runs them on
   every push.
5. **Production deployment tooling** — a separate, hardened Docker Compose
   setup for actually running this on a server with a real domain and HTTPS.

---

## 1. Executive Overview

**Where it lives:** `frontend/src/app/executive/page.tsx` · **See it live
at:** `/executive`, linked from the Conservation Officer, Forest Department
Officer, and Admin dashboards.

Everything on this page already existed somewhere else in the app — this
page just puts the pieces a manager actually cares about on one screen:
which sites are healthiest, which need attention first, is biodiversity
holding up platform-wide, and which species are trending up or down with
enough evidence to say so out loud. Nothing new is computed; it's a
combination view, not a new engine.

---

## 2. Map View

**Where it lives:** `frontend/src/components/SiteMap.tsx`,
`frontend/src/app/map/page.tsx` · **See it live at:** `/map`, linked from
every dashboard.

A real map (OpenStreetMap, no API key needed) with a colored dot for every
monitoring site — green/amber/orange/red matching the same Good/Fair/Poor/
Critical bands already used on the Conservation Insights page. Click a dot to
see the site's name, habitat type, health score, and whether it's flagged for
vegetation decline or conservation priority, with links straight to the full
detail pages.

This is deliberately just a coordinates map, not a satellite/remote-sensing
tool — the same honesty rule from Milestone 3 applies: this platform has no
satellite or drone imagery, so the map shows what's real (site locations and
already-computed health), not a simulated NDVI layer.

---

## 3. PDF and Excel Reports

**Where it lives:** `backend/app/modules/reports/export.py` (the rendering),
`backend/app/modules/reports/router.py` (the endpoints) · **See it live at:**
download buttons on the Admin dashboard, Habitat Intelligence page, and
Conservation Insights page.

Every report that used to only return JSON or a CSV file can now also be
downloaded as a properly formatted PDF or an Excel workbook with multiple
sheets. Two new report types were added — a habitat assessment report and a
conservation/ecosystem-health report — alongside the existing wildlife
monitoring and species-population reports. Every exported file carries the
same caveats the on-screen version does (e.g. "these are detection counts,
not population sizes"), so a printed report can't accidentally overstate
what the platform actually knows.

---

## 4. Testing

**Where it lives:** `backend/tests/test_api_*.py` (new),
`frontend/src/**/*.test.tsx` (new), `.github/workflows/ci.yml` (new).

Before this milestone, every automated test was a "pure function" test —
math and logic checked in isolation, with zero database involved. That's
still true for the original 60 tests. This milestone adds 32 new tests that
actually spin up the FastAPI app and a real test database and hit the API
the way a browser would: register a user, log in, check that a Forest
Officer really can't create a monitoring site, check that an Admin really
can't delete their own account, download all four report formats and check
they come back as the right file type. A GitHub Actions workflow runs both
the old and new backend tests, plus the frontend's lint/typecheck/tests/build,
on every push.

The frontend also has its first tests: does the login-wall component
actually redirect the right people away, does logging in and out update the
app's state correctly, does a failed request really retry itself after
refreshing the session.

**How to see it:** `docker compose exec backend pytest tests/ -m "not
integration" -q` (instant, no setup) or `pytest tests/ -m integration -q`
(needs a test database — see the README). `cd frontend && npm test`.

---

## 5. Production Deployment

**Where it lives:** `docker-compose.prod.yml`, `Caddyfile`,
`docs/deployment.md`, the `prod` stage in both `Dockerfile`s.

The everyday Docker setup (`docker-compose.yml`) is built for development —
your code changes show up live, nothing is locked down. This milestone adds
a second, separate setup meant for actually running the platform on a real
server: the app code gets baked into the image instead of live-mounted, both
services run as a non-admin user, the databases are no longer reachable from
outside the server, and a small reverse-proxy service (Caddy) automatically
gets the site a real HTTPS certificate once it has a real domain name pointed
at it.

Worth being direct about one thing: **nothing was actually deployed to a
live AWS/Azure/GCP server in this project** — there were no cloud account
credentials available to do that. What exists instead is deployment tooling
that was built and verified locally (both production Docker images were
built and started successfully) plus a step-by-step guide for taking it the
rest of the way onto a real VM. That's the same honesty this project has
applied everywhere else: say what's real, don't imply more.

---

## Where things stand, in one paragraph

Milestones 1–3 built a platform that sees, hears, and reasons about wildlife
honestly. Milestone 4 makes that reasoning usable: one screen for the people
who need the big picture, a map for where things are, real files people can
actually download and hand to someone else, a test suite that checks the API
itself rather than just the math underneath it, and a production setup ready
to run on a real server the moment someone points a domain at one. Nothing
here claims a deployment that didn't happen or a capability the platform
doesn't have — the same discipline as every milestone before it.
