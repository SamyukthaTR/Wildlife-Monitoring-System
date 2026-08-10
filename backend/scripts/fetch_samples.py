"""
Acquire the genuine wildlife sample corpus used to seed the platform.

Every file downloaded here is a real observation from a public biodiversity
database, and every record keeps its upstream identifier, licence, contributor
attribution, real capture date and real coordinates. Nothing is synthesised and
nothing is relabelled: what the source says the animal is, is what we store as
ground truth.

That ground truth is what makes `GET /analysis/metrics` an honest measurement
rather than a claim -- model predictions are compared against the community
identification supplied by the source, at the taxonomic rank the model actually
operates at.

Sources (all free, no API key required):
  - iNaturalist  https://api.inaturalist.org/v1/  research-grade observations
  - Xeno-canto   https://xeno-canto.org/api/2/    bird sound recordings
  - GBIF         https://api.gbif.org/v1/         occurrence records

Run:  python -m scripts.fetch_samples
Output: backend/scripts/sample_data/<source>/<file>  +  sample_data/manifest.json

Uses only the standard library so it can be run on the host or in the container.
"""

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(SCRIPT_DIR, "sample_data")
MANIFEST_PATH = os.path.join(SAMPLE_DIR, "manifest.json")

USER_AGENT = (
    "WildlifePopulationIntelligenceSystem/0.2 "
    "(educational conservation-analytics project; dataset seeding)"
)

# Certificates are verified. The earlier one-off fetch scripts in this repo
# disabled verification; that is not repeated here.
SSL_CONTEXT = ssl.create_default_context()

# iNaturalist iconic taxa -> the species_group vocabulary used by the platform.
# Covers the six groups named in the project specification.
ICONIC_TAXA = [
    ("Mammalia", "mammal"),
    ("Aves", "bird"),
    ("Reptilia", "reptile"),
    ("Amphibia", "amphibian"),
    ("Insecta", "insect"),
    ("Actinopterygii", "marine"),
]

# Licences we are willing to redistribute in the repo. "All rights reserved"
# photos are skipped even though the API will happily serve them.
OPEN_LICENCES = {"cc0", "cc-by", "cc-by-nc", "cc-by-sa", "cc-by-nc-sa"}

PHOTOS_PER_GROUP = 5
# Still images only. Animated GIFs decode to a first frame that is often not
# representative, so they are skipped rather than silently mis-analysed.
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png")

# soundfile reads these directly. M4A/AAC needs an external ffmpeg binary via
# audioread, which is present in the container but not on every host, so those
# uploads are skipped here to keep the corpus portable.
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac")

# Xeno-canto retired its keyless v2 API; v3 requires a personal API key that
# cannot be committed. Bird audio therefore comes from iNaturalist, which
# carries the same kind of community-verified identification.
INAT_SOUND_GROUPS = [("Aves", "bird"), ("Amphibia", "amphibian"), ("Insecta", "insect")]
INAT_SOUNDS_PER_GROUP = 3

HTTP_RETRIES = 3


def _http_get(url: str, timeout: int) -> bytes:
    """GET with retries. iNaturalist intermittently truncates large responses."""
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last_error = exc
            if attempt < HTTP_RETRIES:
                time.sleep(2 * attempt)
    raise last_error  # type: ignore[misc]


