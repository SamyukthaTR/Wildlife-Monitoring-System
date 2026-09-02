"""Wildlife monitoring reports.

Milestone 2 delivered report content as JSON plus a flat CSV export.
Milestone 4 adds PDF and Excel export (app/modules/reports/export.py) and two
new report types -- habitat and conservation -- on top of the same
already-computed numbers the habitat/conservation/ecosystem modules expose.

Every report states which models produced its numbers and what was excluded from
them, so a reader can tell a genuine absence of wildlife from an absence of
analysis.
"""

import csv
import datetime
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.trend import linear_trend
from app.core.deps import get_current_user, get_db
from app.modules.analysis.models import AnalysisRun, ImageDetection, RunStatusEnum
from app.modules.biodiversity import indices, queries
from app.modules.ecosystem.service import health_for_site
from app.modules.habitat import queries as habitat_queries
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.reports.export import render_pdf, render_xlsx
from app.modules.species.models import Species, TaxonRankEnum
from app.modules.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])

FORMAT_PATTERN = "^(json|csv|pdf|xlsx)$"

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _file_response(content: bytes, fmt: str, filename_stem: str) -> Response:
    ext = "pdf" if fmt == "pdf" else "xlsx"
    return Response(
        content=content,
        media_type=_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.{ext}"'},
    )


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
    format: str = Query("json", pattern=FORMAT_PATTERN),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wildlife monitoring report for a survey, a site, or the whole platform.

    `format=csv` returns the species table as a flat file; `format=pdf` and
    `format=xlsx` render the full report (summary, species, endangered
    species, caveats).
    """
    report = _build_report(db, site_id, survey_id)
    scope_name = report["scope"].get("location_name") or "all-sites"
    filename_stem = f"wildlife-report-{scope_name[:40].replace(' ', '-')}"

    if format == "json":
        return report

    if format == "pdf":
        sections = [
            ("Summary", {
                "Generated at": report["generated_at"],
                "Scope": scope_name,
                **{f"Observations: {k}": v for k, v in report["observations"].items()},
                **{f"Analysis: {k}": v for k, v in report["analysis"].items()},
            }),
            ("Biodiversity", report["biodiversity"]),
            ("Species detected", report["species_detected"]),
            ("Endangered species", report["endangered_species"] or ["None detected in this scope."]),
            ("Acoustic activity", {k: v for k, v in report["acoustic_activity"].items() if k != "by_label"}),
            ("Caveats", report["caveats"]),
        ]
        return _file_response(render_pdf("Wildlife Monitoring Report", sections), "pdf", filename_stem)

    if format == "xlsx":
        sections = [
            ("Summary", {
                "Generated at": report["generated_at"],
                "Scope": scope_name,
                **{f"Observations: {k}": v for k, v in report["observations"].items()},
                **{f"Analysis: {k}": v for k, v in report["analysis"].items()},
            }),
            ("Biodiversity", report["biodiversity"]),
            ("Species Detected", report["species_detected"]),
            ("Endangered Species", report["endangered_species"]),
            ("Caveats", report["caveats"]),
        ]
        return _file_response(render_xlsx("Wildlife Monitoring Report", sections), "xlsx", filename_stem)

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

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.csv"'},
    )


@router.get("/species-population")
def species_population_report(
    format: str = Query("json", pattern=FORMAT_PATTERN),
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

    report = {
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
            "true population estimation would need capture-recapture or "
            "distance-sampling models, which this platform does not attempt."
        ),
    }

    if format == "json":
        return report

    sections = [
        ("Summary", {"Generated at": report["generated_at"], "Caveat": report["caveat"]}),
        ("Species population by site", report["rows"]),
    ]
    if format == "pdf":
        return _file_response(render_pdf("Species Population Report", sections), "pdf", "species-population-report")
    if format == "xlsx":
        return _file_response(render_xlsx("Species Population Report", sections), "xlsx", "species-population-report")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["scientific_name", "common_name", "species_group", "iucn_status",
                      "is_endangered", "site_id", "location_name", "detections"])
    for row in report["rows"]:
        writer.writerow([row[k] for k in ("scientific_name", "common_name", "species_group",
                                           "iucn_status", "is_endangered", "site_id",
                                           "location_name", "detections")])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="species-population-report.csv"'},
    )


def _build_habitat_report(db: Session, site_id: Optional[int]) -> dict:
    if site_id is not None:
        site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
        history = habitat_queries.assessment_history(db, site_id)
        if not history:
            return {
                "scope": {"type": "site", "location_name": site.location_name},
                "assessments": [],
                "environment": habitat_queries.environmental_summary(db, site_id),
                "note": "No habitat assessment yet for this site.",
            }
        trend = linear_trend([(a.assessed_at.timestamp(), a.vegetation_index) for a in history])
        return {
            "scope": {"type": "site", "location_name": site.location_name},
            "assessments": [
                {
                    "assessed_at": a.assessed_at.isoformat(),
                    "vegetation_index": a.vegetation_index,
                    "green_pixel_fraction": a.green_pixel_fraction,
                    "canopy_texture_index": a.canopy_texture_index,
                    "inferred_habitat_signal": a.inferred_habitat_signal,
                }
                for a in history
            ],
            "vegetation_trend": trend,
            "degradation_flag": trend["direction"] == "decreasing",
            "environment": habitat_queries.environmental_summary(db, site_id),
            "note": (
                "Vegetation metrics are pixel-derived from real camera-trap images "
                "(Excess Green Index); environmental readings are modelled ERA5 "
                "reanalysis, not a field sensor. Degradation requires a "
                "statistically significant declining trend across assessments."
            ),
        }

    results = []
    for site in habitat_queries.sites_with_assessments(db):
        history = habitat_queries.assessment_history(db, site.id)
        latest = history[-1]
        trend = linear_trend([(a.assessed_at.timestamp(), a.vegetation_index) for a in history])
        results.append({
            "location_name": site.location_name,
            "assessments": len(history),
            "latest_vegetation_index": latest.vegetation_index,
            "inferred_habitat_signal": latest.inferred_habitat_signal,
            "degradation_flag": trend["direction"] == "decreasing",
        })
    return {
        "scope": {"type": "all", "location_name": "All assessed sites"},
        "sites": results,
        "note": (
            "One row per assessed site. Degradation is flagged only when the "
            "vegetation index shows a statistically significant decline."
        ),
    }


@router.get("/habitat")
def habitat_report(
    site_id: Optional[int] = Query(None),
    format: str = Query("json", pattern=FORMAT_PATTERN),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Habitat assessment report for one site, or every assessed site."""
    report = _build_habitat_report(db, site_id)
    scope_name = report["scope"]["location_name"]
    filename_stem = f"habitat-report-{scope_name[:40].replace(' ', '-')}"

    if format == "json":
        return report

    sections: list[tuple[str, object]] = [("Scope", report["scope"])]
    if "assessments" in report and report["assessments"] and isinstance(report["assessments"], list) and "assessed_at" in report["assessments"][0]:
        sections.append(("Assessment history", report["assessments"]))
        if "vegetation_trend" in report:
            sections.append(("Vegetation trend", report["vegetation_trend"]))
            sections.append(("Environment", report["environment"]))
    elif "sites" in report:
        sections.append(("Sites", report["sites"]))
    sections.append(("Note", report["note"]))

    if format == "pdf":
        return _file_response(render_pdf("Habitat Assessment Report", sections), "pdf", filename_stem)
    if format == "xlsx":
        return _file_response(render_xlsx("Habitat Assessment Report", sections), "xlsx", filename_stem)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    rows = report.get("assessments") or report.get("sites") or []
    if rows:
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h) for h in headers])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.csv"'},
    )


