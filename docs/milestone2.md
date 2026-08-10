# Milestone 2 — Species Recognition, Bioacoustics & Biodiversity Analytics

Weeks 3 & 4 of the Wildlife Population Intelligence System.

**Evaluation criteria addressed**

| Criterion | Status |
|---|---|
| Species recognition engine operational | Done — YOLOv8n + ResNet-50, running on the seeded corpus |
| Bioacoustic recognition workflows functional | Done — AST/AudioSet + librosa event detection and noise filtering |
| Biodiversity analytics implemented | Done — Shannon, Simpson, Gini-Simpson, inverse Simpson, Pielou evenness |
| Wildlife monitoring reports | Done — JSON report plus CSV export (PDF/Excel is Milestone 4) |

---

## 1. The guiding principle

The models used here are general-purpose. ImageNet-1k contains roughly 400 animal
classes against millions of real species; AudioSet contains none at all. A system
built on them can be genuinely useful, but only if it is honest about the rank at
which it is actually operating.

So the rule throughout this milestone is: **never assert more than the model
supports.**

- A detection the classifier cannot name is stored as `"unidentified animal"`,
  not as the detector's nearest guess.
- Labels that name a group or a sound type ("bird", "Frog", "Insect") are stored
  at `coarse` rank and excluded from species-level diversity indices.
- IUCN status is `null` unless a source database published one. It is never inferred.
- Diversity indices are `null`, not `0`, where they are mathematically undefined.
- Coordinates are `null` where the source does not publish them.

This continues the correction made in commit `ca62335`, which replaced fabricated
sample data and invented GPS coordinates with genuine records and honest nulls.

---

## 2. Models

All PyTorch, CPU-only, loaded lazily on first use and cached in `MODEL_CACHE_DIR`.

| Model | Role | Operates at |
|---|---|---|
| `yolov8n` (COCO) | animal detection, counting, bounding boxes | 10 coarse animal classes |
| `resnet50` (ImageNet-1k V2) | species classification of each detected crop | ~400 animal classes, many species-level |
| `MIT/ast-finetuned-audioset-10-10-0.4593` | acoustic event classification | 527 AudioSet classes, none species-level |
| `librosa` | audio loading, energy envelope, noise floor, event segmentation | — |
| `OpenCV` | image quality metrics | — |

**Why AST instead of the specified YAMNet/BirdNET.** AST classifies the same
AudioSet 527-label ontology as YAMNet, but is a PyTorch model. Using it keeps the
entire stack on one framework: adding TensorFlow alongside PyTorch would have
grown the container by roughly a gigabyte for no gain in capability.

Weights are downloaded once (~450 MB total) by `scripts/download_models.py` into a
Docker volume. A model that fails to load is recorded as unavailable with its
reason, and analysis records a `failed` run with a readable error rather than
returning a server error.

---

## 3. Wildlife Image Analysis Engine

`backend/app/ml/image.py`, `backend/app/ml/quality.py`

Pipeline per image:

1. **Quality assessment** — Laplacian variance for blur, mean luminance and
   highlight/shadow clipping for exposure, standard deviation for contrast,
   combined into a 0–1 score with a human-readable explanation. Thresholds are
   stated in `quality.py` so the score can be argued with.
2. **Animal detection** — YOLOv8n, filtered to COCO's ten animal classes. Boxes
   are converted to original-image pixel coordinates. `animal_count` is the
   number of localised animals.
3. **Species classification** — ResNet-50 on each crop (with a 10% margin, since
   tight boxes cut off horns, tails and legs). Only animal classes are candidates.
4. **Whole-frame fallback** — when the detector finds nothing, the frame is
   classified as a whole. This is how insects and fish get identified at all,
   since COCO has no class for them.
5. **Unknown handling** — below `CLASSIFICATION_CONF_THRESHOLD` (0.25), the
   detection is stored as `"unidentified animal"` with `is_unknown = true`. The
   COCO class that located the box is kept in `detector_label` and the
   classifier's best guess in `candidate_label` / `candidate_confidence`, so the
   result reads *"unidentified animal, closest match terrapin (18%)"*.

**Individual animal identification.** `detection_index` identifies an individual
*within one frame*. Matching an individual across frames — stripe or spot
re-identification — is not attempted and is not claimed anywhere in the API or UI.

