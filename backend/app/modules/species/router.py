from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.modules.analysis.models import AudioClassification, ImageDetection
from app.modules.species.models import Species, SpeciesGroupEnum, TaxonRankEnum
from app.modules.species.schemas import (
    SpeciesCatalogStats,
    SpeciesDetectionSummary,
    SpeciesResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/species", tags=["species"])


@router.get("", response_model=List[SpeciesResponse])
def list_species(
    group: Optional[str] = Query(None, description="mammal|bird|reptile|amphibian|insect|marine|other"),
    rank: Optional[str] = Query(None, description="species|genus|family|coarse"),
    endangered: Optional[bool] = Query(None, description="Only IUCN CR/EN/VU species"),
    detected_only: bool = Query(False, description="Only species actually detected so far"),
    search: Optional[str] = Query(None, description="Match scientific or common name"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The species catalog.

    Entries at `coarse` rank came from a model vocabulary that names a sound or
    an animal group rather than a species; they are not species identifications.
    """
    query = db.query(Species)

    if group:
        try:
            query = query.filter(Species.species_group == SpeciesGroupEnum(group.lower()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown species group '{group}'")
    if rank:
        try:
            query = query.filter(Species.rank == TaxonRankEnum(rank.lower()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown rank '{rank}'")
    if endangered is not None:
        query = query.filter(Species.is_endangered.is_(endangered))
    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            func.lower(Species.scientific_name).like(pattern)
            | func.lower(func.coalesce(Species.common_name, "")).like(pattern)
        )
    if detected_only:
        detected_ids = {
            row[0] for row in db.query(ImageDetection.species_id)
            .filter(ImageDetection.species_id.isnot(None)).distinct()
        } | {
            row[0] for row in db.query(AudioClassification.species_id)
            .filter(AudioClassification.species_id.isnot(None)).distinct()
        }
        if not detected_ids:
            return []
        query = query.filter(Species.id.in_(detected_ids))

    return query.order_by(Species.scientific_name).limit(limit).all()


@router.get("/stats", response_model=SpeciesCatalogStats)
def catalog_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shape of the catalog, including how much of it carries a real IUCN status."""
    by_rank = {
        rank.value: db.query(Species).filter(Species.rank == rank).count()
        for rank in TaxonRankEnum
    }
    by_group = {
        group.value: db.query(Species).filter(Species.species_group == group).count()
        for group in SpeciesGroupEnum
    }
    return SpeciesCatalogStats(
        total=db.query(Species).count(),
        by_rank=by_rank,
        by_group=by_group,
        with_iucn_status=db.query(Species).filter(Species.iucn_status.isnot(None)).count(),
        endangered=db.query(Species).filter(Species.is_endangered.is_(True)).count(),
        note=(
            "IUCN status is present only where a source database published one; "
            "it is never inferred. Coarse-rank entries are model vocabulary "
            "labels, not species."
        ),
    )


@router.get("/detections/summary", response_model=List[SpeciesDetectionSummary])
def detection_summary(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Species ordered by how often they have been detected."""
    image_counts = dict(
        db.query(ImageDetection.species_id, func.count(ImageDetection.id))
        .filter(ImageDetection.species_id.isnot(None))
        .group_by(ImageDetection.species_id)
        .all()
    )
    audio_counts = dict(
        db.query(AudioClassification.species_id, func.count(AudioClassification.id))
        .filter(
            AudioClassification.species_id.isnot(None),
            AudioClassification.is_noise.is_(False),
        )
        .group_by(AudioClassification.species_id)
        .all()
    )

    species_ids = set(image_counts) | set(audio_counts)
    if not species_ids:
        return []

    rows = db.query(Species).filter(Species.id.in_(species_ids)).all()
    summaries = [
        SpeciesDetectionSummary(
            species=SpeciesResponse.model_validate(species),
            image_detections=image_counts.get(species.id, 0),
            acoustic_detections=audio_counts.get(species.id, 0),
            total_detections=image_counts.get(species.id, 0) + audio_counts.get(species.id, 0),
        )
        for species in rows
    ]
    summaries.sort(key=lambda s: s.total_detections, reverse=True)
    return summaries[:limit]


@router.get("/{species_id}", response_model=SpeciesResponse)
def get_species(
    species_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    species = db.query(Species).filter(Species.id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")
    return species
