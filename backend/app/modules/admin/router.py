"""Platform-wide operational overview for the Administrator dashboard.

Every figure here is a plain count or group-by over tables the other
modules already own -- no new tables, and nothing computed that isn't
already trustworthy elsewhere in the platform.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, RoleChecker
from app.modules.analysis.models import AnalysisRun, RunStatusEnum, ImageDetection
from app.modules.monitoring.models import MonitoringSite, Survey, Device
from app.modules.observations.models import ObservationLog
from app.modules.species.models import Species, TaxonRankEnum
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = RoleChecker(['Administrator'])


@router.get("/overview")
def platform_overview(db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    users_by_role = dict(
        db.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    observations_by_status = dict(
        db.query(ObservationLog.processing_status, func.count(ObservationLog.id))
        .group_by(ObservationLog.processing_status).all()
    )
    devices_by_status = dict(
        db.query(Device.status, func.count(Device.id)).group_by(Device.status).all()
    )
    species_detected = (
        db.query(func.count(func.distinct(ImageDetection.species_id)))
        .join(Species, ImageDetection.species_id == Species.id)
        .filter(Species.rank == TaxonRankEnum.SPECIES, ImageDetection.is_unknown.is_(False))
        .scalar()
    )
    endangered_detected = (
        db.query(func.count(func.distinct(ImageDetection.species_id)))
        .join(Species, ImageDetection.species_id == Species.id)
        .filter(Species.is_endangered.is_(True), ImageDetection.is_unknown.is_(False))
        .scalar()
    )

    return {
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": {role.value: count for role, count in users_by_role.items()},
        },
        "monitoring": {
            "sites": db.query(func.count(MonitoringSite.id)).scalar(),
            "surveys": db.query(func.count(Survey.id)).scalar(),
            "devices": db.query(func.count(Device.id)).scalar(),
            "devices_by_status": devices_by_status,
        },
        "observations": {
            "total": sum(observations_by_status.values()),
            "by_status": observations_by_status,
        },
        "analysis": {
            "runs_completed": db.query(func.count(AnalysisRun.id))
                .filter(AnalysisRun.status == RunStatusEnum.COMPLETED).scalar(),
            "runs_failed": db.query(func.count(AnalysisRun.id))
                .filter(AnalysisRun.status == RunStatusEnum.FAILED).scalar(),
            "runs_running": db.query(func.count(AnalysisRun.id))
                .filter(AnalysisRun.status == RunStatusEnum.RUNNING).scalar(),
            "ml_enabled": settings.ENABLE_ML,
        },
        "species": {
            "distinct_species_detected": species_detected or 0,
            "endangered_species_detected": endangered_detected or 0,
        },
    }
