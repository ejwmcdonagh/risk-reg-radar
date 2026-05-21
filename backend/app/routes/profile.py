from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.db.client import get_db
from app.ingestion.custom_rss import run_custom_ingestion

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    technologies: list[str]


class CustomSourceCreate(BaseModel):
    name: str
    url: HttpUrl


# ── Org profile ───────────────────────────────────────────────────────────────

@router.get("")
async def get_profile():
    db = get_db()
    result = db.table("org_profile").select("*").eq("id", 1).single().execute()
    return result.data


@router.put("")
async def update_profile(body: ProfileUpdate):
    # Normalise: strip whitespace, deduplicate, sort for stable storage
    technologies = sorted(set(t.strip() for t in body.technologies if t.strip()))
    db = get_db()
    db.table("org_profile").update({
        "technologies": technologies,
        "updated_at": datetime.now(UTC).isoformat(),
    }).eq("id", 1).execute()
    return {"technologies": technologies}


# ── Custom sources ────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources():
    db = get_db()
    result = db.table("custom_sources").select("*").order("created_at").execute()
    return {"sources": result.data}


@router.post("/sources")
async def add_source(body: CustomSourceCreate):
    db = get_db()
    try:
        result = db.table("custom_sources").insert({
            "name": body.name.strip(),
            "url": str(body.url),
        }).execute()
    except Exception as exc:
        # Unique constraint violation — URL already exists
        raise HTTPException(status_code=409, detail="A source with that URL already exists") from exc
    return result.data[0]


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    db = get_db()
    db.table("custom_sources").delete().eq("id", source_id).execute()
    return {"deleted": source_id}


@router.patch("/sources/{source_id}/toggle")
async def toggle_source(source_id: str):
    db = get_db()
    current = db.table("custom_sources").select("enabled").eq("id", source_id).single().execute()
    if not current.data:
        raise HTTPException(status_code=404, detail="Source not found")
    new_state = not current.data["enabled"]
    db.table("custom_sources").update({"enabled": new_state}).eq("id", source_id).execute()
    return {"id": source_id, "enabled": new_state}


@router.post("/sources/run")
async def trigger_custom_ingestion():
    """Manually trigger ingestion of all enabled custom sources."""
    try:
        inserted = await run_custom_ingestion()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"signals_inserted": inserted}
