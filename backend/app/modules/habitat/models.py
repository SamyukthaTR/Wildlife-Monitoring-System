from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class HabitatAssessment(Base):
    """One vegetation/canopy assessment snapshot for a site.

    Computed from the real pixels of that site's already-uploaded camera-trap
    images (see app/ml/vegetation.py) via POST /habitat/assess-site -- never
    simulated. Append-only: each assessment run adds a new row rather than
    overwriting the last one, so repeated assessments over time give a real
    trend for degradation detection instead of a single snapshot pretending to
    be one.
    """
    __tablename__ = "habitat_assessments"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), index=True, nullable=False)
    assessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    images_sampled = Column(Integer, nullable=False)
    vegetation_index = Column(Float, nullable=False)
    green_pixel_fraction = Column(Float, nullable=False)
    canopy_texture_index = Column(Float, nullable=False)
    # Snapshotted from monitoring_sites.habitat_type at assessment time, so a
    # later edit to the site record doesn't rewrite what this assessment was
    # actually compared against.
    declared_habitat_type = Column(String, nullable=True)
    inferred_habitat_signal = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)


class EnvironmentalReading(Base):
    """One day of modelled historical weather for a site's coordinates.

    Source is Open-Meteo's archive API, which publishes ERA5 reanalysis -- a
    real, freely published dataset, but a modelled ~9-25km grid product, not a
    field sensor reading. That distinction is carried in `source` and repeated
    in every API response that surfaces this table (see
    app/modules/habitat/router.py), because this platform does not overstate
    what a number means (see docs/milestone2.md's founding rule).

    Populated only by scripts/fetch_environment.py; the API never calls the
    weather service directly, so a page load never depends on outbound network
    reachability.
    """
    __tablename__ = "environmental_readings"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), index=True, nullable=False)
    recorded_date = Column(Date, nullable=False)
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    wind_speed_kmh = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="open-meteo-era5-archive")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("site_id", "recorded_date", name="uq_environmental_reading_site_date"),
    )
