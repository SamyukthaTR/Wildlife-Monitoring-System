# Wildlife Population Intelligence System — What We've Built So Far

This document walks through everything that has actually been built in Milestone 1 and Milestone 2 of the project, in plain language. No jargon dumps, no fluff — just what exists, where it lives in the codebase, and why it was built that way.

---

## The big picture

This is a platform for wildlife researchers, conservation officers, forest department officers, and admins to upload camera-trap images and field audio recordings and get back useful information: what animal is in the photo, what's making that sound, and how healthy the surrounding ecosystem looks based on species diversity.

It's split into three folders:

- **`backend`** — a FastAPI (Python) server that does all the real work: authentication, database access, and the AI models.
- **`frontend`** — a Next.js (React) web app where users actually log in and see their data.
- **`infra`** — Docker and environment configuration so the whole thing runs with one command.

Milestone 1 was about getting the foundation right — accounts, roles, sites, surveys, file uploads. Milestone 2 was about making the system actually *see* and *hear* wildlife — running real AI models on the uploaded files and turning the results into biodiversity numbers a researcher can use.

---

## Milestone 1 — The Foundation

### 1. User accounts and login

Anyone using the system falls into one of four roles: **Wildlife Researcher**, **Conservation Officer**, **Forest Department Officer**, or **Administrator**. This isn't just a label — it's enforced in the database as a strict PostgreSQL ENUM, so you can't accidentally end up with a typo'd role like "reseracher" sitting in the users table.

Registration and login work the standard way: you sign up with an email and password, the password gets hashed with bcrypt before it ever touches the database (never stored in plain text), and login gives you back a **JWT access token**.

The access/refresh token setup is worth explaining because it's a bit more thought-through than the bare minimum:
- The **access token** is short-lived and gets sent with every API request to prove who you are.
- The **refresh token** is long-lived and is stored as an **HttpOnly cookie** — meaning JavaScript in the browser can never read it, which protects it from XSS attacks. When the access token expires, the frontend silently calls `/auth/refresh` using this cookie to get a new one, so the user never gets randomly logged out mid-session.
- Logging out just clears that cookie.

There's also a stub for Google OAuth2 login (`/auth/google/callback`) that returns a "not implemented yet" message — it's scaffolded but not wired up, and the documentation is honest about that rather than pretending it works.

Every protected API route checks the token through a `get_current_user` dependency, and a `RoleChecker` helper restricts specific actions (like creating a monitoring site) to specific roles.

### 2. Monitoring sites, surveys, and devices

This is the core setup work a researcher does before any data collection happens:

- **Monitoring sites** — a physical location (say, a specific patch of forest) with a name, habitat type, whether it's inside a protected area, and its GPS coordinates. Coordinates aren't stored as two plain float columns; they use PostGIS's native `POINT` geometry type. That matters because it lets you later ask questions like "which sites are within 50km of this boundary" directly in SQL, instead of writing manual distance math over lat/lng floats.
- **Surveys** — a specific visit or campaign to a site, with a date and status (planned / active / completed). All uploaded data gets tied to a survey, which ties it to a site.
- **Devices** — the camera traps and audio sensors physically deployed at a site, tracked by serial number and status.

Only Researchers and Conservation Officers can create sites, surveys, and devices (enforced via `RoleChecker`); everyone with a valid login can view them.

### 3. File uploads (the raw data pipeline)

The `observation_log` table is where every uploaded image or audio file gets registered. A few deliberate choices here:

- Uploaded files get renamed to a random UUID before being saved to disk. This isn't cosmetic — it prevents path traversal attacks and filename collisions if two people upload files called `photo.jpg` on the same day.
- File size is capped at 50MB and only image/audio MIME types are accepted.
- Every observation starts with `processing_status = "pending"`. As you'll see in Milestone 2, this status field is what the AI pipeline updates as it works through the file.
- Visibility is role-aware: a Wildlife Researcher only sees their *own* uploads when listing observations, while other roles see everything.