def http_json(url: str, params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return json.loads(_http_get(url, timeout=60).decode("utf-8"))


def http_download(url: str, dest: str) -> int:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = _http_get(url, timeout=120)
    with open(dest, "wb") as fh:
        fh.write(data)
    return len(data)


def taxonomy_from_inat(taxon: dict) -> dict:
    """Pull rank-keyed taxonomy out of an iNaturalist taxon object."""
    ranks = {}
    for ancestor in taxon.get("ancestors") or []:
        ranks[ancestor.get("rank")] = ancestor.get("name")
    ranks[taxon.get("rank")] = taxon.get("name")

    status = taxon.get("conservation_status") or {}
    iucn_status = status.get("status")
    iucn_authority = status.get("authority")

    return {
        "scientific_name": taxon.get("name"),
        "common_name": (taxon.get("preferred_common_name") or "").strip() or None,
        "rank": taxon.get("rank"),
        "taxon_class": ranks.get("class"),
        "taxon_order": ranks.get("order"),
        "taxon_family": ranks.get("family"),
        "inat_taxon_id": taxon.get("id"),
        # Left null unless the source actually carries a status. Never guessed.
        "iucn_status": iucn_status.upper() if iucn_status else None,
        "iucn_source": (
            f"iNaturalist conservation_status (authority: {iucn_authority})"
            if iucn_status else None
        ),
    }


def inat_observation_record(obs: dict, group: str, kind: str) -> dict | None:
    """Build a manifest record from an iNaturalist observation."""
    taxon = obs.get("taxon") or {}
    if not taxon.get("name"):
        return None

    lat = lng = None
    geo = obs.get("geojson") or {}
    if geo.get("coordinates"):
        lng, lat = geo["coordinates"][0], geo["coordinates"][1]

    return {
        "source": "iNaturalist",
        "source_id": str(obs["id"]),
        "url": obs.get("uri"),
        "observed_on": obs.get("time_observed_at") or obs.get("observed_on"),
        "latitude": lat,
        "longitude": lng,
        # iNaturalist blurs locations for threatened taxa. We record that fact
        # rather than substituting a plausible-looking coordinate.
        "coordinates_obscured": obs.get("obscured", False) or obs.get("geoprivacy") == "obscured",
        "species_group": group,
        "media_kind": kind,
        "ground_truth": taxonomy_from_inat(taxon),
    }


def fetch_inat_photos(seen_taxa: set, have_per_group: dict) -> list[dict]:
    records = []
    for iconic, group in ICONIC_TAXA:
        needed = PHOTOS_PER_GROUP - have_per_group.get(group, 0)
        if needed <= 0:
            print(f"  iNaturalist photos: {iconic} ({group}) -- already have {have_per_group[group]}, skipping")
            continue
        print(f"  iNaturalist photos: {iconic} ({group}) -- need {needed}")
        try:
            payload = http_json(
                "https://api.inaturalist.org/v1/observations",
                {
                    "quality_grade": "research",
                    "iconic_taxa": iconic,
                    "photos": "true",
                    "identifications": "most_agree",
                    "rank": "species",
                    "order_by": "votes",
                    "order": "desc",
                    "per_page": 40,
                    "page": 1,
                },
            )
        except Exception as exc:  # noqa: BLE001 - surface and continue
            print(f"    [WARN] request failed: {exc}")
            continue

        taken = 0
        for obs in payload.get("results", []):
            if taken >= needed:
                break
            taxon = obs.get("taxon") or {}
            if taxon.get("rank") != "species" or taxon.get("id") in seen_taxa:
                continue
            photos = obs.get("photos") or []
            if not photos:
                continue
            photo = photos[0]
            licence = (photo.get("license_code") or "").lower()
            if licence not in OPEN_LICENCES:
                continue
            # The API returns a square thumbnail URL; request the large variant.
            url = (photo.get("url") or "").replace("/square.", "/large.")
            if not url:
                continue

            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
            if ext.lower() not in PHOTO_EXTENSIONS:
                continue
            rel = f"inaturalist/{obs['id']}{ext}"
            dest = os.path.join(SAMPLE_DIR, rel)
            try:
                size = http_download(url, dest)
            except Exception as exc:  # noqa: BLE001
                print(f"    [WARN] download failed for {obs['id']}: {exc}")
                continue

            record = inat_observation_record(obs, group, "image")
            if not record:
                continue
            record.update({
                "file": rel,
                "bytes": size,
                "license": licence.upper(),
                "attribution": photo.get("attribution") or obs.get("user", {}).get("login"),
                "media_url": url,
            })
            records.append(record)
            seen_taxa.add(taxon["id"])
            taken += 1
            print(f"    + {rel}  {record['ground_truth']['scientific_name']}")
            time.sleep(1.0)  # be polite to the API

        if taken < needed:
            print(f"    [note] only {taken}/{needed} usable for {iconic}")
    return records


def fetch_inat_sounds(seen_taxa: set, have_per_group: dict) -> list[dict]:
    """Bird, amphibian and insect audio, all community-identified."""
    records = []
    for iconic, group in INAT_SOUND_GROUPS:
        needed = INAT_SOUNDS_PER_GROUP - have_per_group.get(group, 0)
        if needed <= 0:
            print(f"  iNaturalist sounds: {iconic} ({group}) -- already have {have_per_group[group]}, skipping")
            continue
        print(f"  iNaturalist sounds: {iconic} ({group}) -- need {needed}")
        try:
            payload = http_json(
                "https://api.inaturalist.org/v1/observations",
                {
                    "quality_grade": "research",
                    "iconic_taxa": iconic,
                    "sounds": "true",
                    "rank": "species",
                    "order_by": "votes",
                    "order": "desc",
                    "per_page": 30,
                },
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    [WARN] request failed: {exc}")
            continue

        taken = 0
        for obs in payload.get("results", []):
            if taken >= needed:
                break
            taxon = obs.get("taxon") or {}
            if taxon.get("rank") != "species" or taxon.get("id") in seen_taxa:
                continue
            sounds = obs.get("sounds") or []
            if not sounds:
                continue
            sound = sounds[0]
            licence = (sound.get("license_code") or "").lower()
            if licence not in OPEN_LICENCES:
                continue
            url = sound.get("file_url")
            if not url:
                continue

            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            rel = f"inaturalist_audio/{obs['id']}{ext}"
            dest = os.path.join(SAMPLE_DIR, rel)
            try:
                size = http_download(url, dest)
            except Exception as exc:  # noqa: BLE001
                print(f"    [WARN] download failed for {obs['id']}: {exc}")
                continue

            record = inat_observation_record(obs, group, "audio")
            if not record:
                continue
            record.update({
                "file": rel,
                "bytes": size,
                "license": licence.upper(),
                "attribution": sound.get("attribution") or obs.get("user", {}).get("login"),
                "media_url": url,
            })
            records.append(record)
            seen_taxa.add(taxon["id"])
            taken += 1
            print(f"    + {rel}  {record['ground_truth']['scientific_name']}")
            time.sleep(1.0)
    return records


# --------------------------------------------------------------------------
# Back-fill provenance for the files already committed by Milestone 1.
# These were downloaded without recording their real capture metadata; we now
# re-query the source APIs for it instead of leaving the seeder to stamp
# datetime.now() and POINT(0 0).
# --------------------------------------------------------------------------

def backfill_existing() -> list[dict]:
    records = []

    # Snapshot Serengeti camera-trap frames from LILA BC. The per-image species
    # labels live in a multi-GB season metadata file that is not bundled here,
    # so ground truth is recorded as unavailable rather than assumed. Capture
    # times below are read from the files' own EXIF DateTimeOriginal.
    serengeti = [
        ("S1_B06_R1_PICT0016.JPG", "2010-07-23T09:55:58"),
        ("S1_B06_R1_PICT0017.JPG", "2010-07-24T07:09:28"),
    ]
    for filename, captured in serengeti:
        path = os.path.join(SAMPLE_DIR, "snapshot_serengeti", filename)
        if not os.path.exists(path):
            continue
        records.append({
            "source": "Snapshot Serengeti (LILA BC)",
            "source_id": os.path.splitext(filename)[0],
            "url": "https://lila.science/datasets/snapshot-serengeti",
            "file": f"snapshot_serengeti/{filename}",
            "bytes": os.path.getsize(path),
            "license": "CDLA-Permissive-1.0",
            "attribution": "Snapshot Serengeti / Snapshot Safari",
            "observed_on": captured,
            "latitude": None,
            "longitude": None,
            "coordinates_obscured": False,
            "coordinates_note": (
                "Per-camera coordinates are not published for Snapshot Serengeti "
                "season 1 site B06; left null rather than approximated."
            ),
            "species_group": None,
            "media_kind": "image",
            "ground_truth": None,
            "ground_truth_note": (
                "Species label not bundled with this sample (LILA season metadata "
                "not distributed here). Excluded from accuracy measurement."
            ),
        })

    # iNaturalist and GBIF records already present -- re-query for real metadata.
    legacy_inat = _first_file(os.path.join(SAMPLE_DIR, "inaturalist"), (".jpg", ".jpeg"))
    if legacy_inat:
        obs_id = os.path.splitext(os.path.basename(legacy_inat))[0]
        if obs_id.isdigit():
            rec = _refetch_inat(obs_id, legacy_inat)
            if rec:
                records.append(rec)

    legacy_gbif = _first_file(os.path.join(SAMPLE_DIR, "gbif"), (".jpg", ".jpeg"))
    if legacy_gbif:
        occ_id = os.path.splitext(os.path.basename(legacy_gbif))[0]
        if occ_id.isdigit():
            rec = _refetch_gbif(occ_id, legacy_gbif)
            if rec:
                records.append(rec)

    # The two Milestone 1 MP3s are Xeno-canto recordings whose real identifiers
    # are in their ID3 comments; re-query the API for authoritative metadata.
    for filename in sorted(os.listdir(os.path.join(SAMPLE_DIR, "birdclef"))) \
            if os.path.isdir(os.path.join(SAMPLE_DIR, "birdclef")) else []:
        if not filename.lower().endswith(".mp3"):
            continue
        path = os.path.join(SAMPLE_DIR, "birdclef", filename)
        rec = _legacy_xenocanto_from_tags(path, f"birdclef/{filename}")
        if rec:
            records.append(rec)
    return records


def _first_file(directory: str, extensions: tuple) -> str | None:
    if not os.path.isdir(directory):
        return None
    for name in sorted(os.listdir(directory)):
        if name.lower().endswith(extensions):
            return os.path.join(directory, name)
    return None


def _refetch_inat(obs_id: str, path: str) -> dict | None:
    try:
        payload = http_json(f"https://api.inaturalist.org/v1/observations/{obs_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"    [WARN] iNat re-fetch {obs_id} failed: {exc}")
        return None
    results = payload.get("results") or []
    if not results:
        return None
    obs = results[0]
    taxon = obs.get("taxon") or {}
    kingdom = None
    for ancestor in taxon.get("ancestors") or []:
        if ancestor.get("rank") == "kingdom":
            kingdom = ancestor.get("name")
    record = inat_observation_record(obs, "other", "image")
    if not record:
        return None
    photos = obs.get("photos") or []
    record.update({
        "file": f"inaturalist/{os.path.basename(path)}",
        "bytes": os.path.getsize(path),
        "license": (photos[0].get("license_code") or "unknown").upper() if photos else "unknown",
        "attribution": photos[0].get("attribution") if photos else None,
    })
    if kingdom and kingdom != "Animalia":
        # Retained deliberately: a correctly-rejected non-animal is a real test
        # of the detector, not a mistake in the corpus.
        record["species_group"] = None
        record["non_animal"] = True
        record["ground_truth_note"] = (
            f"Kingdom {kingdom}, not an animal. Kept as a true-negative case for "
            "the animal detector; excluded from species accuracy measurement."
        )
    return record


def _refetch_gbif(occ_id: str, path: str) -> dict | None:
    try:
        occ = http_json(f"https://api.gbif.org/v1/occurrence/{occ_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"    [WARN] GBIF re-fetch {occ_id} failed: {exc}")
        return None
    return {
        "source": "GBIF",
        "source_id": str(occ_id),
        "url": f"https://www.gbif.org/occurrence/{occ_id}",
        "file": f"gbif/{os.path.basename(path)}",
        "bytes": os.path.getsize(path),
        "license": occ.get("license"),
        "attribution": occ.get("rightsHolder") or occ.get("institutionCode"),
        "observed_on": occ.get("eventDate"),
        "latitude": occ.get("decimalLatitude"),
        "longitude": occ.get("decimalLongitude"),
        "coordinates_obscured": False,
        "species_group": "insect" if occ.get("class") == "Insecta" else None,
        "media_kind": "image",
        "ground_truth": {
            "scientific_name": occ.get("species") or occ.get("scientificName"),
            "common_name": None,
            "rank": (occ.get("taxonRank") or "").lower() or None,
            "taxon_class": occ.get("class"),
            "taxon_order": occ.get("order"),
            "taxon_family": occ.get("family"),
            "gbif_taxon_key": occ.get("speciesKey") or occ.get("taxonKey"),
            "inat_taxon_id": None,
            "iucn_status": None,
            "iucn_source": None,
        },
        "ground_truth_note": (
            "Preserved museum specimen photographed against a scale bar, not a "
            "field observation. Kept because it exercises the insect path."
        ),
    }


def read_id3_tags(path: str) -> dict:
    """Minimal ID3v2 text-frame reader (stdlib only).

    The Milestone 1 MP3s carry their provenance in their own ID3 tags. The
    keyless Xeno-canto v2 API these were downloaded through has since been
    retired, so the tags embedded in the files are now the authoritative record.
    """
    tags: dict = {}
    try:
        with open(path, "rb") as fh:
            header = fh.read(10)
            if len(header) < 10 or header[:3] != b"ID3":
                return tags
            # Synchsafe 28-bit size across the last four header bytes.
            size = 0
            for byte in header[6:10]:
                size = (size << 7) | (byte & 0x7F)
            body = fh.read(size)

        offset = 0
        while offset + 10 <= len(body):
            frame_id = body[offset:offset + 4].decode("latin-1", "ignore")
            if not frame_id.strip("\x00"):
                break
            frame_size = int.from_bytes(body[offset + 4:offset + 8], "big")
            if frame_size <= 0 or offset + 10 + frame_size > len(body):
                break
            payload = body[offset + 10:offset + 10 + frame_size]
            if frame_id.startswith("T") or frame_id == "COMM":
                encoding = payload[0] if payload else 0
                raw = payload[1:]
                codec = "utf-16" if encoding in (1, 2) else "utf-8" if encoding == 3 else "latin-1"
                text = raw.decode(codec, "ignore")
                if frame_id == "COMM":
                    # language (3 bytes) + short description + NUL + text
                    parts = text.split("\x00")
                    text = parts[-1] if parts else text
                tags[frame_id] = text.strip("\x00").strip()
            offset += 10 + frame_size
    except Exception as exc:  # noqa: BLE001
        print(f"    [WARN] could not read ID3 from {path}: {exc}")
    return tags


def _legacy_xenocanto_from_tags(path: str, rel: str) -> dict | None:
    """Build a manifest record for a Milestone 1 MP3 from its embedded tags."""
    tags = read_id3_tags(path)
    title = tags.get("TIT2") or ""
    comment = tags.get("COMM") or ""

    # Title format written by Xeno-canto: "Common Name (Genus species)"
    common_name = scientific_name = None
    if "(" in title and title.endswith(")"):
        common_name = title[:title.rindex("(")].strip() or None
        scientific_name = title[title.rindex("(") + 1:-1].strip() or None
    elif title:
        common_name = title.strip()

    # Comment format: "XC123456 . Recordist // Place (lat, lng), Country // ..."
    lat = lng = None
    if "(" in comment and ")" in comment:
        inner = comment[comment.index("(") + 1:comment.index(")")]
        bits = [b.strip() for b in inner.split(",")]
        if len(bits) == 2:
            try:
                lat, lng = float(bits[0]), float(bits[1])
            except ValueError:
                lat = lng = None

    observed_on = None
    for chunk in comment.split("//"):
        chunk = chunk.strip()
        # e.g. "07:09h, 2011-08-31"
        if "-" in chunk and len(chunk) >= 10:
            candidate = chunk.split(",")[-1].strip()
            if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
                observed_on = candidate
                break

    source_id = os.path.splitext(os.path.basename(path))[0]
    return {
        "source": "Xeno-canto",
        "source_id": source_id,
        "url": f"https://xeno-canto.org/{source_id.lstrip('XCxc')}",
        "file": rel,
        "bytes": os.path.getsize(path),
        "license": tags.get("TCOP") or "see xeno-canto.org record",
        "attribution": tags.get("TPE1"),
        "observed_on": observed_on,
        "latitude": lat,
        "longitude": lng,
        "coordinates_obscured": False,
        "species_group": "bird",
        "media_kind": "audio",
        "provenance_note": (
            "Metadata read from the file's own ID3 tags. Xeno-canto retired its "
            "keyless v2 API, so this could not be re-verified against the live "
            "service at fetch time."
        ),
        "ground_truth": {
            "scientific_name": scientific_name,
            "common_name": common_name,
            "rank": "species" if scientific_name and " " in scientific_name else None,
            "taxon_class": "Aves",
            "taxon_order": None,
            "taxon_family": tags.get("TCON"),
            "inat_taxon_id": None,
            "iucn_status": None,
            "iucn_source": None,
        },
    }


def load_existing_manifest() -> list[dict]:
    """Previously downloaded records, so a re-run tops up rather than restarts.

    Entries whose media file has since been deleted are dropped.
    """
    if not os.path.exists(MANIFEST_PATH):
        return []
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            previous = json.load(fh).get("records", [])
    except (OSError, json.JSONDecodeError):
        return []
    return [r for r in previous if os.path.exists(os.path.join(SAMPLE_DIR, r.get("file", "")))]


def main() -> int:
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    print("Fetching genuine wildlife samples...\n")

    # Resume: keep what previous runs already downloaded, re-derive back-filled
    # provenance (cheap and idempotent), and only fetch groups still short.
    previous = [r for r in load_existing_manifest() if r.get("source") == "iNaturalist"
                and r.get("ground_truth")]
    seen_taxa = {
        (r.get("ground_truth") or {}).get("inat_taxon_id")
        for r in previous
        if (r.get("ground_truth") or {}).get("inat_taxon_id")
    }
    have_photos: dict = {}
    have_sounds: dict = {}
    for rec in previous:
        bucket = have_photos if rec.get("media_kind") == "image" else have_sounds
        group = rec.get("species_group")
        if group:
            bucket[group] = bucket.get(group, 0) + 1

    if previous:
        print(f"Resuming: {len(previous)} downloaded records already on disk\n")

    print("Back-filling provenance for existing files")
    records: list[dict] = backfill_existing()
    records += previous

    print("\nDownloading new labelled samples")
    records += fetch_inat_photos(seen_taxa, have_photos)
    records += fetch_inat_sounds(seen_taxa, have_sounds)

    # A file carried over from a previous run can also be re-derived by the
    # back-fill pass, so collapse on the media path. Back-fill entries come
    # first and win, since they carry the richer provenance notes.
    deduped: dict[str, dict] = {}
    for record in records:
        deduped.setdefault(record["file"], record)
    records = list(deduped.values())

    manifest = {
        "generated_by": "scripts/fetch_samples.py",
        "note": (
            "Every entry is a real record from a public biodiversity database. "
            "Ground truth is the source's own identification and is used to "
            "measure model accuracy. Fields are null where the source does not "
            "publish them; no value here is estimated or invented."
        ),
        "sources": {
            "iNaturalist": "https://api.inaturalist.org/v1/ (research-grade observations)",
            "GBIF": "https://api.gbif.org/v1/ (occurrence records)",
            "Snapshot Serengeti": "https://lila.science/datasets/snapshot-serengeti",
            "Xeno-canto": (
                "https://xeno-canto.org/ -- the two Milestone 1 recordings only. "
                "Its keyless v2 API has been retired and v3 needs a personal key, "
                "so their metadata is read from the files' own ID3 tags and newer "
                "audio comes from iNaturalist instead."
            ),
        },
        "records": records,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    images = sum(1 for r in records if r.get("media_kind") == "image")
    audio = sum(1 for r in records if r.get("media_kind") == "audio")
    labelled = sum(1 for r in records if (r.get("ground_truth") or {}).get("scientific_name"))
    total_bytes = sum(r.get("bytes") or 0 for r in records)

    print(
        f"\nManifest written: {MANIFEST_PATH}\n"
        f"  {len(records)} files ({images} image, {audio} audio), "
        f"{labelled} with species-level ground truth, "
        f"{total_bytes / 1_048_576:.1f} MB total"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
