"""
Threat research blog ingesters.

All five sources share the same RSS parsing logic - the only differences
are the feed URL and SignalSource enum value, so a single configurable class
handles all of them rather than five near-identical files.

Sources:
  Recorded Future  - https://www.recordedfuture.com/feed
  Google Threat Intelligence (formerly Mandiant) - https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/
  Horizon3.ai      - https://www.horizon3.ai/feed/
  Dark Reading     - https://www.darkreading.com/rss.xml
  CrowdStrike      - https://www.crowdstrike.com/en-us/blog/feed/

These differ from news sources (Bleeping Computer) in that they contain
deeper technical analysis and often break new TTP disclosures. Combined with
official advisory signals, a blog post from one of these is strong corroboration
that a threat has advanced beyond initial disclosure.
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


class ResearchFeedIngester(BaseIngester):
    """Generic RSS ingester for threat research blogs."""

    def __init__(self, source: SignalSource, feed_url: str) -> None:
        self.source = source
        self.feed_url = feed_url

    async def fetch(self) -> list[Signal]:
        async with async_client(timeout=30) as client:
            resp = await client.get(self.feed_url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        return [s for entry in feed.entries if (s := self._parse(entry)) is not None]

    def _parse(self, entry: dict) -> Signal | None:
        title: str = entry.get("title", "").strip()
        if not title:
            return None

        summary: str = entry.get("summary", "")
        link: str = entry.get("link", "")
        # Use URL slug as source_id - stable across re-ingestion
        source_id = link.rstrip("/").split("/")[-1] if link else title[:100]

        published_at = None
        if pub := entry.get("published"):
            try:
                published_at = parsedate_to_datetime(pub).astimezone(UTC)
            except Exception:
                pass

        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return Signal(
            source=self.source,
            source_id=source_id,
            signal_type=SignalType.THREAT_INTEL,
            title=title,
            summary=summary,
            published_at=published_at,
            severity=infer_severity(title, summary),
            risk_domains=map_domains(title, summary, tags),
            tags=tags,
            url=link or None,
            raw_data={
                "title": title,
                "summary": summary,
                "link": link,
                "published": entry.get("published", ""),
            },
        )


# Pre-built instances used by the ingestion registry and scheduler
RecordedFutureIngester = ResearchFeedIngester(
    source=SignalSource.RECORDED_FUTURE,
    feed_url="https://www.recordedfuture.com/feed",
)

GoogleThreatIntelIngester = ResearchFeedIngester(
    source=SignalSource.GOOGLE_THREAT_INTEL,
    feed_url="https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",
)

Horizon3Ingester = ResearchFeedIngester(
    source=SignalSource.HORIZON3,
    feed_url="https://horizon3.ai/feed/",
)

DarkReadingIngester = ResearchFeedIngester(
    source=SignalSource.DARK_READING,
    feed_url="https://www.darkreading.com/rss.xml",
)

CrowdStrikeIngester = ResearchFeedIngester(
    source=SignalSource.CROWDSTRIKE,
    feed_url="https://www.crowdstrike.com/en-us/blog/feed",
)

MicrosoftSecurityIngester = ResearchFeedIngester(
    source=SignalSource.MICROSOFT_SECURITY,
    feed_url="https://www.microsoft.com/en-us/security/blog/feed/",
)

CofenseIngester = ResearchFeedIngester(
    source=SignalSource.COFENSE,
    feed_url="https://cofense.com/feed/",
)

KrebsIngester = ResearchFeedIngester(
    source=SignalSource.KREBS,
    feed_url="https://krebsonsecurity.com/feed/",
)
