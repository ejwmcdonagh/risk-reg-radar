from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_db
from app.models.enums import RiskDomain
from app.services.card_generator import generate_cards

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.post("/run")
async def trigger_card_generation(cluster_ids: list[str] | None = None):
    """
    Manually trigger card generation.

    Without a body: generates cards for all pending clusters above the score threshold.
    With cluster_ids in the JSON body: generates cards for only those specific clusters,
    useful for targeted re-generation after prompt tuning.
    """
    try:
        written = await generate_cards(cluster_ids=cluster_ids)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"cards_written": written}


@router.get("")
async def list_cards(
    risk_domain: Annotated[RiskDomain | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    List provocation cards ordered by score descending.

    Filters:
    - risk_domain: narrow to a specific domain
    - status: 'active' | 'archived'
    - min_score: only return cards above this score threshold
    """
    db = get_db()
    query = (
        db.table("provocation_cards")
        .select("*")
        .order("score", desc=True)
        .range(offset, offset + limit - 1)
    )

    if risk_domain:
        query = query.eq("risk_domain", risk_domain.value)
    if status:
        query = query.eq("status", status)
    else:
        query = query.eq("status", "active")
    if min_score is not None:
        query = query.gte("score", min_score)

    result = query.execute()
    return {"cards": result.data, "offset": offset, "limit": limit}


@router.get("/{card_id}")
async def get_card(card_id: str):
    """Fetch a single provocation card by ID, including all 5 layers."""
    db = get_db()
    result = db.table("provocation_cards").select("*").eq("id", card_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Card not found")
    return result.data
