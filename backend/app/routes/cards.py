import logging
from typing import Annotated

import anthropic
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
from pydantic import BaseModel

from app.config import settings
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
        # Log full exception server-side; don't expose internal detail to the caller
        logger.exception("Card generation run failed")
        raise HTTPException(status_code=500, detail="Card generation failed") from exc
    return {"cards_written": written}


@router.get("")
async def list_cards(
    risk_domain: Annotated[RiskDomain | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0)] = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    List provocation cards ordered by score descending.

    Filters:
    - risk_domain: narrow to a specific domain
    - status: 'active' | 'archived' (default: active)
    - min_score: only return cards above this score threshold
    - before: ISO date string - only cards generated before this date
    """
    db = get_db()
    query = (
        db.table("provocation_cards")
        .select("*")
        .order("generated_at", desc=True)
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
    if before:
        query = query.lte("generated_at", before)

    result = query.execute()
    return {"cards": result.data, "offset": offset, "limit": limit}


@router.post("/{card_id}/dismiss")
async def dismiss_card(card_id: str):
    """
    Archive a card and mark its cluster as dismissed so the same signals
    are not re-clustered on the next pipeline run.
    """
    db = get_db()
    result = db.table("provocation_cards").select("id, cluster_id").eq("id", card_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Card not found")

    cluster_id = result.data["cluster_id"]

    db.table("provocation_cards").update({"status": "archived"}).eq("id", card_id).execute()
    # Mark the cluster dismissed so its signals are excluded from future clustering runs.
    # The _already_clustered_ids_for_domain function includes dismissed clusters, meaning
    # the same signals won't form a new cluster unless fresh signals come in after this point.
    db.table("signal_clusters").update({"status": "dismissed"}).eq("id", cluster_id).execute()

    return {"dismissed": True}


@router.get("/{card_id}")
async def get_card(card_id: str):
    """Fetch a single provocation card by ID, including all 5 layers."""
    db = get_db()
    result = db.table("provocation_cards").select("*").eq("id", card_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Card not found")
    return result.data


class TeamSummaryRequest(BaseModel):
    team: str


@router.post("/{card_id}/team-summary")
async def get_team_summary(card_id: str, body: TeamSummaryRequest):
    """
    Generate a short summary of how this card's risk specifically affects the given team.
    Called on demand when a user clicks a team badge in the card modal.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")

    db = get_db()
    result = db.table("provocation_cards").select("*").eq("id", card_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = result.data
    evidence_titles = ", ".join(e["source"] for e in (card.get("evidence_stack") or [])[:4])

    prompt = (
        f"Risk card: {card['signal_headline']}\n"
        f"Risk domain: {card['risk_domain']}\n"
        f"Summary: {card['metadata'].get('cluster_summary', '')}\n"
        f"Sources: {evidence_titles}\n\n"
        f"In 2-3 plain sentences, explain specifically how this risk affects the {body.team} team "
        f"and what they should do or check. Write directly for that team, not for a general audience. "
        f"Be concrete - name the likely systems, processes, or responsibilities involved. No jargon acronyms."
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    summary = response.content[0].text.strip() if response.content else ""
    return {"team": body.team, "summary": summary}
