"""Build the species catalog.

Four sources feed the catalog, and each row records which one it came from:

  1. corpus ground truth   -- the identifications iNaturalist/GBIF attached to
                              the seeded media, including real IUCN status
  2. ImageNet-1k animals   -- the classifier's ~398 animal labels, resolved
                              against the GBIF backbone taxonomy
  3. COCO animal classes   -- the detector's ten labels, all coarse
  4. AudioSet biological   -- the audio model's sound-type labels, all coarse

Nothing is invented. A label GBIF cannot match keeps its raw name, is stored at
coarse rank with no taxonomy, and `gbif_match_type` records the miss. IUCN
status stays null unless a source published one.

Run: python -m scripts.seed_species
Safe to re-run; existing rows are updated in place.
"""

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

from app.core.database import SessionLocal
from app.ml import labels as label_maps
from app.modules.species.catalog import (
    group_from_string,
    group_from_taxon_class,
    is_threatened,
)
from app.modules.species.models import Species, SpeciesGroupEnum, TaxonRankEnum

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "sample_data", "manifest.json")

USER_AGENT = "WildlifePopulationIntelligenceSystem/0.2 (species catalog build)"
SSL_CONTEXT = ssl.create_default_context()
GBIF_DELAY = 0.12  # seconds between GBIF calls


# ---------------------------------------------------------------------------
# GBIF backbone taxonomy
# ---------------------------------------------------------------------------

def gbif_lookup(name: str) -> dict | None:
    """Resolve a name against the GBIF backbone.

    Tries the scientific-name matcher first. ImageNet labels are common names
    ("African elephant"), which that matcher often misses, so a vernacular
    search is used as a fallback. Whichever path succeeded is recorded.
    """
    match = _gbif_get(
        "https://api.gbif.org/v1/species/match",
        {"name": name, "strict": "false"},
    )
    if match and match.get("matchType") not in (None, "NONE"):
        return _from_gbif_payload(match, match.get("matchType"))

    search = _gbif_get(
        "https://api.gbif.org/v1/species/search",
        {
            "q": name,
            "qField": "VERNACULAR",
            "rank": "SPECIES",
            "status": "ACCEPTED",
            "datasetKey": "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",  # GBIF backbone
            "limit": 1,
        },
    )
    results = (search or {}).get("results") or []
    if results:
        return _from_gbif_payload(results[0], "VERNACULAR_SEARCH")

    return None


def _gbif_get(url: str, params: dict) -> dict | None:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - a miss is a valid, recorded outcome
        return None
    finally:
        time.sleep(GBIF_DELAY)


def _from_gbif_payload(payload: dict, match_type: str | None) -> dict:
    rank = (payload.get("rank") or "").upper()
    return {
        "scientific_name": payload.get("species") or payload.get("scientificName")
        or payload.get("canonicalName"),
        "taxon_class": payload.get("class"),
        "taxon_order": payload.get("order"),
        "taxon_family": payload.get("family"),
        "gbif_taxon_key": payload.get("speciesKey") or payload.get("usageKey")
        or payload.get("key"),
        "gbif_match_type": match_type,
        "gbif_rank": rank,
    }


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert(db, *, scientific_name: str, model_label: str | None, label_source: str,
           rank: TaxonRankEnum, group: SpeciesGroupEnum, common_name: str | None = None,
           taxon_class: str | None = None, taxon_order: str | None = None,
           taxon_family: str | None = None, gbif_taxon_key: int | None = None,
           gbif_match_type: str | None = None, inat_taxon_id: int | None = None,
           iucn_status: str | None = None, iucn_source: str | None = None) -> Species:
    """Insert or update one catalog row, keyed on scientific_name."""
    species = db.query(Species).filter(Species.scientific_name == scientific_name).first()
    if species is None:
        species = Species(scientific_name=scientific_name)
        db.add(species)
        # autoflush is off on this session, so a later upsert() call in the
        # same uncommitted batch needs this flushed to see it and avoid
        # inserting a second row for the same scientific_name.
        db.flush()

    species.common_name = common_name or species.common_name
    species.rank = rank
    species.species_group = group
    species.taxon_class = taxon_class or species.taxon_class
    species.taxon_order = taxon_order or species.taxon_order
    species.taxon_family = taxon_family or species.taxon_family
    species.gbif_taxon_key = gbif_taxon_key or species.gbif_taxon_key
    species.gbif_match_type = gbif_match_type or species.gbif_match_type
    species.inat_taxon_id = inat_taxon_id or species.inat_taxon_id

    # Ground truth carries real IUCN status; never overwrite it with a null.
    if iucn_status:
        species.iucn_status = iucn_status
        species.iucn_source = iucn_source
        species.is_endangered = is_threatened(iucn_status)

    # First writer wins on model_label so a species-level ground-truth row is
    # not later hijacked by a coarse model label.
    if model_label and not species.model_label:
        species.model_label = model_label.strip().lower()
    species.label_source = species.label_source or label_source
    return species


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def seed_from_manifest(db) -> int:
    """Ground truth of the seeded corpus -- the only source of IUCN status."""
    if not os.path.exists(MANIFEST_PATH):
        print(f"  [WARN] no manifest at {MANIFEST_PATH}; run scripts.fetch_samples first")
        return 0

    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        records = json.load(fh).get("records", [])

    count = 0
    for record in records:
        truth = record.get("ground_truth") or {}
        name = truth.get("scientific_name")
        if not name:
            continue
        group = group_from_string(record.get("species_group")) if record.get("species_group") \
            else group_from_taxon_class(truth.get("taxon_class"))
        upsert(
            db,
            scientific_name=name,
            model_label=None,  # ground truth is not a model vocabulary
            label_source="corpus-groundtruth",
            rank=TaxonRankEnum.SPECIES if (truth.get("rank") == "species") else TaxonRankEnum.GENUS,
            group=group,
            common_name=truth.get("common_name"),
            taxon_class=truth.get("taxon_class"),
            taxon_order=truth.get("taxon_order"),
            taxon_family=truth.get("taxon_family"),
            gbif_taxon_key=truth.get("gbif_taxon_key"),
            inat_taxon_id=truth.get("inat_taxon_id"),
            iucn_status=truth.get("iucn_status"),
            iucn_source=truth.get("iucn_source"),
        )
        count += 1
    db.commit()
    return count


