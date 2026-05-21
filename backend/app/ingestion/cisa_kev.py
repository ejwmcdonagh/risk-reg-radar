"""
CISA Known Exploited Vulnerabilities (KEV) catalog ingester.

Source: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
Feed:   https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The KEV catalog is CISA's authoritative list of CVEs with confirmed real-world
exploitation. It's a high signal-to-noise source — every entry represents a
vulnerability that attackers are actively using, not just theoretically dangerous.

This is intentionally one of the first sources in V1 because the CVE IDs here
can later be cross-referenced against NVD for CVSS scores, giving us a combined
"actively exploited + high severity" signal which is a strong card trigger.
"""

from datetime import date, datetime, timezone

from app.domain_mapper import map_domains
from app.http import async_client
from app.ingestion.base import BaseIngester
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.severity_mapper import infer_severity

FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # KEV dateAdded is YYYY-MM-DD with no time component
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)
    except ValueError:
        return None


class CisaKevIngester(BaseIngester):
    source = SignalSource.CISA_KEV

    async def fetch(self) -> list[Signal]:
        async with async_client(timeout=30) as client:
            resp = await client.get(FEED_URL)
            resp.raise_for_status()
            data = resp.json()

        return [self._parse(entry) for entry in data.get("vulnerabilities", [])]

    def _parse(self, entry: dict) -> Signal:
        cve_id: str = entry["cveID"]
        title = f"{cve_id}: {entry.get('vulnerabilityName', '')}"
        summary = entry.get("shortDescription", "")

        # Ransomware flag is explicit in KEV data — use it to seed domain mapping
        # rather than relying solely on keyword matching
        tags: list[str] = []
        if entry.get("knownRansomwareCampaignUse", "").lower() == "known":
            tags.append("ransomware")

        return Signal(
            source=SignalSource.CISA_KEV,
            source_id=cve_id,
            signal_type=SignalType.VULNERABILITY,
            title=title,
            summary=summary,
            published_at=_parse_date(entry.get("dateAdded")),
            severity=infer_severity(title, summary),
            risk_domains=map_domains(title, summary, tags),
            tags=tags,
            url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            raw_data=entry,
        )
