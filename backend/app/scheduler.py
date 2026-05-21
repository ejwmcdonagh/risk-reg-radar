"""
APScheduler setup for periodic signal ingestion.

We use AsyncIOScheduler so jobs run in the same event loop as FastAPI,
avoiding thread-safety issues with async DB clients. Each ingester gets its
own cron job so a slow or failing source doesn't block others.

Cron expressions are read from config so operators can adjust timing via
environment variables without code changes.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.ingestion.cisa_advisories import CisaAdvisoriesIngester
from app.ingestion.cisa_kev import CisaKevIngester
from app.ingestion.ncsc import NcscIngester
from app.ingestion.nvd import NvdIngester
from app.services.card_generator import generate_cards
from app.services.clustering import run_clustering

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    ingesters = [
        (CisaKevIngester(), settings.cisa_kev_cron),
        (CisaAdvisoriesIngester(), settings.cisa_advisories_cron),
        (NcscIngester(), settings.ncsc_cron),
        (NvdIngester(), settings.nvd_cron),
    ]

    for ingester, cron in ingesters:
        scheduler.add_job(
            ingester.run,
            trigger=CronTrigger.from_crontab(cron),
            id=f"ingest_{ingester.source.value}",
            name=f"Ingest {ingester.source.value}",
            # Coalesce missed runs — if the server was down for several cycles,
            # run once on startup rather than firing once per missed window
            coalesce=True,
            max_instances=1,
        )
        logger.info("Scheduled ingester: source=%s cron=%s", ingester.source.value, cron)

    # Clustering runs after ingestion (default 08:00 UTC, configurable via CLUSTERING_CRON).
    # coalesce=True so a missed run doesn't trigger a burst of back-to-back cluster jobs.
    scheduler.add_job(
        run_clustering,
        trigger=CronTrigger.from_crontab(settings.clustering_cron),
        id="signal_clustering",
        name="Signal combination detection",
        coalesce=True,
        max_instances=1,
    )
    logger.info("Scheduled clustering job: cron=%s", settings.clustering_cron)

    # Card generation runs after clustering — default 09:00 UTC
    scheduler.add_job(
        generate_cards,
        trigger=CronTrigger.from_crontab(settings.card_generation_cron),
        id="card_generation",
        name="Provocation card generation",
        coalesce=True,
        max_instances=1,
    )
    logger.info("Scheduled card generation job: cron=%s", settings.card_generation_cron)

    return scheduler
