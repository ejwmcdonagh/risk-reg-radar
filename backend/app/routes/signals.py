from typing import Annotated

from fastapi import APIRouter, Query

from app.db.client import get_db
from app.models.enums import RiskDomain, SignalSource

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
async def list_signals(
    source: Annotated[SignalSource | None, Query()] = None,
    risk_domain: Annotated[RiskDomain | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    List signals with optional filtering.

    risk_domain uses a Postgres array containment check (@>) - it matches any
    signal whose risk_domains array contains the requested domain, not an
    exact equality match. A signal tagged [identity_credential, vulnerability_patch]
    will be returned when filtering by either domain.
    """
    db = get_db()
    query = db.table("signals").select("*").order("published_at", desc=True).range(offset, offset + limit - 1)

    if source:
        query = query.eq("source", source.value)
    if risk_domain:
        # PostgREST array containment filter
        query = query.contains("risk_domains", [risk_domain.value])

    result = query.execute()
    return {"signals": result.data, "offset": offset, "limit": limit}


@router.get("/stats")
async def signal_stats():
    """
    Counts grouped by source and risk domain.

    Uses a SQL function rather than loading all rows into Python - the
    risk_domains TEXT[] column requires unnest() to group by individual
    domain values, which isn't expressible via the PostgREST filter API.
    """
    db = get_db()
    result = db.rpc("get_signal_stats", {}).execute()
    return result.data


@router.get("/{signal_id}")
async def get_signal(signal_id: str):
    db = get_db()
    result = db.table("signals").select("*").eq("id", signal_id).single().execute()
    return result.data
