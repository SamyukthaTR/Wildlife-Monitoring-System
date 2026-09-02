import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.core.database import Base

class RoleEnum(str, enum.Enum):
    RESEARCHER = "Wildlife Researcher"
    CONSERVATION_OFFICER = "Conservation Officer"
    FOREST_OFFICER = "Forest Department Officer"
    ADMIN = "Administrator"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    # Nullable: Google-authenticated accounts never set a password.
    hashed_password = Column(String, nullable=True)
    role = Column(Enum(RoleEnum), nullable=False)
    organization = Column(String, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
