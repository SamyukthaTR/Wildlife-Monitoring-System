from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.deps import get_db, get_current_user, RoleChecker
from app.modules.users.models import User
from app.modules.monitoring.models import MonitoringSite, Survey, Device
from app.modules.monitoring.schemas import (
    MonitoringSiteCreate, MonitoringSiteResponse,
    SurveyCreate, SurveyResponse,
    DeviceCreate, DeviceResponse
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

write_roles = RoleChecker(['Wildlife Researcher', 'Conservation Officer'])

# --- Monitoring Sites ---
@router.post("/sites", response_model=MonitoringSiteResponse, status_code=status.HTTP_201_CREATED)
def create_site(
    site_in: MonitoringSiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles)
):
    wkt_geom = f"SRID=4326;POINT({site_in.longitude} {site_in.latitude})"
    
    new_site = MonitoringSite(
        location_name=site_in.location_name,
        geom=wkt_geom,
        habitat_type=site_in.habitat_type,
        protected_area=site_in.protected_area,
        monitoring_device_type=site_in.monitoring_device_type,
        created_by=current_user.id
    )
    db.add(new_site)
    db.commit()
    db.refresh(new_site)
    
    return MonitoringSiteResponse(
        id=new_site.id,
        location_name=new_site.location_name,
        habitat_type=new_site.habitat_type,
        protected_area=new_site.protected_area,
        monitoring_device_type=new_site.monitoring_device_type,
        created_by=new_site.created_by,
        created_at=new_site.created_at,
        latitude=site_in.latitude,
        longitude=site_in.longitude
    )

@router.get("/sites", response_model=List[MonitoringSiteResponse])
def get_sites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sites = db.query(
        MonitoringSite.id,
        MonitoringSite.location_name,
        MonitoringSite.habitat_type,
        MonitoringSite.protected_area,
        MonitoringSite.monitoring_device_type,
        MonitoringSite.created_by,
        MonitoringSite.created_at,
        func.ST_X(MonitoringSite.geom).label('longitude'),
        func.ST_Y(MonitoringSite.geom).label('latitude')
    ).all()
    
    return [MonitoringSiteResponse(**dict(s._mapping)) for s in sites]

# --- Surveys ---
@router.post("/surveys", response_model=SurveyResponse, status_code=status.HTTP_201_CREATED)
def create_survey(
    survey_in: SurveyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles)
):
    site = db.query(MonitoringSite).filter(MonitoringSite.id == survey_in.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
        
    new_survey = Survey(
        site_id=survey_in.site_id,
        survey_date=survey_in.survey_date,
        notes=survey_in.notes
    )
    db.add(new_survey)
    db.commit()
    db.refresh(new_survey)
    return new_survey

@router.get("/surveys", response_model=List[SurveyResponse])
def get_surveys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Survey).all()

# --- Devices ---
@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device_in: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles)
):
    existing = db.query(Device).filter(Device.serial == device_in.serial).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device with this serial already exists")
        
    site = db.query(MonitoringSite).filter(MonitoringSite.id == device_in.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
        
    new_device = Device(
        site_id=device_in.site_id,
        device_type=device_in.device_type,
        serial=device_in.serial,
        status=device_in.status
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

@router.get("/devices", response_model=List[DeviceResponse])
def get_devices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Device).all()
