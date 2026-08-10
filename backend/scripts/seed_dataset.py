"""Seed monitoring infrastructure and observations from the sample corpus.

Reads scripts/sample_data/manifest.json, which scripts/fetch_samples.py builds
from the source APIs. Two things Milestone 1 got wrong are fixed here:

  * observation timestamps were stamped with datetime.now(); they now use the
    real observation date the source published
  * every site was placed at POINT(0 0); sites are now positioned from the real
    coordinates of the observations they contain

Where the source publishes no coordinate (Snapshot Serengeti does not release
per-camera positions; iNaturalist blurs threatened taxa) the observation is
assigned to an explicitly-named unlocated site rather than given a plausible
guess.

Run: python -m scripts.seed_dataset
Idempotent -- re-running skips observations already ingested.
"""

import datetime
import json
import os
import shutil
import sys
from collections import defaultdict

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.modules.monitoring.models import (
    Device,
    DeviceTypeEnum,
    MonitoringSite,
    Survey,
    SurveyStatusEnum,
)
from app.modules.observations.models import FileTypeEnum, ObservationLog
from app.modules.users.models import RoleEnum, User

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "sample_data", "manifest.json")

# Coarse continental bounding boxes, used only to group scattered records into
# named regions. Approximate by construction -- the label says so.
REGIONS = [
    ("Africa", -35.0, 38.0, -18.0, 52.0),
    ("Europe", 36.0, 72.0, -25.0, 45.0),
    ("Asia", 5.0, 78.0, 45.0, 180.0),
    ("Oceania", -50.0, 5.0, 110.0, 180.0),
    ("North America", 7.0, 84.0, -170.0, -50.0),
    ("South America", -56.0, 13.0, -82.0, -34.0),
]


def region_for(latitude: float, longitude: float) -> str:
    for name, lat_min, lat_max, lng_min, lng_max in REGIONS:
        if lat_min <= latitude <= lat_max and lng_min <= longitude <= lng_max:
            return name
    return "Other region"


