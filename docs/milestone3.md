# Milestone 3 — Population, Habitat & Conservation Intelligence

Population Intelligence Engine, Habitat Intelligence, Conservation Recommendation
workflows, and ecosystem health analytics, built on top of the detections and
survey data Milestones 1–2 already collect.

**Evaluation criteria addressed**

| Criterion | Status |
|---|---|
| Population Intelligence Engine operational | Done — peak counts, trends, encounter rate, presence patterns |
| Habitat Intelligence functional | Done — vegetation from real pixels, degradation trend, environment, suitability |
| Conservation Recommendation workflows completed | Done — deterministic rule engine over already-computed numbers |
| Ecosystem health analytics | Done — four component scores with honest null propagation |
| Wildlife intelligence dashboards | Done — `/population`, `/habitat`, `/conservation` pages |

---

## 1. The guiding principle, continued

Milestone 2 established one rule and this milestone inherits it without
exception: **never assert more than the data actually supports.** This system
has no marked or cross-frame re-identifiable animals, no satellite or drone
imagery, and no on-site weather sensors. Rather than simulate any of those,
every new number here comes from one of three honest sources:

1. **Data already in the database** — detections, survey dates, sites.
2. **Real pixel-derived metrics** computed from the same camera-trap images
   the species recognition engine already analyses, the same precedent
   `app/ml/quality.py` set for blur/exposure scoring in Milestone 2.
3. **A real, free, no-key external dataset** — Open-Meteo's historical
   weather archive — fetched by a standalone script, the same pattern
   `scripts/fetch_samples.py` already uses for iNaturalist/GBIF.

Two naming corrections matter enough to state up front:

- The largest number of individuals of one species seen together in a single
  frame is **not** "Minimum Number Alive" — that term describes a
  mark-recapture quantity, and this platform performs no cross-frame
  individual re-identification (unchanged since Milestone 2). It is called
  `peak_simultaneous_count` everywhere, and documented as a **lower bound**,
  not an estimate.
- Environmental readings are **ERA5 reanalysis** — a real, modelled,
  ~9–25km-grid dataset — not a field sensor. Every response that surfaces
  them says so.

A third discipline is new this milestone: a linear regression always produces
*some* slope, even from noise. Every trend figure (`app/analytics/trend.py`)
is gated on sample size and statistical significance (p < 0.05), and reports
`"insufficient evidence"` rather than a confident-looking direction when the
data doesn't support one.

---

## 2. Population Intelligence Engine

`backend/app/modules/population/`

| Quantity | What it is | What it is *not* |
|---|---|---|
| `peak_simultaneous_count` | Max individuals of a species in one frame | A population estimate — it's a lower bound |
| `count_variability` | Bootstrap spread of per-survey peak counts (n ≥ 5) | A calibrated confidence interval for true population size |
| Trend `direction` | Regression-fit direction, gated on p < 0.05 and n ≥ 3 | A claim from 2–3 noisy points |
| `encounter_rate_per_100_observations` | Detections normalised by monitoring effort | A true area-based density — no site records its surveyed area |
| Distribution by month | Species × site × month presence | Confirmed migration — no individual is tracked across frames or sites |

Time axis is `Survey.survey_date` throughout, not `ObservationLog.uploaded_at`
— upload time can lag real fieldwork by years for the seeded historical
corpus. Counting unit and exclusions (unknown detections, coarse-rank labels)
match `biodiversity/queries.py` exactly; audio is excluded entirely since an
acoustic event carries no simultaneous-individual-count signal.

**API**
```
GET /population/estimates     ?site_id=&species_id=
GET /population/trends        ?site_id=&species_id=
GET /population/density       ?site_id=
GET /population/distribution  ?site_id=&species_id=
```

---

## 3. Habitat Intelligence

`backend/app/ml/vegetation.py`, `backend/app/modules/habitat/`

**Vegetation analysis** reads the Excess Green Index (Woebbecke et al. 1995)
directly from each image's RGB pixels — no satellite data required or
claimed. `canopy_texture_index` is Laplacian edge density, a rough proxy for
visual clutter. Neither is a trained classifier; thresholds are stated in
`vegetation.py` so they can be argued with, the same discipline
`quality.py` established.

**Habitat classification** bands the vegetation index into a descriptive
signal, corroborated by which species groups have actually been detected at
the site (e.g. a strong marine/amphibian presence nudges the signal toward
wetland even at moderate greenness). A transparent heuristic
(`app/modules/habitat/classify.py`), not a trained model.

**Habitat degradation** requires a real trend: `POST /habitat/assess-site/{id}`
computes vegetation metrics from up to `limit` of a site's real images and
appends one row to `habitat_assessments` — it never overwrites the previous
assessment. Degradation is flagged only when the vegetation index shows a
*statistically significant* decline across assessments; one assessment alone
can never show degradation.

**Environmental conditions** come only from `scripts/fetch_environment.py`,
which pulls real ERA5 reanalysis daily weather for each site's actual
coordinates and survey date range from Open-Meteo's free archive API. The
habitat router never calls the weather API itself — a page load never depends
on outbound network reachability, and a genuinely unlocated or placeholder
(`0, 0`) site is skipped by the fetch script rather than given a
plausible-looking but meaningless reading.

**Habitat suitability** blends the site's vegetation index with how much of
its own detection history already belongs to the requested species group — a
transparent weighted heuristic (`classify.py`), not a trained
suitability model; there is no labelled suitability dataset to train one on.