**Animal behaviour detection.** `posture_hint` is derived from bounding-box
aspect ratio and is labelled everywhere as a geometric heuristic, not a trained
behaviour classifier. A real one would need a behaviour-annotated dataset such as
Animal Kingdom, which is deferred (see `docs/datasets.md`).

### Why the "unidentified animal" rule matters

On the real corpus, YOLOv8n labelled a **snapping turtle as "elephant" at 0.84
confidence** and a **salamander as "bird" at 0.93**. Both are confident, both are
wrong, and both are exactly what a COCO-trained detector does when shown an animal
outside its ten classes. Presenting either as the finding would be a mistake a
surveyor could not catch. The classifier disagreed in both cases, so both are
recorded as unidentified.

---

## 4. Bioacoustic Recognition Engine

`backend/app/ml/audio.py`

1. **Load** at 16 kHz mono.
2. **Noise floor** — the 10th percentile of frame RMS energy, which for field
   recordings is the ambient background between calls. Spectral flatness is
   reported alongside it (near 1 = noise-like, near 0 = tonal).
3. **Acoustic event detection** — stretches rising 8 dB above the noise floor
   become events. Events closer than 0.4 s are merged; anything under 0.35 s is
   a transient, not a call.
4. **Windowing** — the recording is tiled into non-overlapping 10.24 s windows
   (AST's expected length) and only tiles containing an event are classified.
   Centring a window on each event instead made consecutive windows overlap
   almost completely on a bird calling every two seconds: the model was handed
   near-identical audio repeatedly, returned identical scores, and the file took
   84 seconds. Tiling classifies each second at most once.
5. **Classification and noise filtering** — AST returns AudioSet labels, split
   into biological (bird, frog, insect, mammal vocalisations) and environmental
   (wind, rain, speech, vehicles). Environmental labels are **kept** with
   `is_noise = true` rather than discarded, so the filtering is auditable.

**Stated limitation.** AudioSet has no species-level classes. This engine
distinguishes a bird from a frog from rain; it cannot distinguish a macaw from a
parakeet. Acoustic detections are stored at coarse rank and are excluded from
species diversity indices — counting "Bird" as a species would inflate richness
with something that is not a species.

---

## 5. Species Identification Engine

`backend/app/modules/species/`

A catalog table (`species`) built from four sources, each recorded in `label_source`:

| Source | Rank | Provides |
|---|---|---|
| Corpus ground truth (iNaturalist / GBIF) | species | real taxonomy **and the only IUCN statuses in the system** |
| ImageNet-1k animal labels | resolved via GBIF backbone | scientific name, class/order/family, `gbif_taxon_key` |
| COCO animal classes | coarse | 10 group-level entries |
| AudioSet biological classes | coarse | ~60 sound-type entries |

ImageNet labels are resolved through the free GBIF species-match API, falling back
to a vernacular-name search. GBIF's own `matchType` is stored; where GBIF finds
nothing the row is kept at coarse rank with `gbif_match_type = "NONE"` and no
taxonomy asserted.

`is_endangered` is derived strictly from the IUCN threatened categories
(CR, EN, VU). The Conservation Officer dashboard additionally surfaces EX and EW,
which sit outside the formal "threatened" bracket but obviously belong on a
conservation view.

---

## 6. Biodiversity Intelligence

`backend/app/modules/biodiversity/indices.py` — pure functions, unit-tested with
no database and no models (`backend/tests/test_biodiversity.py`, 8 tests).

With `p_i = n_i / N`:

- Species richness `S` — distinct species with `n_i > 0`
- Shannon `H' = −Σ p_i ln p_i`
- Simpson `D = Σ p_i²` (dominance); Gini-Simpson `1 − D`; inverse Simpson `1/D`
- Pielou evenness `J' = H' / ln S`

**Counting unit:** one detected animal in one frame is one observation of that
species. Three things are excluded from the indices and reported separately
rather than silently dropped — coarse-rank labels, unidentified detections, and
all acoustic detections.

**Undefined vs zero.** With one species, evenness is `0/0` and is reported as
`null` — a single-species community is not "perfectly uneven". With no detections,
every index is `null` with an explanatory note, because reporting zeros would make
an unsurveyed site look like a dead one.

---

## 7. Data corpus

`backend/scripts/fetch_samples.py` → `backend/scripts/sample_data/manifest.json`

Milestone 1 shipped 7 files. Inspection showed only 2 contained a recognisable
animal: both Snapshot Serengeti frames are empty savanna, the iNaturalist sample
was **red clover — a plant** (the adapter had no `iconic_taxa` filter), and the
GBIF sample is a pinned moth specimen. A recognition engine on that corpus would
honestly report almost nothing.

The corpus is now **45 files, 43 with species-level ground truth**:

| | |
|---|---|
| 34 images, 11 audio | across all six specification species groups |
| 41/45 with real coordinates | 10 flagged `coordinates_obscured` (iNaturalist blurs threatened taxa) |
| 10 with a published IUCN status | including CR, VU, NT and EX |

**All 7 original files were kept.** The empty Serengeti frames exercise the
"no detection" path and image-quality scoring; the clover is a true negative for
the animal detector; the moth exercises the insect path.

Ground truth is the source database's own community-verified identification, which
is what makes `GET /analysis/metrics` a **measurement** rather than a claim. It
reports species-level and class-level agreement separately, because class-level is
the fair measure of these models on this task.

Two provenance fixes to Milestone 1: observation timestamps now use the real
observed date instead of `datetime.now()`, and sites are positioned from the real
coordinates of their observations instead of `POINT(0 0)`.

Xeno-canto retired its keyless v2 API (v3 requires a personal key), so the two
Milestone 1 MP3s have their metadata read from their own ID3 tags and newer bird
audio comes from iNaturalist instead.

---

## 8. API surface

```
POST /analysis/observations/{id}/analyze     202  Researcher, Conservation Officer, Admin
POST /analysis/run-pending                   202  Admin — analyses the seeded corpus
GET  /analysis/observations/{id}                  detections + run + how to read them
GET  /analysis/runs                               recent runs with latency
GET  /analysis/models                             which models loaded, and why any failed
GET  /analysis/metrics                            accuracy vs ground truth; latency p50/p95

GET  /species              ?group=&rank=&endangered=&detected_only=&search=
GET  /species/stats
GET  /species/detections/summary
GET  /species/{id}

GET  /biodiversity/indices      ?site_id=&survey_id=
GET  /biodiversity/composition  ?site_id=&survey_id=
GET  /biodiversity/acoustic     ?site_id=&survey_id=
GET  /biodiversity/sites

GET  /reports/monitoring        ?site_id=&survey_id=&format=json|csv
GET  /reports/species-population
```

Analysis is queued by `BackgroundTasks` on upload, so the uploader gets an
immediate 201 and polls for the result. `processing_status` moves
`pending → processing → completed | failed`. Re-analysis replaces an observation's
previous detections rather than adding to them.

Every analysis response carries an `interpretation` block explaining what
`is_unknown`, `detector_label`, `posture_hint` and the acoustic labels do and do
not mean, so a consumer of the raw API cannot mistake a coarse label for a species
identification.

---

## 9. Frontend

| File | What it adds |
|---|---|
| `components/DetectionOverlay.tsx` | boxes over the image; pixel coords converted to percentages of natural size so they scale with the rendered element |
| `components/AnalysisPanel.tsx` | results modal — image + overlay, or audio timeline; polls while analysis is in flight |
| `app/biodiversity/page.tsx` | index cards, species composition chart, acoustic activity, per-site comparison |
| `app/dashboards/researcher/page.tsx` | Analyze / Re-analyze buttons, status badges, results modal |
| `app/dashboards/conservation-officer/page.tsx` | species of conservation concern by IUCN category, most-detected species chart |
| `lib/types.ts` | shared API types |
| `lib/api.ts` | now reads `NEXT_PUBLIC_API_URL` (compose already set it; it was dead config) |

Added dependency: `recharts`.

Unidentified detections render **amber**, named identifications **emerald** — a
guess is never visually indistinguishable from a confirmed identification. Null
indices render as `n/a`, never `0`. Empty results get an explicit "No animals
detected — an empty frame is a normal camera-trap result" panel rather than a
blank space.

---

## 10. Schema

New alembic revision `b7c2e9d41a05`, chained off `386be452379f`. This fills in the
`image_detections` and `audio_classifications` tables that `docs/schema.md`
reserved for this milestone.

- **`species`** — catalog with taxonomy, GBIF/iNat keys, IUCN status and its source
- **`image_detections`** — label, confidence, bbox, `detector_label`,
  `candidate_label`, `posture_hint`, `is_unknown`
- **`audio_classifications`** — label, confidence, time window, `is_noise`
- **`analysis_runs`** — status, models used, `latency_ms`, animal count, quality
  score, error

`analysis_runs` exists because the specification requires image and audio
inference latency as performance metrics, and because a failed model load needs
somewhere honest to land.

---

## 11. Running it

```bash
docker compose up --build                                       # slow first build (~2 GB of ML deps)
docker compose exec backend python -m scripts.download_models   # ~450 MB, once
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.fetch_samples     # corpus + manifest (already committed)
docker compose exec backend python -m scripts.seed_dataset
docker compose exec backend python -m scripts.seed_species
docker compose exec backend pytest tests/ -q

# then, as an Administrator:
curl -X POST localhost:8000/analysis/run-pending -H "Authorization: Bearer <token>"
```

`scripts/try_engines.py` runs both engines over the corpus without a database —
useful for seeing raw model output directly.

Config added to `Settings`: `UPLOAD_DIR`, `MODEL_CACHE_DIR`, `ENABLE_ML`,
`DETECTION_CONF_THRESHOLD`, `CLASSIFICATION_CONF_THRESHOLD`,
`AUDIO_CONF_THRESHOLD`. `docker-compose.yml` now also passes `SECRET_KEY`, which
it never had — JWTs were being signed with the `config.py` default.

---

## 12. Measured results on the real corpus

Run with `scripts/try_engines.py`. These are actual outputs, including the misses.

**Images** — 0.3–0.6 s per image on CPU after warm-up.

| File | Ground truth | Result |
|---|---|---|
| `S1_B06_R1_PICT0016.JPG` | unlabelled (empty frame) | 0 animals, quality 0.94 — correct |
| `S1_B06_R1_PICT0017.JPG` | unlabelled (empty frame) | 0 animals, quality 0.93 (dawn capture) — correct |
| `387582910.jpg` | *Trifolium pratense* (a plant) | 0 animals — correctly rejected |
| `116714177.jpg` | *Richardia advena* (a fly) | "fly" 0.51 — correct at family level |
| `31991090.jpg` | *Breviceps gibbosus* (frog) | "tailed frog" 0.30 — correct at order level |
| `69033681.jpg` | *Ecnomiohyla rabborum* (treefrog) | "tree frog" 0.25 — correct at order level |
| `25020107.jpeg` | *Phrynocephalus mystaceus* (agama) | "frilled lizard" 0.26 — correct at order level |
| `159932888.jpeg` | *Chelydra serpentina* (turtle) | unidentified; YOLO said "elephant" 0.84, classifier disagreed — correctly withheld |
| `1539820.jpg` | *Anolis sagrei* | quality 0.58, "blurred or motion-smeared" — quality scoring working |
| `86030605.jpg` | *Aplopeltura boa* (snake) | quality 0.70, "underexposed; 28% of pixels crushed to black" |

**Audio** — 25–45 s per file before the windowing fix; substantially lower after.

| File | Ground truth | Result |
|---|---|---|
| `68688132.wav` | *Phrynomantis affinis* (frog) | "Frog" 0.87–0.97, "Croak" — correct at order level |
| `190098176.wav` | *Phoenicopterus ruber* (flamingo) | "Goose" 0.76, "Honk" — correct class (Aves), wrong species |
| `XC123456.mp3` | *Anodorhynchus hyacinthinus* (macaw) | "Bird", "Bird vocalization", "Fowl" — correct class, no species |
| `191645308.mp3` | *Phymonotus glyphopyrenos* (katydid) | only "Rustling leaves", filtered as noise — an honest miss |
| `212453209.wav` | *Pezoporus occidentalis* (night parrot) | events detected, nothing above threshold — an honest miss |

**The bird results are the expected outcome, not a failure.** AudioSet has no
parrot species class. Class-level agreement is what these models can deliver, and
`/analysis/metrics` reports it separately from species-level agreement for exactly
this reason.

---

## 13. Out of scope for Milestone 2

Deliberately not built, to keep this milestone to its stated boundaries:

- Population estimation, habitat intelligence, conservation recommendations,
  ecosystem health scoring — **Milestone 3**
- PDF and Excel export, GIS map visualisation — **Milestone 4**
- Cross-frame individual re-identification, and a trained behaviour classifier
- Celery/Redis, a service-layer abstraction, MongoDB usage
