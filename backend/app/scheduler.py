"""
APScheduler setup for periodic signal ingestion.

We use AsyncIOScheduler so jobs run in the same event loop as FastAPI,
avoiding thread-safety issues with async DB clients. Each ingester gets its
own cron job so a slow or failing source doesn't block others.

Cron expressions are read from config so operators can adjust timing via
environment variables without code changes.

Each ingester is wrapped in _guarded_run which checks org_profile.disabled_sources
before executing. This lets users toggle any source from the settings page
without a server restart.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.client import get_db
from app.ingestion.bleeping_computer import BleepingComputerIngester
from app.ingestion.cisa_advisories import CisaAdvisoriesIngester
from app.ingestion.cisa_kev import CisaKevIngester
from app.ingestion.exploit_db import ExploitDbIngester
from app.ingestion.github_advisory import GithubAdvisoryIngester
from app.ingestion.ico_enforcement import IcoEnforcementIngester
from app.ingestion.ncsc import NcscIngester
from app.ingestion.nvd import NvdIngester
from app.ingestion.research_feeds import (
    CrowdStrikeIngester,
    DarkReadingIngester,
    GoogleThreatIntelIngester,
    Horizon3Ingester,
    RecordedFutureIngester,
)
from app.services.card_generator import generate_cards
from app.services.clustering import run_clustering
from app.ingestion.custom_rss import run_custom_ingestion

logger = logging.getLogger(__name__)


def _is_source_enabled(source_id: str) -> bool:
    """Check org_profile.disabled_sources to see if a source should run."""
    try:
        db = get_db()
        result = db.table("org_profile").select("disabled_sources").eq("id", 1).single().execute()
        disabled = result.data.get("disabled_sources", []) if result.data else []
        return source_id not in disabled
    except Exception:
        # If the check fails, default to enabled so ingestion still runs
        return True


async def _guarded_run(ingester, source_id: str) -> None:
    if not _is_source_enabled(source_id):
        logger.info("Skipping disabled source: %s", source_id)
        return
    await ingester.run()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    ingesters = [
        (CisaKevIngester(),          "cisa_kev",            settings.cisa_kev_cron),
        (CisaAdvisoriesIngester(),   "cisa_advisory",       settings.cisa_advisories_cron),
        (NcscIngester(),             "ncsc",                settings.ncsc_cron),
        (NvdIngester(),              "nvd",                 settings.nvd_cron),
        (ExploitDbIngester(),        "exploit_db",          settings.cisa_advisories_cron),
        (BleepingComputerIngester(), "bleeping_computer",   settings.cisa_advisories_cron),
        (IcoEnforcementIngester(),   "ico_enforcement",     settings.cisa_kev_cron),
        (GithubAdvisoryIngester(),   "github_advisory",     settings.nvd_cron),
        # Research feeds run daily - high quality but lower cadence than news sources
        (RecordedFutureIngester,     "recorded_future",     settings.cisa_kev_cron),
        (GoogleThreatIntelIngester,  "google_threat_intel", settings.cisa_kev_cron),
        (Horizon3Ingester,           "horizon3",            settings.cisa_kev_cron),
        (DarkReadingIngester,        "dark_reading",        settings.cisa_advisories_cron),
        (CrowdStrikeIngester,        "crowdstrike",         settings.cisa_kev_cron),
    ]

    for ingester, source_id, cron in ingesters:
        scheduler.add_job(
            _guarded_run,
            args=[ingester, source_id],
            trigger=CronTrigger.from_crontab(cron),
            id=f"ingest_{source_id}",
            name=f"Ingest {source_id}",
            coalesce=True,
            max_instances=1,
        )
        logger.info("Scheduled ingester: source=%s cron=%s", source_id, cron)

    scheduler.add_job(
        run_custom_ingestion,
        trigger=CronTrigger.from_crontab(settings.cisa_kev_cron),
        id="ingest_custom",
        name="Ingest custom RSS sources",
        coalesce=True,
        max_instances=1,
    )

    scheduler.add_job(
        run_clustering,
        trigger=CronTrigger.from_crontab(settings.clustering_cron),
        id="signal_clustering",
        name="Signal combination detection",
        coalesce=True,
        max_instances=1,
    )
    logger.info("Scheduled clustering job: cron=%s", settings.clustering_cron)

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