def seed_coco(db) -> int:
    """The detector's ten animal classes. All coarse by construction."""
    for label, info in label_maps.COCO_ANIMAL_CLASSES.items():
        upsert(
            db,
            scientific_name=info["taxon"],
            model_label=label,
            label_source="yolov8n-coco",
            rank=TaxonRankEnum.COARSE,
            group=group_from_string(info["group"]),
            common_name=label,
        )
    db.commit()
    return len(label_maps.COCO_ANIMAL_CLASSES)


def seed_audioset(db) -> int:
    """The audio model's biological labels. All coarse -- AudioSet names sound
    types, not species."""
    for label, (taxon, group) in label_maps.AUDIOSET_BIOLOGICAL.items():
        upsert(
            db,
            scientific_name=taxon,
            model_label=label,
            label_source="ast-audioset",
            rank=TaxonRankEnum.COARSE,
            group=group_from_string(group),
            common_name=label,
        )
    db.commit()
    return len(label_maps.AUDIOSET_BIOLOGICAL)


def seed_imagenet(db, resolve: bool = True) -> int:
    """The classifier's animal labels, resolved against GBIF where possible."""
    try:
        from torchvision.models import ResNet50_Weights
        categories = ResNet50_Weights.IMAGENET1K_V2.meta["categories"]
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] torchvision unavailable, skipping ImageNet labels: {exc}")
        return 0

    count = 0
    unmatched = 0
    for index, label in enumerate(categories):
        group_name = label_maps.imagenet_group_for_index(index)
        if group_name is None:
            continue

        # "African elephant, Loxodonta africana" -> query the informative part.
        parts = [p.strip() for p in label.split(",")]
        query = parts[-1] if len(parts) > 1 and " " in parts[-1] else parts[0]

        resolved = gbif_lookup(query) if resolve else None
        if resolved and resolved.get("scientific_name"):
            gbif_rank = resolved.get("gbif_rank") or ""
            rank = TaxonRankEnum.SPECIES if gbif_rank == "SPECIES" else (
                TaxonRankEnum.GENUS if gbif_rank == "GENUS" else TaxonRankEnum.COARSE
            )
            group = group_from_taxon_class(resolved.get("taxon_class")) \
                if resolved.get("taxon_class") else group_from_string(group_name)
            upsert(
                db,
                scientific_name=resolved["scientific_name"],
                model_label=parts[0],
                label_source="resnet50-imagenet",
                rank=rank,
                group=group,
                common_name=parts[0],
                taxon_class=resolved.get("taxon_class"),
                taxon_order=resolved.get("taxon_order"),
                taxon_family=resolved.get("taxon_family"),
                gbif_taxon_key=resolved.get("gbif_taxon_key"),
                gbif_match_type=resolved.get("gbif_match_type"),
            )
        else:
            # Unmatched labels are kept so the detection still resolves to a
            # group, but with no taxonomy asserted.
            unmatched += 1
            upsert(
                db,
                scientific_name=f"[unmatched] {parts[0]}",
                model_label=parts[0],
                label_source="resnet50-imagenet",
                rank=TaxonRankEnum.COARSE,
                group=group_from_string(group_name),
                common_name=parts[0],
                gbif_match_type="NONE",
            )
        count += 1
        if count % 50 == 0:
            db.commit()
            print(f"    ... {count} ImageNet labels processed")
    db.commit()
    print(f"    {unmatched}/{count} ImageNet labels had no GBIF backbone match")
    return count


def main() -> int:
    resolve = "--no-gbif" not in sys.argv
    db = SessionLocal()
    try:
        print("Seeding species catalog\n")

        print("  corpus ground truth (iNaturalist / GBIF / Xeno-canto)")
        n_truth = seed_from_manifest(db)
        print(f"    {n_truth} identifications")

        print("  COCO detector classes")
        print(f"    {seed_coco(db)} labels")

        print("  AudioSet biological classes")
        print(f"    {seed_audioset(db)} labels")

        print("  ImageNet-1k animal classes"
              + ("" if resolve else " (GBIF resolution skipped)"))
        n_imagenet = seed_imagenet(db, resolve=resolve)
        print(f"    {n_imagenet} labels")

        total = db.query(Species).count()
        endangered = db.query(Species).filter(Species.is_endangered.is_(True)).count()
        with_status = db.query(Species).filter(Species.iucn_status.isnot(None)).count()
        print(
            f"\nCatalog: {total} entries, {with_status} with a published IUCN "
            f"status, {endangered} of them threatened (CR/EN/VU)."
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Error seeding species catalog: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
