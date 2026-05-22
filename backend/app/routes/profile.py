import ipaddress
import socket
from datetime import UTC, datetime
from urllib.parse import urlparse

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
    blocked_technologies: list[str] = []


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
    # Use the SQL function instead of read-modify-write to avoid a race condition
    # where two concurrent toggles on the same source lose one update.
    result = db.rpc("toggle_disabled_source", {"p_source_id": source_id}).execute()
    enabled: bool = result.data
    return {"id": source_id, "enabled": enabled}


@router.put("")
async def update_profile(body: ProfileUpdate):
    # Normalise: strip whitespace, deduplicate, sort for stable storage
    technologies = sorted(set(t.strip() for t in body.technologies if t.strip()))
    blocked = sorted(set(t.strip() for t in body.blocked_technologies if t.strip()))
    db = get_db()
    db.table("org_profile").update({
        "technologies": technologies,
        "blocked_technologies": blocked,
        "updated_at": datetime.now(UTC).isoformat(),
    }).eq("id", 1).execute()
    return {"technologies": technologies, "blocked_technologies": blocked}


# ── Custom sources ────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources():
    db = get_db()
    result = db.table("custom_sources").select("*").order("created_at").execute()
    return {"sources": result.data}


def _reject_private_url(url: str) -> None:
    """
    Reject URLs that resolve to private/loopback/link-local IPs.
    Prevents SSRF where a user submits an internal network address as an RSS
    feed and the ingester fetches it (e.g. AWS metadata at 169.254.169.254).
    """
    hostname = urlparse(url).hostname or ""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=422, detail="Could not resolve hostname")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=422, detail="URL resolves to a private address")


@router.post("/sources")
async def add_source(body: CustomSourceCreate):
    _reject_private_url(str(body.url))
    db = get_db()
    try:
        result = db.table("custom_sources").insert({
            "name": body.name.strip(),
            "url": str(body.url),
        }).execute()
    except Exception as exc:
        # Unique constraint on url column - surface a clean message, not the DB error
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
