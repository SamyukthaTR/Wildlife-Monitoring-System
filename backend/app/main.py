from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.health.router import router as health_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.observations.router import router as observations_router
from app.modules.analysis.router import router as analysis_router
from app.modules.species.router import router as species_router
from app.modules.biodiversity.router import router as biodiversity_router
from app.modules.reports.router import router as reports_router

app = FastAPI(
    title="Wildlife Population Intelligence System",
    description="Backend API for monitoring species, populations, and habitat health.",
    version="0.2.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(monitoring_router)
app.include_router(observations_router)
# Milestone 2: recognition engines and biodiversity analytics
app.include_router(analysis_router)
app.include_router(species_router)
app.include_router(biodiversity_router)
app.include_router(reports_router)