def parse_timestamp(value: str | None) -> datetime.datetime | None:
    """Parse the varied date formats the source APIs return."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    for parser in (
        datetime.datetime.fromisoformat,
        lambda v: datetime.datetime.strptime(v, "%Y-%m-%d"),
        lambda v: datetime.datetime.strptime(v, "%Y-%m-%dT%H:%M:%S"),
    ):
        try:
            parsed = parser(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed
        except (ValueError, TypeError):
            continue
    return None


def get_or_create_seed_user(db) -> User:
    email = "seed_system@wildlife.org"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            name="System Seed Process",
            email=email,
            hashed_password=get_password_hash("secureseed123!"),
            role=RoleEnum.RESEARCHER,
            organization="Dataset Ingestion",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_or_create_site(db, user_id: int, name: str, latitude, longitude, note: str):
    site = db.query(MonitoringSite).filter(MonitoringSite.location_name == name).first()
    if site:
        return site
    # Unlocated groups still need a geometry for the NOT NULL PostGIS column;
    # POINT(0 0) is used only where the source publishes no coordinate, and the
    # site name records that fact.
    lat = latitude if latitude is not None else 0.0
    lng = longitude if longitude is not None else 0.0
    site = MonitoringSite(
        location_name=name,
        geom=f"SRID=4326;POINT({lng} {lat})",
        # Left null rather than guessed: the sources do not publish habitat type.
        habitat_type=None,
        protected_area=None,
        monitoring_device_type=note,
        created_by=user_id,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def get_or_create_survey(db, site_id: int, survey_date: datetime.date, notes: str) -> Survey:
    survey = db.query(Survey).filter(Survey.site_id == site_id).first()
    if survey:
        return survey
    survey = Survey(
        site_id=site_id,
        survey_date=survey_date,
        status=SurveyStatusEnum.COMPLETED,
        notes=notes,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


def get_or_create_device(db, site_id: int, serial: str, device_type: DeviceTypeEnum) -> Device:
    device = db.query(Device).filter(Device.serial == serial).first()
    if device:
        return device
    device = Device(site_id=site_id, device_type=device_type, serial=serial, status="active")
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def group_records(records: list[dict]) -> dict:
    """Bucket manifest records into the sites they will be seeded under.

    Located records group by source and region; unlocated ones group by source
    alone, under a name that says they are unlocated.
    """
    groups = defaultdict(list)
    for record in records:
        source = record.get("source", "Unknown source")
        latitude, longitude = record.get("latitude"), record.get("longitude")
        if latitude is not None and longitude is not None:
            key = (source, region_for(latitude, longitude), True)
        else:
            key = (source, None, False)
        groups[key].append(record)
    return groups


def site_name_for(source: str, region: str | None, located: bool, count: int) -> str:
    if located:
        return f"{source} records - {region} (centroid of {count} observations)"
    return f"{source} records - location not published by source"


def seed_database() -> int:
    if not os.path.exists(MANIFEST_PATH):
        print(f"No manifest at {MANIFEST_PATH}.")
        print("Run `python -m scripts.fetch_samples` first.")
        return 1

    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        records = json.load(fh).get("records", [])
    if not records:
        print("Manifest contains no records.")
        return 1

    sample_dir = os.path.join(SCRIPT_DIR, "sample_data")
    uploads_dir = settings.UPLOAD_DIR
    os.makedirs(uploads_dir, exist_ok=True)

    db = SessionLocal()
    inserted = skipped = missing = 0
    try:
        seed_user = get_or_create_seed_user(db)

        for (source, region, located), group in sorted(
            group_records(records).items(), key=lambda kv: str(kv[0])
        ):
            latitudes = [r["latitude"] for r in group if r.get("latitude") is not None]
            longitudes = [r["longitude"] for r in group if r.get("longitude") is not None]
            centroid_lat = sum(latitudes) / len(latitudes) if latitudes else None
            centroid_lng = sum(longitudes) / len(longitudes) if longitudes else None

            name = site_name_for(source, region, located, len(group))
            note = (
                "Site position is the mean of its observations' published "
                "coordinates; regions are coarse bounding boxes."
                if located else
                "Source does not publish coordinates for these records."
            )
            print(f"\n{name}")
            site = get_or_create_site(db, seed_user.id, name, centroid_lat, centroid_lng, note)

            dates = [parse_timestamp(r.get("observed_on")) for r in group]
            dates = [d.date() for d in dates if d]
            survey_date = min(dates) if dates else datetime.date.today()
            survey = get_or_create_survey(
                db, site.id, survey_date,
                f"Seeded from {source}. {note}",
            )

            has_audio = any(r.get("media_kind") == "audio" for r in group)
            device_type = DeviceTypeEnum.AUDIO_SENSOR if has_audio else DeviceTypeEnum.CAMERA_TRAP
            serial = f"SEED-{abs(hash(name)) % 100000:05d}"
            get_or_create_device(db, site.id, serial, device_type)

            for record in group:
                source_id = f"{record['source'].split()[0].lower()}_{record['source_id']}"
                source_path = os.path.join(sample_dir, record["file"])
                if not os.path.exists(source_path):
                    print(f"  [MISS] {record['file']} not on disk")
                    missing += 1
                    continue

                existing = db.query(ObservationLog).filter(
                    ObservationLog.storage_path.like(f"%{source_id}%")
                ).first()
                if existing:
                    skipped += 1
                    continue

                extension = os.path.splitext(record["file"])[1]
                destination = os.path.join(uploads_dir, f"{source_id}{extension}")
                shutil.copy(source_path, destination)

                observed = parse_timestamp(record.get("observed_on"))
                observation = ObservationLog(
                    survey_id=survey.id,
                    uploaded_by=seed_user.id,
                    file_type=(
                        FileTypeEnum.AUDIO if record.get("media_kind") == "audio"
                        else FileTypeEnum.IMAGE
                    ),
                    storage_path=destination,
                    # The real observation date where the source published one.
                    uploaded_at=observed or datetime.datetime.now(datetime.timezone.utc),
                    processing_status="pending",
                )
                db.add(observation)
                inserted += 1
                truth = (record.get("ground_truth") or {}).get("scientific_name") or "unlabelled"
                print(f"  [ADD] {source_id}  {truth}")
            db.commit()

        print(
            f"\nSeed complete: {inserted} added, {skipped} already present, "
            f"{missing} missing from disk."
        )
        if inserted:
            print("Run `python -m scripts.seed_species` then analyse via "
                  "POST /analysis/run-pending.")
        return 0

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Error during seeding: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(seed_database())
