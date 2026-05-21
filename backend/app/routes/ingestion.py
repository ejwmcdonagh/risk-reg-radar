"""
Manual ingestion trigger endpoints.

These are primarily for development and operational use - not part of the
user-facing product. They let you kick off a source run on demand rather
than waiting for the scheduler, which is useful when testing a new ingester
or recovering from a failed scheduled run.
"""

from fastapi import APIRouter, HTTPException

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
    CofenseIngester,
    CrowdStrikeIngester,
    DarkReadingIngester,
    GoogleThreatIntelIngester,
    Horizon3Ingester,
    KrebsIngester,
    MicrosoftSecurityIngester,
    RecordedFutureIngester,
)
from app.models.enums import SignalSource

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

# Registry maps source enum values to ingester instances.
# Adding a new source requires only adding it here - the route handler is generic.
_INGESTERS = {
    SignalSource.CISA_KEV:            CisaKevIngester(),
    SignalSource.CISA_ADVISORY:       CisaAdvisoriesIngester(),
    SignalSource.NCSC:                NcscIngester(),
    SignalSource.NVD:                 NvdIngester(),
    SignalSource.EXPLOIT_DB:          ExploitDbIngester(),
    SignalSource.BLEEPING_COMPUTER:   BleepingComputerIngester(),
    SignalSource.ICO_ENFORCEMENT:     IcoEnforcementIngester(),
    SignalSource.GITHUB_ADVISORY:     GithubAdvisoryIngester(),
    SignalSource.RECORDED_FUTURE:     RecordedFutureIngester,
    SignalSource.GOOGLE_THREAT_INTEL: GoogleThreatIntelIngester,
    SignalSource.HORIZON3:            Horizon3Ingester,
    SignalSource.DARK_READING:        DarkReadingIngester,
    SignalSource.CROWDSTRIKE:         CrowdStrikeIngester,
    SignalSource.MICROSOFT_SECURITY:  MicrosoftSecurityIngester,
    SignalSource.COFENSE:             CofenseIngester,
    SignalSource.KREBS:               KrebsIngester,
}


@router.post("/run")
async def trigger_ingestion(source: SignalSource):
    """
    Trigger an immediate ingestion run for a specific source.
    Returns the count of newly inserted signals.
    """
    ingester = _INGESTERS.get(source)
    if not ingester:
        raise HTTPException(status_code=404, detail=f"No ingester registered for source: {source}")

    try:
        inserted = await ingester.run()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"source": source, "inserted": inserted}


@router.get("/status")
async def ingestion_status(limit: int = 20):
    """Returns the most recent ingestion run records, newest first."""
    db = get_db()
    result = (
        db.table("ingestion_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"runs": result.data}
