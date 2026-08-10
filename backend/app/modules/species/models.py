import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.core.database import Base


class SpeciesGroupEnum(str, enum.Enum):
    """The six species groups named in the project specification, plus a bucket
    for anything the source taxonomy does not place in one of them."""
    MAMMAL = "mammal"
    BIRD = "bird"
    REPTILE = "reptile"
    AMPHIBIAN = "amphibian"
    INSECT = "insect"
    MARINE = "marine"
    OTHER = "other"


class TaxonRankEnum(str, enum.Enum):
    """The rank an entry actually resolves to.

    This exists so the platform never overstates an identification. A YOLO box
    labelled "bird" and an AudioSet label "Bird" both identify the class Aves,
    not a species, and are stored as COARSE. Only entries the source resolved to
    a binomial are stored as SPECIES.
    """
    SPECIES = "species"
    GENUS = "genus"
    FAMILY = "family"
    COARSE = "coarse"


# IUCN Red List categories that count as threatened.
THREATENED_STATUSES = {"CR", "EN", "VU"}


class Species(Base):
    """Canonical species catalog.

    Rows come from two places, both recorded in `label_source`:
      1. the ground truth of the seeded corpus (iNaturalist / GBIF / Xeno-canto)
      2. the label vocabularies of the models themselves, resolved against the
         GBIF backbone taxonomy at seed time

    `iucn_status` is null unless a source published one. It is never inferred.
    """
    __tablename__ = "species"

    id = Column(Integer, primary_key=True, index=True)
    scientific_name = Column(String, unique=True, index=True, nullable=False)
    common_name = Column(String, nullable=True)
    rank = Column(Enum(TaxonRankEnum), nullable=False, default=TaxonRankEnum.COARSE)
    species_group = Column(Enum(SpeciesGroupEnum), nullable=False, default=SpeciesGroupEnum.OTHER)

    taxon_class = Column(String, nullable=True)
    taxon_order = Column(String, nullable=True)
    taxon_family = Column(String, nullable=True)

    gbif_taxon_key = Column(Integer, nullable=True)
    gbif_match_type = Column(String, nullable=True)
    inat_taxon_id = Column(Integer, nullable=True)

    iucn_status = Column(String, nullable=True)
    iucn_source = Column(String, nullable=True)
    is_endangered = Column(Boolean, nullable=False, default=False)

    # Which vocabulary this row entered from, e.g. "inaturalist-groundtruth",
    # "yolov8n-coco", "resnet50-imagenet", "ast-audioset".
    label_source = Column(String, nullable=True)
    # The raw model label string this row is matched by, lower-cased.
    model_label = Column(String, index=True, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
