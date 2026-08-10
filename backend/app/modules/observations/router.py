import os
import uuid
import shutil
from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from app.core.config import settings
from app.core.deps import get_db, get_current_user, RoleChecker
from app.modules.analysis.pipeline import run_analysis
from app.modules.users.models import User
from app.modules.monitoring.models import Survey
from app.modules.observations.models import ObservationLog, FileTypeEnum
from app.modules.observations.schemas import ObservationLogResponse

router = APIRouter(prefix="/observations", tags=["observations"])

UPLOAD_DIR = settings.UPLOAD_DIR
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/gif", "audio/mpeg", "audio/wav", "audio/ogg"]

# Ensure uploads directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

write_roles = RoleChecker(['Wildlife Researcher', 'Conservation Officer'])

@router.post("/upload", response_model=ObservationLogResponse, status_code=status.HTTP_201_CREATED)
async def upload_observation(
    background_tasks: BackgroundTasks,
    survey_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles)
):
    # 1. Validate survey
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # 2. Validate MIME type
    if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
        if not (file.content_type and (file.content_type.startswith("image/") or file.content_type.startswith("audio/"))):
            raise HTTPException(status_code=400, detail="Invalid file type. Only images and audio are allowed.")
    
    # 3. Determine file type enum
    file_type = FileTypeEnum.IMAGE if file.content_type.startswith("image") else FileTypeEnum.AUDIO

    # 4. Generate UUID filename to prevent path traversal & collisions
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # 5. Save file & check size limit
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    file.file.seek(0)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not save file")

    # 6. Create ObservationLog
    new_obs = ObservationLog(
        survey_id=survey_id,
        uploaded_by=current_user.id,
        file_type=file_type,
        storage_path=file_path,
        processing_status="pending"
    )
    db.add(new_obs)
    db.commit()
    db.refresh(new_obs)

    # Analyse after the response is sent. CPU inference takes a few seconds, so
    # the uploader gets an immediate 201 and polls /analysis/observations/{id}.
    background_tasks.add_task(run_analysis, new_obs.id)

    return new_obs


@router.get("", response_model=List[ObservationLogResponse])
def get_observations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(ObservationLog)
    
    # Visibility logic: Wildlife Researchers only see their own uploads
    if current_user.role == "Wildlife Researcher":
        query = query.filter(ObservationLog.uploaded_by == current_user.id)
        
    return query.all()


@router.get("/{obs_id}/file")
def get_observation_file(obs_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    obs = db.query(ObservationLog).filter(ObservationLog.id == obs_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
        
    # Visibility check
    if current_user.role == "Wildlife Researcher" and obs.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this file")
        
    if not os.path.exists(obs.storage_path):
        raise HTTPException(status_code=404, detail="File not found on server")
        
    return FileResponse(obs.storage_path, media_type="application/octet-stream")
