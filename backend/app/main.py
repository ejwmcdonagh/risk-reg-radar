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

# CORS is permissive in development. In production, restrict origins to the
# frontend domain via the ALLOWED_ORIGINS environment variable (add to config.py).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {"status": "ok"}
