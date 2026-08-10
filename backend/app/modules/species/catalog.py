"""Resolving a model's raw label to a row in the species catalog.

The catalog is pre-seeded (see scripts/seed_species.py), so this is a lookup,
not a network call -- analysis must not depend on an external API being up.

A label that has no catalog entry resolves to None. The detection is still
recorded with its raw label and confidence; it simply carries no taxonomy. That
is preferable to inventing a match.
"""

from sqlalchemy.orm import Session

from app.modules.species.models import Species, SpeciesGroupEnum, THREATENED_STATUSES


def resolve_label(db: Session, label_raw: str, group: str | None = None) -> Species | None:
    """Find the catalog entry for a model label."""
    if not label_raw:
        return None

    normalised = label_raw.strip().lower()
    species = db.query(Species).filter(Species.model_label == normalised).first()
    if species:
        return species

    # ImageNet labels carry synonym lists, e.g. "African elephant, Loxodonta
    # africana". Try the leading name before giving up.
    if "," in normalised:
        head = normalised.split(",")[0].strip()
        species = db.query(Species).filter(Species.model_label == head).first()
        if species:
            return species

    return None


def is_threatened(status: str | None) -> bool:
    """IUCN categories that count as threatened: CR, EN, VU."""
    return bool(status) and status.strip().upper() in THREATENED_STATUSES


def group_from_taxon_class(taxon_class: str | None) -> SpeciesGroupEnum:
    """Map a taxonomic class name onto the platform's species groups."""
    if not taxon_class:
        return SpeciesGroupEnum.OTHER
    lowered = taxon_class.strip().lower()
    mapping = {
        "mammalia": SpeciesGroupEnum.MAMMAL,
        "aves": SpeciesGroupEnum.BIRD,
        "reptilia": SpeciesGroupEnum.REPTILE,
        "amphibia": SpeciesGroupEnum.AMPHIBIAN,
        "insecta": SpeciesGroupEnum.INSECT,
        "arachnida": SpeciesGroupEnum.INSECT,
        "actinopterygii": SpeciesGroupEnum.MARINE,
        "chondrichthyes": SpeciesGroupEnum.MARINE,
        "elasmobranchii": SpeciesGroupEnum.MARINE,
        "malacostraca": SpeciesGroupEnum.MARINE,
        "cephalopoda": SpeciesGroupEnum.MARINE,
        "bivalvia": SpeciesGroupEnum.MARINE,
        "gastropoda": SpeciesGroupEnum.MARINE,
        "anthozoa": SpeciesGroupEnum.MARINE,
        "scyphozoa": SpeciesGroupEnum.MARINE,
    }
    return mapping.get(lowered, SpeciesGroupEnum.OTHER)


def group_from_string(value: str | None) -> SpeciesGroupEnum:
    """Map a species_group string (as used in labels.py and the manifest)."""
    if not value:
        return SpeciesGroupEnum.OTHER
    try:
        return SpeciesGroupEnum(value.strip().lower())
    except ValueError:
        return SpeciesGroupEnum.OTHER
