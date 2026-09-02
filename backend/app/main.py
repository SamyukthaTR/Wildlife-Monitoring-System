from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import log_requests, setup_logging
from app.core.rate_limit import limiter
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.health.router import router as health_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.observations.router import router as observations_router
from app.modules.analysis.router import router as analysis_router
from app.modules.species.router import router as species_router
from app.modules.biodiversity.router import router as biodiversity_router
from app.modules.reports.router import router as reports_router
from app.modules.population.router import router as population_router
from app.modules.habitat.router import router as habitat_router
from app.modules.conservation.router import router as conservation_router
from app.modules.ecosystem.router import router as ecosystem_router
from app.modules.admin.router import router as admin_router

setup_logging(settings.LOG_LEVEL)

app = FastAPI(
    title="Wildlife Population Intelligence System",
    description="Backend API for monitoring species, populations, and habitat health.",
    version="0.2.0"
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests, please try again later."})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.middleware("http")(log_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
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
# Milestone 3: population, habitat, conservation, ecosystem intelligence
app.include_router(population_router)
app.include_router(habitat_router)
app.include_router(conservation_router)
app.include_router(ecosystem_router)
app.include_router(admin_router)