Deliberately, this table was kept thin — it doesn't have columns for detected species, bounding boxes, or confidence scores. The reasoning documented in `docs/schema.md` is that the ML pipelines (added in Milestone 2) needed their own dedicated tables, so this table wouldn't turn into an overloaded catch-all that couples unrelated concerns together.

### 4. The database itself

PostgreSQL with the PostGIS extension is the primary database (for the spatial site data), and the project also provisions MongoDB for unstructured data/logs, though that hasn't actually been used yet in the modules built so far — it's there for when it's needed.

Schema changes are managed with Alembic migrations. The first migration (`386be452379f`) laid down `users`, `monitoring_sites`, `surveys`, `devices`, and `observation_log`.

### 5. The frontend shell

The Next.js app has:
- A login page and registration page.
- An `AuthContext` that holds the current user in React state, attempts a silent token refresh on page load, and exposes `login()`/`logout()` to the rest of the app.
- A `ProtectedRoute` wrapper component that redirects to `/login` if you're not authenticated, and redirects away if your role isn't allowed on that page — with a loading spinner in between so you don't see a flash of content you shouldn't.
- Role-based dashboard routing: the homepage (`/`) doesn't show any content itself — it just looks at your role and bounces you to the right dashboard (`/dashboards/researcher`, `/dashboards/admin`, etc).

At the end of Milestone 1, the Admin and Forest Officer dashboards were just placeholder shells (a header and a welcome message) — real functionality for those two roles is planned for a later milestone. The Researcher and Conservation Officer dashboards got built out properly in Milestone 2, described below.

### 6. Dataset ingestion groundwork

Before any AI model can be tested, you need real wildlife data to test it on. `docs/datasets.md` defines a common `DatasetAdapter` interface so that pulling data from different public biodiversity sources (iNaturalist, GBIF, Snapshot Serengeti, BirdCLEF/Xeno-canto) all funnels through the same ingestion script (`seed_dataset.py`) into the same `observation_log` table, tagged with a system user, site, survey, and device so it behaves exactly like real field data would.

Milestone 1 shipped an initial batch of 7 sample files this way. As you'll see below, this batch turned out to be mostly unusable and got fixed in Milestone 2.

---

## Milestone 2 — Teaching the System to See and Hear

This milestone is the heart of the project: real computer vision and audio AI models running on real wildlife data, plus the math to turn detections into biodiversity numbers.

### The guiding principle (this shaped everything)

Before getting into the features, it's worth explaining the rule that everything in this milestone follows, because it explains a lot of otherwise-odd-looking design decisions:

**Never claim more than the model actually supports.**

The AI models used here are general-purpose, off-the-shelf models — not custom-trained wildlife classifiers. ImageNet (which the species classifier is trained on) only has about 400 animal categories out of millions of real species, and the audio model's vocabulary (AudioSet) has zero species-level sound classes at all — it can tell you "bird" but never "scarlet macaw."

So rather than dressing up a low-confidence guess as a confident answer, the system is built to be honest about uncertainty everywhere:
- If the classifier isn't confident, the result is stored as `"unidentified animal"` — not the model's best guess dressed up as fact.
- Labels that only identify a group (like "bird" or "insect") are marked as **coarse rank** and kept *out* of species-level diversity calculations, because counting "bird" as a species would be wrong.
- Conservation status (IUCN) is only ever shown if a real source database actually published one for that record — it's never guessed or inferred.
- Diversity numbers are shown as "not applicable" rather than zero when they're mathematically undefined (an empty site isn't the same as a "dead" site with zero diversity).

This same principle is why the sample data problem (below) got fixed rather than left alone.

### 1. Fixing the sample data first

Before trusting any model output, the team actually looked at what the Milestone 1 sample corpus contained — and found it was mostly useless for testing a wildlife recognizer: two of the images were empty savanna frames, one "sample" was a photo of red clover (a plant, not an animal), and another was a pinned moth specimen photo. Testing a recognition engine against that would have generated a comfortable-looking but meaningless report.

