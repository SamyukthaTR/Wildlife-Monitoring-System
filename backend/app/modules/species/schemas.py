from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SpeciesResponse(BaseModel):
    id: int
    scientific_name: str
    common_name: Optional[str] = None
    rank: str
    species_group: str
    taxon_class: Optional[str] = None
    taxon_order: Optional[str] = None
    taxon_family: Optional[str] = None
    gbif_taxon_key: Optional[int] = None
    gbif_match_type: Optional[str] = None
    inat_taxon_id: Optional[int] = None
    iucn_status: Optional[str] = None
    iucn_source: Optional[str] = None
    is_endangered: bool
    label_source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SpeciesDetectionSummary(BaseModel):
    """How often a species has actually been detected across the platform."""
    species: SpeciesResponse
    image_detections: int
    acoustic_detections: int
    total_detections: int


class SpeciesCatalogStats(BaseModel):
    total: int
    by_rank: dict
    by_group: dict
    with_iucn_status: int
    endangered: int
    note: str
