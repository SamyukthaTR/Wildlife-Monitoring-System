"""Fetch real historical weather for monitoring sites from Open-Meteo's archive.

Open-Meteo's historical-weather archive (https://archive-api.open-meteo.com) is
free, needs no API key, and publishes ERA5 reanalysis -- a real, published
dataset, but a modelled, grid-interpolated one (~9-25km resolution), not a
field sensor reading. That distinction is stored in
`environmental_readings.source` and repeated in the API layer
(app/modules/habitat/router.py), so nothing here is presented as more precise
than it is.

Sites with placeholder ("null island", 0,0) coordinates are skipped rather
than given a plausible-looking but meaningless reading -- the same discipline
scripts/fetch_samples.py already applies to sources with no published
location.

Run:  python -m scripts.fetch_environment
Idempotent -- upserts on (site_id, recorded_date); safe to re-run.
"""

import datetime
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy import func

from app.core.database import SessionLocal
from app.modules.habitat.models import EnvironmentalReading
from app.modules.monitoring.models import MonitoringSite, Survey

USER_AGENT = (
    "WildlifePopulationIntelligenceSystem/0.3 "
    "(educational conservation-analytics project; environmental data seeding)"
)

# Certificates are verified, matching scripts/fetch_samples.py's convention.
SSL_CONTEXT = ssl.create_default_context()

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HTTP_RETRIES = 3

# The archive does not publish the most recent few days yet.
ARCHIVE_LAG_DAYS = 5

DAILY_VARIABLES = (
    "temperature_2m_mean,relative_humidity_2m_mean,"
    "precipitation_sum,wind_speed_10m_max"
)


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(HTTP_RETRIES):
        try:
            with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{last_error}")


def _is_placeholder(latitude: float, longitude: float) -> bool:
    """"Null island" -- (0, 0) is used only as a NOT NULL placeholder for sites
    with no published coordinates (see scripts/seed_dataset.py); it is not a
    real location and must never be presented as one."""
    return abs(latitude) < 1e-6 and abs(longitude) < 1e-6


def get_site_coordinates(db) -> list[tuple]:
    return db.query(
        MonitoringSite, func.ST_X(MonitoringSite.geom), func.ST_Y(MonitoringSite.geom)
    ).all()


def survey_date_range(db, site_id: int):
    return db.query(
        func.min(Survey.survey_date), func.max(Survey.survey_date)
    ).filter(Survey.site_id == site_id).first()


def upsert_readings(db, site_id: int, daily: dict) -> int:
    dates = daily.get("time", [])
    temperature = daily.get("temperature_2m_mean", [])
    humidity = daily.get("relative_humidity_2m_mean", [])
    precipitation = daily.get("precipitation_sum", [])
    wind = daily.get("wind_speed_10m_max", [])

    inserted = 0
    for index, date_str in enumerate(dates):
        recorded_date = datetime.date.fromisoformat(date_str)
        existing = db.query(EnvironmentalReading).filter(
            EnvironmentalReading.site_id == site_id,
            EnvironmentalReading.recorded_date == recorded_date,
        ).first()
        if existing:
            continue
        db.add(EnvironmentalReading(
            site_id=site_id,
            recorded_date=recorded_date,
            temperature_c=temperature[index] if index < len(temperature) else None,
            humidity_pct=humidity[index] if index < len(humidity) else None,
            precipitation_mm=precipitation[index] if index < len(precipitation) else None,
            wind_speed_kmh=wind[index] if index < len(wind) else None,
            source="open-meteo-era5-archive",
        ))
        inserted += 1
    db.commit()
    return inserted


def fetch_environment() -> int:
    db = SessionLocal()
    today = datetime.date.today()
    latest_available = today - datetime.timedelta(days=ARCHIVE_LAG_DAYS)
    fetched = skipped = failed = 0

    try:
        for site, longitude, latitude in get_site_coordinates(db):
            if latitude is None or longitude is None or _is_placeholder(latitude, longitude):
                print(f"[SKIP] {site.location_name}: no real coordinates")
                skipped += 1
                continue

            start, end = survey_date_range(db, site.id)
            if start is None:
                print(f"[SKIP] {site.location_name}: no surveys")
                skipped += 1
                continue
            end = min(end, latest_available)
            if start > end:
                print(f"[SKIP] {site.location_name}: survey dates too recent for the archive")
                skipped += 1
                continue

            params = urllib.parse.urlencode({
                "latitude": round(latitude, 4),
                "longitude": round(longitude, 4),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": DAILY_VARIABLES,
                "timezone": "UTC",
            })
            url = f"{ARCHIVE_URL}?{params}"

            try:
                payload = _fetch_json(url)
            except RuntimeError as exc:
                print(f"[FAIL] {site.location_name}: {exc}")
                failed += 1
                continue

            inserted = upsert_readings(db, site.id, payload.get("daily") or {})
            print(
                f"[OK]   {site.location_name}: {inserted} new daily reading(s) "
                f"({start.isoformat()} to {end.isoformat()})"
            )
            fetched += 1
            time.sleep(0.5)  # be polite to the free API

        print(f"\nDone: {fetched} site(s) fetched, {skipped} skipped, {failed} failed.")
        if fetched:
            print("Run GET /habitat/environment?site_id=<id> to see the results.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Error fetching environmental data: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(fetch_environment())