So the corpus was expanded to **45 real files (34 images, 11 audio clips)** spanning all six species groups the project targets, with 43 of them carrying genuine species-level ground truth from their source databases (iNaturalist/GBIF community identifications) — so results can be checked against a real answer instead of taken on faith. All 7 original files were kept too, because even the "bad" ones are useful: the empty frames test that the system correctly reports "nothing detected," and the clover photo tests that the animal detector correctly rejects a non-animal.

Two smaller correctness fixes also went in here: observation timestamps now use the file's actual capture date instead of "the moment it was uploaded," and site coordinates use the sample's real GPS location instead of a placeholder `(0,0)` point.

### 2. The image analysis engine

Lives in `backend/app/ml/image.py` and `backend/app/ml/quality.py`. Here's what happens, step by step, when a camera-trap photo comes in:

1. **Quality check first.** Before anything else, the image is scored for blur (using Laplacian variance — basically, how much sharp detail there is), exposure (is it too dark/bright, are highlights or shadows clipped), and contrast. This produces a 0–1 quality score with a plain-English explanation attached, so a low-quality photo doesn't get silently misinterpreted as "no animals" when actually it's just too blurry to tell.
2. **Find the animals.** A YOLOv8n model (trained on the COCO dataset) scans the image and draws bounding boxes around anything in its 10 recognized animal categories (bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe — COCO's set, not a wildlife-specific one).
3. **Identify each one.** Each detected box gets cropped out (with a 10% padding margin, so horns/tails/legs sitting right at the box edge don't get chopped off) and run through a ResNet-50 classifier trained on ImageNet, which recognizes roughly 400 animal categories — many of which are real species.
4. **Whole-frame fallback.** If YOLO finds no animals at all — which happens a lot with insects and fish, since COCO doesn't have categories for them — the *entire* frame gets classified as one shot instead of giving up. This is literally the only way the system can identify insects or fish at all.
5. **Be honest about uncertainty.** If the classifier's confidence is below 25%, the result is stored as `"unidentified animal"` rather than whatever the model's top guess was — but the guess isn't thrown away either, it's kept as a `candidate_label` so a human reviewing the result can see "unidentified, closest match: terrapin (18%)" and make their own judgment call.

**Why the honesty rule actually matters here** — this isn't theoretical. On the real test corpus, the object detector confidently (84% confidence!) labeled a snapping turtle as an "elephant," and separately labeled a salamander as a "bird" at 93% confidence. Both are wrong, and both are exactly the kind of mistake a general-purpose detector makes when shown something outside its training categories. The classification stage disagreed with the detector in both cases, so both got correctly flagged as unidentified instead of being reported as confident (and wrong) answers.

One more honest limitation, documented rather than hidden: the system can count and identify multiple animals *within a single photo*, but it does **not** attempt to recognize that "the tiger in photo #47" is the same individual as "the tiger in photo #52" (that would need stripe/spot pattern matching, which wasn't built). Similarly, there's a rough "posture hint" (standing / lying / etc.) derived just from the shape of the bounding box — it's explicitly labeled everywhere as a simple geometric guess, not a real trained behavior classifier.

### 3. The bioacoustic (sound) analysis engine

Lives in `backend/app/ml/audio.py`. This one has more steps because raw audio is messier to work with than a single image:

1. **Load the recording** at a standard 16kHz mono format so every file is processed consistently.
2. **Figure out the noise floor.** The system looks at the quietest 10% of the recording (by energy) and treats that as "ambient background noise" — the constant hum of wind, insects, etc. between actual calls.
3. **Find the actual events.** Any stretch of audio that jumps at least 8 decibels above that noise floor gets flagged as a possible "event" (a call, a bark, a splash). Events less than 0.4 seconds apart get merged together, and anything shorter than 0.35 seconds gets thrown out as background noise rather than a real animal sound.
4. **Chop it into windows smartly.** The recording gets cut into consecutive ~10-second chunks (matching what the AI model expects as input), and *only* the chunks that actually contain a detected event get sent to the model. This sounds like a small detail but it was a real fix: an earlier approach centered a window on every single event, which meant that for a bird calling every two seconds, consecutive windows almost completely overlapped — the model was being asked to classify nearly the same 10 seconds of audio over and over, and one audio file took 84 seconds to process. The fixed approach dropped that dramatically.
5. **Classify and filter.** An AST (Audio Spectrogram Transformer) model trained on Google's AudioSet dataset (527 general sound categories) classifies each chunk. Results get split into "biological" sounds (bird/frog/insect/mammal calls) and "environmental" sounds (wind, rain, human speech, vehicles). Importantly, the environmental/noise labels are **kept in the results, just flagged `is_noise = true`**, rather than silently deleted — so if someone wants to double-check why a chunk got filtered out, the evidence is still there.

**The honest limitation here is a big one and worth stating plainly:** AudioSet has *no* species-level sound categories. This engine can tell you "that's a frog" or "that's a bird," but it cannot tell you *which* frog or *which* bird. So all acoustic identifications are stored at the coarse "class" level and are deliberately excluded from species-diversity math — counting "Bird" as if it were one species would inflate the numbers with something that isn't actually a species count.

### 4. The species catalog

`backend/app/modules/species/`. This is essentially the system's reference dictionary of every species/group it can recognize, built by merging four different sources:

- Real ground-truth identifications from the sample corpus (iNaturalist/GBIF) — these are the only entries with an actual verified conservation status.
- ImageNet's animal labels, cross-referenced against GBIF's official species database to attach real scientific names and taxonomy.
- COCO's 10 broad animal categories (kept at "coarse" rank, since "bird" isn't a species).
- AudioSet's roughly 60 biological sound categories (also kept at coarse rank).

Every entry records exactly which of these sources it came from (`label_source`), so nothing in the catalog pretends to be more precise than it actually is. Endangered status is pulled strictly from the official IUCN threatened categories (Critically Endangered, Endangered, Vulnerable) — never guessed.

### 5. Biodiversity math

`backend/app/modules/biodiversity/indices.py` — and this part is genuinely just math, no AI models involved, which is why it's unit-tested on its own (8 tests, no database needed). Given a set of species counts from a site or survey, it calculates the standard ecology metrics:

- **Species richness** — simply, how many distinct species were found.
- **Shannon diversity index** — a standard measure that accounts for both how many species there are and how evenly distributed they are.
- **Simpson's index** (and its two common variants, Gini-Simpson and inverse Simpson) — measures the probability that two randomly picked individuals belong to different species.
- **Pielou's evenness** — how evenly individuals are spread across the species present, independent of how many species there are.

The counting rule: one animal detected in one photo counts as one observation of that species. Coarse-rank labels (like "bird"), unidentified detections, and all acoustic detections are deliberately excluded from these calculations — but they're not silently dropped from the system, they're reported separately so nothing just disappears unexplained.

One subtle-but-important choice: when a calculation is mathematically undefined (for example, evenness is undefined when there's only one species — it's a 0/0 situation), the system reports it as "not applicable" rather than 0. And when a site has zero detections at all, every index shows "not applicable" with an explanation, rather than a row of zeros that would make an unsurveyed site look identical to a genuinely empty/dead one.

### 6. How analysis actually runs (the API flow)

When a file is uploaded, analysis doesn't block the upload response — it's queued as a background task. The uploader gets an immediate confirmation and the file's status moves through `pending → processing → completed` (or `failed`, with a readable error message, if a model couldn't load or the file was bad). Re-running analysis on the same file replaces its previous results rather than duplicating them.

Key endpoints added this milestone:
- Trigger or re-trigger analysis on a specific observation, or run analysis across every pending item in the seeded corpus at once (admin-only).
- Look up an observation's detections along with an `interpretation` block that spells out, in plain language, what fields like `is_unknown` or `posture_hint` do and don't mean — so nobody consuming the raw API mistakes a coarse guess for a confirmed species ID.
- Browse and search the species catalog, filtered by group, taxonomic rank, endangered status, or whether it's actually been detected in the data.
- Pull biodiversity indices, species composition, and acoustic activity, per site or per survey.
- Generate a monitoring report as JSON or CSV (PDF/Excel export is planned for a later milestone).
- Check which models successfully loaded and why any didn't, plus accuracy-against-ground-truth and latency numbers, via a metrics endpoint.

### 7. The frontend catches up

The Researcher and Conservation Officer dashboards were built out properly this milestone:
- The Researcher dashboard now has "Analyze" and "Re-analyze" buttons on uploads, status badges, and a results modal that shows either the photo with bounding boxes drawn over it, or an audio timeline for sound files — and it polls automatically while analysis is still running.
- The Conservation Officer dashboard surfaces species of conservation concern grouped by IUCN category, plus a chart of the most frequently detected species.
- A new Biodiversity page shows the diversity index cards, a species composition chart, acoustic activity, and side-by-side comparison across sites.

A couple of small but meaningful UI conventions worth mentioning: unidentified detections are always shown in amber/orange, while confirmed species identifications are shown in green — so a low-confidence guess is never visually confusable with a real answer at a glance. Similarly, "not applicable" values render as literal text like "n/a," never as a bare 0 that could be misread as "measured and found to be zero." And an empty result (no animals in a photo) gets an explicit message explaining that an empty camera-trap frame is a completely normal, expected outcome — not a blank space that looks like something broke.

### 8. Database changes

A second Alembic migration (`b7c2e9d41a05`) added four new tables to support all of this:
- **`species`** — the catalog described above, with taxonomy, external database IDs, and conservation status.
- **`image_detections`** — every animal detection: label, confidence, bounding box, plus the honesty fields (`detector_label`, `candidate_label`, `is_unknown`, `posture_hint`).
- **`audio_classifications`** — every acoustic detection: label, confidence, time window, and the `is_noise` flag.
- **`analysis_runs`** — a log of every analysis job: which models were used, how long it took, how many animals were found, the quality score, and any error. This table exists specifically because inference speed needed to be measurable, and because a failed model load needed somewhere honest to be recorded instead of just erroring out silently.

### 9. Measured, real results (not projected numbers)

The team actually ran the finished pipeline against the real 45-file test corpus and recorded what happened, misses included:

- Images process in roughly 0.3–0.6 seconds each on a regular CPU (no GPU needed) once the models are warmed up.
- Correct results included: empty frames correctly identified as having zero animals, the clover photo correctly rejected as not containing an animal, a fly and two frogs correctly identified at the family/order level, and — importantly — the snapping turtle that YOLO mislabeled as "elephant" at 84% confidence got correctly withheld as "unidentified" because the classification stage disagreed.
- On audio, results like labeling a flamingo recording as "Goose" show the honest ceiling of this approach: it got the right general class (a bird making a honking sound) but couldn't get the species, because the audio model simply has no species-level bird categories to choose from. This is explicitly treated as an expected outcome of using a general-purpose sound model, not a bug — and the system's metrics endpoint reports species-level accuracy and class-level accuracy separately for exactly this reason.

### 10. What was deliberately left out of Milestone 2

To keep this milestone focused, a few things were consciously scoped out rather than half-built:
- Population size estimation, habitat quality scoring, and conservation recommendations — planned for Milestone 3.
- PDF/Excel report export and map-based (GIS) visualization — planned for Milestone 4.
- Matching the same individual animal across multiple photos, and a real trained animal-behavior classifier (both would need specialized annotated datasets that weren't part of this phase).
- Heavier infrastructure like Celery/Redis task queues or a separate service-layer abstraction — not needed yet at this scale, so not added prematurely.

---

## Where things stand, in one paragraph

Milestone 1 built a working, role-based platform: real authentication with secure token handling, spatially-aware site/survey/device management, and a safe file upload pipeline — all backed by a properly migrated PostgreSQL/PostGIS schema. Milestone 2 turned that pipeline into something genuinely useful by wiring in real (if general-purpose) computer vision and audio AI models, and — just as importantly — built the entire system around being honest about what those models can and can't actually tell you, rather than dressing up uncertain guesses as confident answers. The biodiversity math on top of it is standard, peer-reviewed ecology — nothing invented — applied carefully to only the detections that are actually species-level and trustworthy enough to count.