def _build_conservation_report(db: Session, site_id: Optional[int]) -> dict:
    if site_id is not None:
        sites = [db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()]
        if not sites[0]:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
        scope_name = sites[0].location_name
    else:
        sites = db.query(MonitoringSite).order_by(MonitoringSite.id).all()
        scope_name = "All sites"

    site_reports = []
    for site in sites:
        health = health_for_site(db, site.id)
        site_reports.append({
            "location_name": site.location_name,
            "overall_health": health["overall_ecosystem_health_score"],
            "health_band": health.get("band"),
            "biodiversity_score": health["biodiversity_score"],
            "habitat_quality_score": health["habitat_quality_score"],
            "population_stability_score": health["population_stability_score"],
        })

    return {
        "scope": {"type": "site" if site_id else "all", "location_name": scope_name},
        "sites": site_reports,
        "note": (
            "Ecosystem health scores only -- see GET /conservation/recommendations "
            "for the full rule-based recommendation rationale per site."
        ),
    }


@router.get("/conservation")
def conservation_report(
    site_id: Optional[int] = Query(None),
    format: str = Query("json", pattern=FORMAT_PATTERN),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ecosystem health / conservation report for one site or the whole platform."""
    report = _build_conservation_report(db, site_id)
    scope_name = report["scope"]["location_name"]
    filename_stem = f"conservation-report-{scope_name[:40].replace(' ', '-')}"

    if format == "json":
        return report

    sections = [("Scope", report["scope"]), ("Ecosystem health by site", report["sites"]), ("Note", report["note"])]
    if format == "pdf":
        return _file_response(render_pdf("Conservation Report", sections), "pdf", filename_stem)
    if format == "xlsx":
        return _file_response(render_xlsx("Conservation Report", sections), "xlsx", filename_stem)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if report["sites"]:
        headers = list(report["sites"][0].keys())
        writer.writerow(headers)
        for row in report["sites"]:
            writer.writerow([row.get(h) for h in headers])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.csv"'},
    )