**API**
```
POST /habitat/assess-site/{site_id}   ?limit=       Researcher, Conservation Officer, Admin
GET  /habitat/sites
GET  /habitat/{site_id}
GET  /habitat/environment             ?site_id=
GET  /habitat/suitability             ?site_id=&species_group=
```

---

## 4. Conservation Recommendation workflows

`backend/app/modules/conservation/engine.py`

A deterministic, rule-based decision-support layer — explicitly **not**
framed as AI-generated, because there is no training data for "the right
conservation action" and presenting rules as AI would overstate them exactly
the way this project has avoided overstating its ML models throughout.

| Category | Triggered by |
|---|---|
| `conservation_priority` | Overall ecosystem health score below 40 (high below 25) |
| `wildlife_protection` | An IUCN-listed species detected at the site; escalated if that species also shows a significant declining trend |
| `habitat_restoration` | A statistically significant declining vegetation-index trend |
| `monitoring_allocation` | Effort below 10 observations (too sparse to trust), or high species richness with comparatively low effort (under-sampled) |

Every rationale string cites the actual number that triggered it. A missing
input produces no recommendation for that category — never a guessed one.

**API**
```
GET /conservation/recommendations   ?site_id=
GET /conservation/priorities
```

---

## 5. Ecosystem health analytics

`backend/app/modules/ecosystem/scoring.py`

| Score | Formula | Null when |
|---|---|---|
| `biodiversity_score` | Mean of (Shannon H' normalised to a reference of ln(20)) and Pielou evenness, ×100 | Both inputs missing |
| `habitat_quality_score` | Vegetation index ×100, ×0.7 if degradation is significant | No habitat assessment |
| `population_stability_score` | Share of species trending stable/increasing vs. declining, excluding "insufficient evidence" species from the denominator | No species with usable trend data |
| `overall_ecosystem_health_score` | Weighted mean (35/30/35) of the three above, **renormalised over whichever are available** | Fewer than 2 of the 3 components are available |

The `overall` score always returns `computed_from`, so the UI never shows a
confident-looking 0–100 figure without saying how much of it is actually
backed by data — the same discipline `biodiversity/indices.py`'s `_empty()`
applies at the community level, extended to composite scores.

**API**
```
GET /ecosystem/health         ?site_id=
GET /ecosystem/health/sites
```

---

## 6. Schema

New Alembic revision `d4f1a7c93e56`, chained off `b7c2e9d41a05`. Everything
else in this milestone is computed on read from existing tables plus these
two — no other schema changes were needed.

- **`habitat_assessments`** — append-only; one row per `POST /habitat/assess-site`
  run: `vegetation_index`, `green_pixel_fraction`, `canopy_texture_index`,
  `declared_habitat_type` (snapshotted from the site at assessment time),
  `inferred_habitat_signal`, `images_sampled`, `created_by`.
- **`environmental_readings`** — one row per site per day:
  `temperature_c`, `humidity_pct`, `precipitation_mm`, `wind_speed_kmh`,
  `source` (always `"open-meteo-era5-archive"`). Unique on
  `(site_id, recorded_date)` so re-running the fetch script upserts instead
  of duplicating.

---

## 7. Frontend

| Page | What it adds |
|---|---|
| `app/population/page.tsx` | Peak-count table, trend chart per species, encounter-rate table, presence-by-month view |
| `app/habitat/page.tsx` | Vegetation history chart, degradation flag, environmental conditions, suitability score, role-gated "Run Assessment" action |
| `app/conservation/page.tsx` | Ecosystem health score cards, site ranking, recommendation cards grouped by priority |
| `dashboards/forest-officer/page.tsx` | Built out from an empty placeholder: sites-needing-attention table and habitat overview |
| `dashboards/researcher/page.tsx`, `dashboards/conservation-officer/page.tsx` | Nav links to the new pages |

Every derived numeric field in `lib/types.ts` is typed `number \| null`,
matching the existing `DiversityIndices` convention — null renders as "n/a" or
an explicit empty-state message, never a fabricated zero.

---

## 8. Running it

```bash
docker compose up --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.fetch_environment   # real weather, once
# then, per site, as a Researcher/Conservation Officer/Admin:
curl -X POST localhost:8000/habitat/assess-site/<site_id> -H "Authorization: Bearer <token>"
```

Pure-function tests (no database required) run anywhere:
```bash
cd backend
./.venv-ml/Scripts/python.exe -m pytest tests/ -q
```

---

## 9. Out of scope for Milestone 3

Deliberately not built, for the same reason Milestone 2 declined to overstate
its models:

- **True population estimation** via distance sampling, N-mixture models, or
  real mark-recapture — all require either a modelled detection probability
  or marked/re-identifiable individuals, neither of which this platform has.
- **Satellite- or drone-derived vegetation indices** (e.g. NDVI from
  multispectral imagery) — no such imagery is available; vegetation analysis
  here is deliberately scoped to what real camera-trap RGB pixels support.
- **Live on-site environmental sensors** — `environmental_readings` is
  modelled reanalysis, not telemetry, and is labelled as such everywhere.
- **A trained habitat-suitability or conservation-recommendation model** —
  no labelled dataset exists for either; both are transparent, arguable
  heuristics instead.
- PDF/Excel export, GIS map visualisation — Milestone 4.
