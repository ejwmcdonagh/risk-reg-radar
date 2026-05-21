from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.db.client import get_db
from app.ingestion.custom_rss import run_custom_ingestion

router = APIRouter(prefix="/api/profile", tags=["profile"])

# All built-in sources in display order
BUILTIN_SOURCES = [
    {"id": "cisa_kev",            "name": "CISA KEV",                       "description": "US known exploited vulnerabilities catalog"},
    {"id": "cisa_advisory",       "name": "CISA Advisories",                "description": "US cybersecurity advisories (RSS)"},
    {"id": "ncsc",                "name": "NCSC",                           "description": "UK National Cyber Security Centre alerts"},
    {"id": "nvd",                 "name": "NVD",                            "description": "National Vulnerability Database - critical CVEs"},
    {"id": "exploit_db",          "name": "SANS Internet Storm Center",     "description": "Daily threat analysis and active exploitation reports"},
    {"id": "bleeping_computer",   "name": "Bleeping Computer",              "description": "Breaking cybersecurity news"},
    {"id": "ico_enforcement",     "name": "FCA News",                       "description": "UK Financial Conduct Authority enforcement actions and regulatory guidance"},
    {"id": "github_advisory",     "name": "GitHub Security Advisories",     "description": "Open source vulnerability advisories"},
    {"id": "recorded_future",     "name": "Recorded Future",                "description": "Threat intelligence research and analysis"},
    {"id": "google_threat_intel", "name": "Google Threat Intelligence",     "description": "Threat research from Google and Mandiant"},
    {"id": "horizon3",            "name": "Horizon3.ai",                    "description": "Adversarial attack path research and exploit analysis"},
    {"id": "dark_reading",        "name": "Dark Reading",                   "description": "Cybersecurity news and threat research"},
    {"id": "crowdstrike",         "name": "CrowdStrike",                    "description": "Adversary intelligence and threat research from CrowdStrike"},
    {"id": "microsoft_security",  "name": "Microsoft Security",             "description": "Phishing campaigns, BEC, and credential threats tracked by Microsoft"},
    {"id": "cofense",             "name": "Cofense",                        "description": "Phishing intelligence and email threat analysis"},
    {"id": "krebs",               "name": "Krebs on Security",              "description": "In-depth reporting on fraud, social engineering, and cybercrime"},
]


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


@router.get("/sources/builtin")
async def list_builtin_sources():
    """Return all built-in sources with their current enabled state."""
    db = get_db()
    result = db.table("org_profile").select("disabled_sources").eq("id", 1).single().execute()
    disabled = result.data.get("disabled_sources", []) if result.data else []
    sources = [
        {**s, "enabled": s["id"] not in disabled}
        for s in BUILTIN_SOURCES
    ]
    return {"sources": sources}


@router.patch("/sources/builtin/{source_id}/toggle")
async def toggle_builtin_source(source_id: str):
    """Enable or disable a built-in source."""
    if not any(s["id"] == source_id for s in BUILTIN_SOURCES):
        raise HTTPException(status_code=404, detail="Unknown source")
    db = get_db()
    result = db.table("org_profile").select("disabled_sources").eq("id", 1).single().execute()
    disabled: list[str] = result.data.get("disabled_sources", []) if result.data else []
    if source_id in disabled:
        disabled = [s for s in disabled if s != source_id]
        enabled = True
    else:
        disabled = [*disabled, source_id]
        enabled = False
    db.table("org_profile").update({
        "disabled_sources": disabled,
        "updated_at": datetime.now(UTC).isoformat(),
    }).eq("id", 1).execute()
    return {"id": source_id, "enabled": enabled}


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
        # Unique constraint violation - URL already exists
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
