"""Ecosystem health analytics -- composes biodiversity, population and habitat
outputs into four component scores. See scoring.py for the formulas and their
null-propagation rules, and service.py for how the inputs are assembled.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.modules.ecosystem.service import health_for_site
from app.modules.monitoring.models import MonitoringSite
from app.modules.users.models import User

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


@router.get("/health")
def ecosystem_health(
    site_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ecosystem health for one site, or the whole platform when site_id is omitted."""
    if site_id is not None:
        site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
    return health_for_site(db, site_id)


@router.get("/health/sites")
def ecosystem_health_sites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ecosystem health for every site, ranked best to worst. Unscored sites sort last."""
    sites = db.query(MonitoringSite).order_by(MonitoringSite.id).all()
    results = [
        {"location_name": site.location_name, **health_for_site(db, site.id)}
        for site in sites
    ]
    results.sort(
        key=lambda r: (
            r["overall_ecosystem_health_score"] is None,
            -(r["overall_ecosystem_health_score"] or 0),
        )
    )
    return {"sites": results}
