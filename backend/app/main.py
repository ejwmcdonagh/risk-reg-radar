"""
FastAPI application entry point.

The scheduler is started inside the lifespan context manager so it shuts down
cleanly on server exit rather than leaving background threads orphaned. This
matters for graceful restarts in production (e.g. Docker, systemd, Fly.io).
"""

import logging
from contextlib import asynccontextmanager

import truststore
from fastapi import FastAPI

# Inject the OS native trust store (macOS Keychain) into Python's ssl module.
# Required on corporate networks where a proxy CA is trusted by the system
# but not present in certifi's bundled CA list.
truststore.inject_into_ssl()
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.client import get_db
from app.routes import cards, clusters, ingestion, profile, signals
from app.scheduler import create_scheduler

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    else:
        scheduler = None
        logger.info("Scheduler disabled - set SCHEDULER_ENABLED=true to enable daily runs")
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(
    title="Regulatory Radar API",
    description="Signal ingestion and retrieval for the Regulatory Radar intelligence agent.",
    version="0.1.0",
    lifespan=lifespan,
)

# In production, set ALLOWED_ORIGINS="https://your-domain.com" in the env.
# Defaults to ["*"] so local dev works without any config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router)
app.include_router(ingestion.router)
app.include_router(clusters.router)
app.include_router(cards.router)
app.include_router(profile.router)


@app.get("/health")
async def health():
    # Verify DB connectivity, not just process liveness - a dead DB connection
    # would otherwise look healthy to a load balancer or uptime monitor
    try:
        db = get_db()
        db.table("org_profile").select("id").eq("id", 1).execute()
        return {"status": "ok"}
    except Exception:
        logger.exception("Health check DB ping failed")
        from fastapi import Response
        return Response(content='{"status":"degraded"}', status_code=503, media_type="application/json")
