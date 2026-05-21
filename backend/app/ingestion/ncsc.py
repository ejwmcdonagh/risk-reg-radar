"""
NCSC (UK National Cyber Security Centre) alerts and guidance ingester.

Source: https://www.ncsc.gov.uk/section/keep-up-to-date/alerts-advisories
Feed:   https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml

NCSC guidance is particularly valuable for UK-regulated organisations (FCA,
ICO, DORA-scoped entities). It's also often ahead of US advisories for
threats that hit European infrastructure first. Combined with a CISA advisory
on the same TTP, an NCSC alert becomes strong evidence for a multi-signal card.
"""

from datetime import UTC
from email.utils import parsedate_to_datetime

import feedparser

from app.domain_mapper import map_domains
from app.http import async_client
from app.ingestion.base import BaseIngester
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.severity_mapper import infer_severity

FEED_URL = "https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml"


class NcscIngester(BaseIngester):
    source = SignalSource.NCSC

    async def fetch(self) -> list[Signal]:
        async with async_client(timeout=30) as client:
            resp = await client.get(FEED_URL)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        return [self._parse(entry) for entry in feed.entries]

    def _parse(self, entry: dict) -> Signal:
        title: str = entry.get("title", "")
        summary: str = entry.get("summary", "")
        link: str = entry.get("link", "")

        published_at = None
        if pub := entry.get("published"):
            try:
                published_at = parsedate_to_datetime(pub).astimezone(UTC)
            except Exception:
                pass

        # NCSC URLs are stable slugs — use the final path segment as source_id
        source_id = link.rstrip("/").split("/")[-1] if link else entry.get("id", title[:100])

        return Signal(
            source=SignalSource.NCSC,
            source_id=source_id,
            signal_type=SignalType.ADVISORY,
            title=title,
            summary=summary,
            published_at=published_at,
            severity=infer_severity(title, summary),
            risk_domains=map_domains(title, summary),
            tags=[],
            url=link,
            raw_data={
                "id": entry.get("id", ""),
                "title": title,
                "summary": summary,
                "link": link,
                "published": entry.get("published", ""),
            },
        )
