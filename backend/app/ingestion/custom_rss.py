"""
Generic RSS/Atom ingester for custom sources added via the profile API.

Unlike the built-in ingesters, this one is not instantiated at startup.
It reads enabled custom sources from the DB each time it runs, so newly
added sources are picked up without a server restart.

Source attribution: since all custom signals share SignalSource.CUSTOM,
the actual source name is stored as "source:<name>" in the tags array
so the frontend can still display the correct label.
"""

import logging
from datetime import UTC
from email.utils import parsedate_to_datetime

import feedparser

from app.db.client import get_db
from app.domain_mapper import map_domains
from app.http import async_client
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.severity_mapper import infer_severity

logger = logging.getLogger(__name__)


async def run_custom_ingestion() -> int:
    """
    Fetch and ingest all enabled custom RSS sources.
    Returns total signals inserted across all sources.
    """
    db = get_db()
    result = db.table("custom_sources").select("*").eq("enabled", True).execute()
    sources = result.data or []

    if not sources:
        logger.info("Custom ingestion: no enabled custom sources configured")
        return 0

    total = 0
    for source in sources:
        try:
            inserted = await _ingest_one(db, source)
            total += inserted
            logger.info("Custom source ingested: name=%s inserted=%d", source["name"], inserted)
        except Exception:
            logger.exception("Custom ingestion failed: name=%s url=%s", source["name"], source["url"])

    return total


async def _ingest_one(db, source: dict) -> int:
    name: str = source["name"]
    url: str = source["url"]

    async with async_client(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    signals = [_parse(entry, name) for entry in feed.entries]
    signals = [s for s in signals if s is not None]

    if not signals:
        return 0

    rows = [
        {
            **s.model_dump(mode="json"),
            "risk_domains": [d.value for d in s.risk_domains],
        }
        for s in signals
    ]

    result = (
        db.table("signals")
        .upsert(rows, on_conflict="source,source_id", ignore_duplicates=True)
        .execute()
    )
    return len(result.data) if result.data else 0


def _parse(entry: dict, source_name: str) -> Signal | None:
    title: str = entry.get("title", "").strip()
    if not title:
        return None

    summary: str = entry.get("summary", "")
    link: str = entry.get("link", "")
    source_id = link.rstrip("/").split("/")[-1] if link else entry.get("id", title[:100])

    published_at = None
    if pub := entry.get("published"):
        try:
            published_at = parsedate_to_datetime(pub).astimezone(UTC)
        except Exception:
            pass

    tags: list[str] = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
    # Store source name in tags so the frontend can display "SANS ISC" instead of "custom"
    tags.append(f"source:{source_name}")

    return Signal(
        source=SignalSource.CUSTOM,
        source_id=source_id,
        signal_type=SignalType.ADVISORY,
        title=title,
        summary=summary,
        published_at=published_at,
        severity=infer_severity(title, summary),
        risk_domains=map_domains(title, summary, tags),
        tags=tags,
        url=link or None,
        raw_data={"title": title, "summary": summary, "link": link, "published": entry.get("published", "")},
    )
