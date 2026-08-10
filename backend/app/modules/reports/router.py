"""Wildlife monitoring reports.

Milestone 2 delivers the report content as JSON plus a flat CSV export; PDF and
Excel export are Milestone 4 deliverables and are not attempted here.

Every report states which models produced its numbers and what was excluded from
them, so a reader can tell a genuine absence of wildlife from an absence of
analysis.
"""

import csv
import datetime
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.modules.analysis.models import AnalysisRun, ImageDetection, RunStatusEnum
from app.modules.biodiversity import indices, queries
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.species.models import Species, TaxonRankEnum
from app.modules.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])


def _build_report(db: Session, site_id: Optional[int], survey_id: Optional[int]) -> dict:
    if survey_id is not None:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        site = db.query(MonitoringSite).filter(MonitoringSite.id == survey.site_id).first()
        scope = {
            "type": "survey",
            "survey_id": survey.id,
            "survey_date": survey.survey_date.isoformat(),
            "status": survey.status.value,
            "notes": survey.notes,
            "site_id": site.id if site else None,
            "location_name": site.location_name if site else None,
        }
    elif site_id is not None:
        site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
        scope = {
            "type": "site",
            "site_id": site.id,
            "location_name": site.location_name,
            "habitat_type": site.habitat_type,
            "protected_area": site.protected_area,
        }
    else:
        scope = {"type": "all", "location_name": "All monitoring sites"}

    abundances, excluded = queries.species_abundances(db, site_id, survey_id)
    diversity = indices.compute(abundances)
    composition = indices.composition(abundances)

    # Species detected in scope, with conservation status.
    detected_rows = (
        db.query(Species, func.count(ImageDetection.id))
        .join(ImageDetection, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(ImageDetection.is_unknown.is_(False))
    )
    if survey_id is not None:
        detected_rows = detected_rows.filter(Survey.id == survey_id)
    if site_id is not None:
        detected_rows = detected_rows.filter(Survey.site_id == site_id)
    detected_rows = detected_rows.group_by(Species.id).all()

    species_records = [
        {
            "scientific_name": species.scientific_name,
            "common_name": species.common_name,
            "rank": species.rank.value,
            "species_group": species.species_group.value,
            "taxon_class": species.taxon_class,
            "taxon_family": species.taxon_family,
            "iucn_status": species.iucn_status,
            "iucn_source": species.iucn_source,
            "is_endangered": species.is_endangered,
            "detections": count,
        }
        for species, count in sorted(detected_rows, key=lambda r: r[1], reverse=True)
    ]
    endangered = [s for s in species_records if s["is_endangered"]]

    runs = db.query(AnalysisRun).join(
        ObservationLog, AnalysisRun.observation_id == ObservationLog.id
    ).join(Survey, ObservationLog.survey_id == Survey.id)
    if survey_id is not None:
        runs = runs.filter(Survey.id == survey_id)
    if site_id is not None:
        runs = runs.filter(Survey.site_id == site_id)

    completed = runs.filter(AnalysisRun.status == RunStatusEnum.COMPLETED).count()
    failed = runs.filter(AnalysisRun.status == RunStatusEnum.FAILED).count()
    models = sorted({
        row[0] for row in runs.with_entities(AnalysisRun.models_used).distinct().all()
        if row[0]
    })

    return {
        "report_type": "wildlife_monitoring",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": scope,
        "observations": queries.observation_counts(db, site_id, survey_id),
        "analysis": {
            "runs_completed": completed,
            "runs_failed": failed,
            "models_used": models,
        },
        "biodiversity": diversity,
        "species_composition": composition,
        "species_detected": species_records,
        "endangered_species": endangered,
        "acoustic_activity": queries.acoustic_activity(db, site_id, survey_id),
        "excluded_from_indices": excluded,
        "caveats": [
            "Species identification uses ResNet-50 trained on ImageNet-1k, which "
            "covers roughly 400 animal classes. Species outside that vocabulary "
            "cannot be named and appear as unidentified detections.",
            "Acoustic labels come from the AudioSet ontology, which has no "
            "species-level classes. They indicate sound type only.",
            "IUCN status is shown only where a source database published one.",
            "Counts are detections, not individual animals: the same animal "
            "photographed twice counts twice. Cross-frame individual "
            "identification is not performed.",
        ],
    }


@router.get("/monitoring")
def monitoring_report(
    site_id: Optional[int] = Query(None),
    survey_id: Optional[int] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wildlife monitoring report for a survey, a site, or the whole platform.

    `format=csv` returns the species table as a flat file. PDF and Excel export
    arrive in Milestone 4.
    """
    report = _build_report(db, site_id, survey_id)

    if format == "json":
        return report

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "scientific_name", "common_name", "rank", "species_group", "taxon_class",
        "taxon_family", "iucn_status", "is_endangered", "detections",
    ])
    for species in report["species_detected"]:
        writer.writerow([
            species["scientific_name"], species["common_name"], species["rank"],
            species["species_group"], species["taxon_class"], species["taxon_family"],
            species["iucn_status"] or "", species["is_endangered"], species["detections"],
        ])
    buffer.seek(0)

    scope_name = report["scope"].get("location_name") or "all-sites"
    filename = f"wildlife-report-{scope_name[:40].replace(' ', '-')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/species-population")
def species_population_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detection counts per species per site.

    Detection counts are an index of relative activity, not an absolute
    population estimate. Turning them into population figures needs
    capture-recapture or distance-sampling models, which are Milestone 3 work.
    """
    rows = (
        db.query(
            Species,
            MonitoringSite.location_name,
            MonitoringSite.id,
            func.count(ImageDetection.id),
        )
        .join(ImageDetection, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .join(MonitoringSite, Survey.site_id == MonitoringSite.id)
        .filter(
            ImageDetection.is_unknown.is_(False),
            Species.rank == TaxonRankEnum.SPECIES,
        )
        .group_by(Species.id, MonitoringSite.id, MonitoringSite.location_name)
        .all()
    )

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "rows": [
            {
                "scientific_name": species.scientific_name,
                "common_name": species.common_name,
                "species_group": species.species_group.value,
                "iucn_status": species.iucn_status,
                "is_endangered": species.is_endangered,
                "site_id": site_id,
                "location_name": location_name,
                "detections": count,
            }
            for species, location_name, site_id, count in sorted(
                rows, key=lambda r: r[3], reverse=True
            )
        ],
        "caveat": (
            "Detections index relative activity. They are not population sizes; "
            "population estimation is a Milestone 3 deliverable."
        ),
    }
