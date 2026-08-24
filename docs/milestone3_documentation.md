# Wildlife Population Intelligence System — Milestone 3, Explained

This document walks through everything built in Milestone 3, in plain language — what exists, where it lives in the codebase, and how to actually go see it working. Written in the same spirit as `docs/milestone1_2_documentation.md`: no jargon dumps, just what's real.

---

## The big picture

Milestone 1 built the foundation (accounts, sites, uploads). Milestone 2 taught the system to *see and hear* — real AI models turning photos and audio into species detections, plus the biodiversity math on top of that. Milestone 3 takes those detections and turns them into something a researcher or officer can actually act on: **is this population growing or shrinking, is this habitat degrading, which sites need attention first, and how healthy is this ecosystem overall.**

Four engines, one dashboard set:

1. **Population Intelligence Engine** — peak counts, trends, encounter rates, presence patterns.
2. **Habitat Intelligence** — vegetation health from real photo pixels, degradation over time, weather, suitability.
3. **Conservation Recommendation workflows** — a rule-based advisor that tells you *why* a site needs attention.
4. **Ecosystem health analytics** — four 0–100 scores that roll everything above into one picture.

### The same guiding principle, carried forward

Milestone 2's rule was: never claim more than the model actually supports. Milestone 3 had to apply that same discipline to a much harder problem, because this system has **no marked or re-identifiable animals** (no way to tell "this tiger" apart from "that tiger" across two different photos), **no satellite imagery**, and **no weather sensors in the field**. Rather than fake any of that, every number in this milestone comes from one of three honest places:

- Data already sitting in the database (detections, survey dates, sites).
- **Real pixel math** run on the same camera-trap photos already uploaded — the same trick Milestone 2 used to score image blur/exposure, just pointed at vegetation instead.
- **Real weather data** pulled from a free public archive, for the site's actual coordinates and actual survey dates — never invented.

Two naming choices matter enough to call out directly, because getting them wrong would have quietly contradicted what Milestone 2 already promised:

- The system never says "population estimate." It says **"peak simultaneous count"** — the most animals of one species ever seen together in a single photo. That's a real, useful field number, but it's a *floor*, not an estimate: it tells you "at least this many were here," never "this many total exist." A true population estimate needs either marked animals or a modeled detection probability, and this system has neither.
- Weather data is labeled everywhere as **modeled historical reanalysis**, not a field sensor reading — because that's exactly what it is (see below). It's real and useful, just not the same thing as a thermometer bolted to a tree.

One more discipline is new this milestone: **a trend line always has *a* slope, even when the data is just noise.** So every trend number here is checked for statistical significance before the system will say "increasing" or "decreasing" out loud — otherwise it says "insufficient evidence," even though a raw number technically exists underneath.

---

## 1. Population Intelligence Engine

**Where it lives:** `backend/app/modules/population/` (`analytics.py` has the pure math, `queries.py` pulls the numbers from the database, `router.py` exposes the API) · **See it live at:** the `/population` page, linked from the Researcher and Conservation Officer dashboards.

Four things it actually measures, and — just as important — what it deliberately does *not* claim:

