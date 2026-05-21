"""
CISA Cybersecurity Advisories ingester.

Source: https://www.cisa.gov/cybersecurity-advisories
Feed:   https://www.cisa.gov/cybersecurity-advisories/all.xml  (RSS 2.0)

CISA advisories are richer than KEV entries — they describe attack campaigns,
TTPs, and mitigations, not just individual CVEs. They're the primary source for
multi-signal cards involving threat actor behaviour (e.g. an AiTM phishing
advisory combined with an insurance questionnaire update).

We use feedparser here rather than raw XML parsing because CISA's feed
occasionally includes non-standard RSS elements and feedparser handles
those edge cases gracefully.
"""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser

from app.domain_mapper import map_domains
from app.http import async_client
from app.ingestion.base import BaseIngester
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.severity_mapper import infer_severity

FEED_URL = "https://www.cisa.gov/cybersecurity-advisories/all.xml"


class CisaAdvisoriesIngester(BaseIngester):
    source = SignalSource.CISA_ADVISORY

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

        # feedparser normalises pubDate to a 9-tuple; fallback to now if absent
        published_at: datetime | None = None
        if pub := entry.get("published"):
            try:
                published_at = parsedate_to_datetime(pub).astimezone(UTC)
            except Exception:
                pass

        # CISA advisory IDs follow the pattern AA25-XXX — extract from the URL
        # slug so we get a stable source_id even if the title changes
        source_id = link.rstrip("/").split("/")[-1] if link else title[:100]

        # Tags from the RSS categories, if present
        tags: list[str] = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return Signal(
            source=SignalSource.CISA_ADVISORY,
            source_id=source_id,
            signal_type=SignalType.ADVISORY,
            title=title,
            summary=summary,
            published_at=published_at,
            severity=infer_severity(title, summary),
            risk_domains=map_domains(title, summary, tags),
            tags=tags,
            url=link,
            raw_data={
                "id": entry.get("id", ""),
                "title": title,
                "summary": summary,
                "link": link,
                "published": entry.get("published", ""),
                "tags": tags,
            },
        )