- **Peak simultaneous count** — the largest number of individuals of one species caught in a single frame. Real, but a lower bound.
- **Trends** — is a species being detected more or less often over time, per site? This uses proper statistics (`scipy`'s linear regression) fit against the *survey date* — not the date the file happened to get uploaded to the system, which can be years off for the historical sample corpus. If there aren't enough survey dates, or the trend line isn't statistically convincing, the system honestly reports "insufficient evidence" rather than a guess.
- **Encounter rate ("density")** — detections per 100 observations at a site. This is explicitly *not* a true animal-per-square-kilometer density, because no site in this system records how large an area it actually covers. Calling it a real density would have been the exact kind of overclaiming Milestone 2 was built to avoid.
- **Presence pattern by month** — which species showed up at which site in which month. This is the honest version of "migration patterns": it shows *when and where* a species was seen, but since no individual animal is tracked between sightings, it cannot and does not claim to have tracked actual migration.

**How to see it:** Log in as a Researcher or Conservation Officer, click **"Population Intelligence"** in the dashboard header, pick a site (or leave it as "all sites"), and you'll see all four of the above as tables and a trend chart you can flip between species.

---

## 2. Habitat Intelligence

**Where it lives:** `backend/app/ml/vegetation.py` (the pixel math), `backend/app/modules/habitat/` (`classify.py`, `models.py`, `queries.py`, `router.py`), `backend/scripts/fetch_environment.py` (the weather fetcher) · **See it live at:** the `/habitat` page, linked from every officer-facing dashboard.

- **Vegetation analysis** — every camera-trap photo is, underneath everything else, just a grid of colored pixels. This engine runs a real formula from plant-ecology literature (the Excess Green Index) over those pixels to score how "green"/vegetated a scene looks, plus a rough texture score for how visually cluttered the canopy is. No satellite needed — it's reading the exact same photos the species detector already looked at.
- **Habitat classification** — turns that greenness score into a plain-English label ("dense vegetation," "sparse vegetation," etc.), and cross-checks it against which kinds of animals have actually been seen there (lots of amphibians/marine species nudges the label toward "wetland," for example).
- **Habitat degradation detection** — this is the one that *needs* repeated visits: a single assessment can't show a decline, only a trend across several can. Every time someone clicks "Run Vegetation Assessment," a new row gets added (never overwriting the last one), and once there's enough history, the system checks whether vegetation is *significantly* trending down — not just noisily bouncing around.
- **Environmental conditions** — real historical daily weather (temperature, humidity, rainfall, wind) for each site's actual GPS coordinates and actual survey dates, pulled from Open-Meteo's free public archive. Worth being precise about what this is: it's **modeled reanalysis data** (a scientifically respected dataset, but computed from a weather model on a ~10–25km grid), not a thermometer physically sitting at that site. The system says so every time it shows this data, rather than letting it look like a field sensor reading.
- **Habitat suitability** — a transparent, explainable score (not a trained AI model — there's no labeled dataset to train one on) that blends the vegetation score with how much of that site's own detection history already belongs to the species group you're asking about.

**How to see it:** Go to `/habitat`, pick a site. If you're a Researcher, Conservation Officer, or Admin, you'll see a **"Run Vegetation Assessment"** button — click it and watch a real assessment appear, computed live from that site's uploaded photos. The environmental conditions and suitability score sections update automatically for whichever site you have selected.

---

## 3. Conservation Recommendation workflows

**Where it lives:** `backend/app/modules/conservation/engine.py` (the rules), `router.py` (wires it to the API) · **See it live at:** the `/conservation` page, and a "Sites Needing Attention" table on the Forest Department Officer dashboard.

This is a deliberately simple, deterministic **rule engine** — not an AI model pretending to have judgment it doesn't have. Every recommendation it makes is triggered by an actual number computed elsewhere in the system, and that number is quoted right back in the recommendation so it can be checked, not just trusted:

| If this happens... | ...the system suggests |
|---|---|
| A site's overall ecosystem health score drops below 40 | **Conservation priority** — this site needs attention |
| An IUCN-listed (endangered/threatened) species is detected | **Wildlife protection** measures, escalated further if that species is also trending downward |
| Vegetation is significantly declining over repeated assessments | **Habitat restoration** — recommends a field vegetation survey |
| A site has very few observations, or a lot of species from very few observations | **Monitoring allocation** — more camera-trap/audio-sensor coverage needed here |

Every one of these only fires when the underlying data actually supports it — a site with no habitat assessment yet simply gets no habitat-restoration suggestion, rather than a guessed one.

**How to see it:** `/conservation` shows recommendation cards color-coded by priority (red = high, amber = medium, gray = low), grouped by site.

---

## 4. Ecosystem health analytics

**Where it lives:** `backend/app/modules/ecosystem/scoring.py` (the formulas), `service.py` (pulls the inputs together), `router.py` · **See it live at:** the top of the `/conservation` page, and the site-ranking table right below it.

Four scores, all 0–100, all built from numbers the system had already computed:

- **Biodiversity score** — from the Shannon diversity index and evenness (the same real ecology math from Milestone 2).
- **Habitat quality score** — from the vegetation index, discounted if degradation is significant.
- **Population stability score** — the share of species trending stable-or-up versus down, ignoring the ones with "insufficient evidence" rather than unfairly counting them against the site.
- **Overall ecosystem health score** — a weighted blend of the three above.

The one rule that took the most care here: **the overall score only appears once at least two of the three pieces are actually available**, and it always says exactly which pieces went into it. A site with only a biodiversity number and nothing else does *not* get a confident-looking 0–100 score built on 1/3 of the real picture — that would have been exactly the kind of false precision this whole project has tried to avoid.

**How to see it:** `/conservation`'s top section shows the four scores as cards for whichever site you've selected, plus a color-coded band (Good/Fair/Poor/Critical), and a full ranking of every site below it.

---

## 5. Where all this shows up on each dashboard

- **Researcher dashboard** — new "Population Intelligence" link in the header.
- **Conservation Officer dashboard** — new links to Population Intelligence, Habitat Intelligence, and Conservation Insights.
- **Forest Department Officer dashboard** — this one was an empty placeholder before Milestone 3. It now has real content: a "Sites Needing Attention" table (pulled straight from the conservation recommendation engine) and a habitat overview table (latest vegetation reading + degradation flag per site), plus links to the full Habitat and Conservation pages.

---

## 6. Database and API additions

Two new tables (migration `d4f1a7c93e56`, chained onto Milestone 2's schema):

- **`habitat_assessments`** — every vegetation assessment ever run, never overwritten — this history is what makes degradation *detection* possible instead of just a single opinion.
- **`environmental_readings`** — the real daily weather data per site, fetched by `scripts/fetch_environment.py` and stored so the habitat page never has to depend on an internet connection to Open-Meteo at the moment someone loads it.

Everything else in this milestone — population numbers, conservation recommendations, ecosystem scores — is computed fresh each time it's requested from data that already exists, rather than stored and risking going stale.

New API endpoints, if you want to poke at the raw JSON directly (via `/docs` on the running backend):
```
GET  /population/estimates | /trends | /density | /distribution
POST /habitat/assess-site/{site_id}
GET  /habitat/sites | /{site_id} | /environment | /suitability
GET  /conservation/recommendations | /priorities
GET  /ecosystem/health | /health/sites
```

---

## 7. How to actually run and see this

```bash
docker compose up --build
docker compose exec backend alembic upgrade head          # creates the 2 new tables
docker compose exec backend python -m scripts.fetch_environment   # pulls real weather, once
```
Then log in, and as a Researcher/Conservation Officer/Admin, visit `/habitat` and click **"Run Vegetation Assessment"** on a site that has uploaded photos — that's the one piece of Milestone 3 that needs a manual click to generate its first data point, since it's genuinely computing something from real images rather than just reading numbers that were already sitting in the database.

Everything else (population trends, conservation recommendations, ecosystem scores) works immediately off whatever species detections already exist from Milestone 2's analysis pipeline.

---

## 8. What was deliberately left out

Same spirit as Milestone 2's "left out" list — these weren't forgotten, they were consciously not attempted because doing them honestly would have needed data this system doesn't have:

- **True population estimation** (distance sampling, capture-recapture, N-mixture models) — all of these need either marked animals or a modeled detection probability, neither of which exists here.
- **Satellite-derived vegetation data (like NDVI)** — no satellite imagery is available, so vegetation analysis was deliberately scoped to what the existing camera-trap photos can honestly support.
- **Real field weather sensors** — the environmental data is real, but it's modeled reanalysis, not on-site telemetry, and is labeled as such everywhere it appears.
- **A trained "suitability" or "recommendation" AI model** — there's no labeled dataset for either, so both are transparent, arguable rule-based systems instead of a black box.

---

## Where things stand, in one paragraph

Milestone 1 built the platform. Milestone 2 gave it the ability to see and hear wildlife, honestly. Milestone 3 turns those raw detections into decision support: real trend statistics instead of guessed directions, real pixel-derived vegetation scores instead of invented ones, real historical weather instead of made-up numbers, and a transparent rule engine instead of a black-box "AI recommends" button. Nothing in this milestone claims a capability the underlying data can't back up — every score, trend, and recommendation can be traced back to an actual number sitting in the database, and the system says so at every step.
