"""
Signal combination detection - Step 2 of the Regulatory Radar build sequence.

Approach:
- Pull signals from the last N days (configurable via CLUSTERING_WINDOW_DAYS, default 30)
- Skip signals already assigned to a cluster in this window
- Send a condensed signal list to Claude and ask it to identify convergence patterns
- Score each cluster using an additive model (see _score below)
- Persist new clusters to signal_clusters

Why LLM-assisted rather than pure keyword matching?
The keyword domain mapper (Step 1) tags signals into broad domains. Clustering
requires a finer judgement: "are these five advisories all pointing at the same
underlying exploit chain?" That requires reading titles and summaries together,
not just matching isolated keywords. Claude handles that comparison well.

Why tool use for the LLM call?
Tool use forces the model to return structured data with a predictable schema.
Asking for JSON in a free-text response is fragile - minor formatting differences
cause parse errors. With tool use, the SDK validates the schema before we receive it.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic

from app.config import settings
from app.db.client import get_db
from app.domain_mapper import map_domains
from app.models.enums import RiskDomain, Severity

logger = logging.getLogger(__name__)

# Severity ordinal for score comparison and sorting
_SEVERITY_RANK = {
    Severity.CRITICAL.value: 4,
    Severity.HIGH.value: 3,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
}

# Tool schema the model must use when returning cluster data.
# Each element of the "clusters" array represents one detected convergence pattern.
_CLUSTER_TOOL: dict[str, Any] = {
    "name": "record_signal_clusters",
    "description": (
        "Record the groups of signals that converge on the same specific threat vector. "
        "Only group signals that share a concrete underlying cause - same CVE class, "
        "same threat actor, same misconfiguration type. Broad domain overlap alone is "
        "not enough. If no genuine convergence exists, return an empty clusters array."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "0-based indices into the signals array you were given",
                        },
                        "risk_domain": {
                            "type": "string",
                            "enum": [
                                "identity_credential",
                                "vulnerability_patch",
                                "supply_chain",
                                "detection_response",
                                "data_exposure",
                                "ransomware_extortion",
                            ],
                            "description": "Primary risk domain for this cluster",
                        },
                        "risk_vector": {
                            "type": "string",
                            "description": (
                                "The specific threat vector these signals converge on "
                                "(e.g. 'RCE via unpatched Cisco IOS-XE tracked as CVE-2023-20198')"
                            ),
                        },
                        "cluster_summary": {
                            "type": "string",
                            "description": (
                                "One sentence describing what is happening right now - "
                                "present tense, direct, no jargon"
                            ),
                        },
                        "all_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All risk domains represented across this cluster's signals",
                        },
                    },
                    "required": [
                        "signal_indices",
                        "risk_domain",
                        "risk_vector",
                        "cluster_summary",
                        "all_domains",
                    ],
                },
            }
        },
        "required": ["clusters"],
    },
}

_SYSTEM_PROMPT = """You are a threat intelligence analyst. You will be given a list of recent
cybersecurity signals - vulnerability disclosures, threat advisories, and known-exploited
vulnerability entries - and asked to identify convergence patterns.

Your job is to find groups of signals pointing at the same underlying threat.

Strong clustering evidence (any of these justifies a cluster):
- Same CVE ID appearing across multiple sources (e.g. NVD + CISA KEV + CISA advisory = strong match)
- Same vendor or product targeted in multiple advisories within days of each other
- Same threat actor or campaign named across multiple sources
- An advisory and a KEV entry that clearly reference the same vulnerability
- Same exploit technique applied to the same product family

Do NOT group signals that only share a vulnerability class. "Multiple products have RCE"
is not a cluster - it is noise. "Flowise versions before 3.1.0 have RCE" is a cluster.
The test: could a patch manager read this cluster and know exactly which product or
vendor to act on? If the answer requires listing more than 2-3 unrelated vendors, split it.

Signal types for context:
- vulnerability: CVE entry from NVD or GitHub Advisory
- advisory: official advisory from CISA, NCSC, or similar
- threat_intel: blog post or research from a vendor or researcher
A KEV entry (cisa_kev source) means the CVE is confirmed actively exploited in the wild.

Single-signal clusters are allowed when a signal is significant enough to stand alone -
for example: a confirmed ransomware campaign advisory, an NCSC alert with no related signals,
or a critical actively-exploited CVE with no peer signals. Use single-signal clusters
sparingly and only for genuinely high-importance signals.

A signal can only belong to one cluster. Signals that are neither part of a convergence
pattern nor significant enough to stand alone should not be clustered."""


# Max signals that contribute to base and severity scoring. Beyond this,
# additional signals from the same source stop inflating the score - a cluster
# of 25 identical GitHub Advisory CVEs should not outrank a 4-signal
# multi-source cluster just because of volume.
_SIGNAL_SCORE_CAP = 5


def _score(signals: list[dict[str, Any]], all_domains: list[str]) -> tuple[float, dict[str, Any]]:
    """
    Additive scoring model. Returns (total_score, breakdown_dict).

    Components:
    - Base: 2 points per signal, capped at _SIGNAL_SCORE_CAP signals
    - Severity: CRITICAL=10, HIGH=5, MEDIUM=2 per signal, capped at _SIGNAL_SCORE_CAP
    - Recency: +3 per signal published within last 7 days (uncapped - recency is always relevant)
    - Source diversity: +5 per unique source (cross-source = stronger signal)
    - Domain span: +10 if cluster touches 2+ domains (multi-vector = board-relevant)
    - KEV bonus: +20 if any signal is from cisa_kev (confirmed active exploitation)
    """
    now = datetime.now(UTC)
    recency_cutoff = now - timedelta(days=7)

    # Sort scored signals: highest severity first so the cap keeps the best ones
    _sev_order = {Severity.CRITICAL.value: 0, Severity.HIGH.value: 1, Severity.MEDIUM.value: 2}
    scored_signals = sorted(signals, key=lambda s: _sev_order.get(s.get("severity") or "", 3))
    capped = scored_signals[:_SIGNAL_SCORE_CAP]

    base = len(capped) * 2.0
    severity_pts = 0.0
    recency_pts = 0.0
    sources: set[str] = set()

    for sig in capped:
        sev = sig.get("severity")
        if sev == Severity.CRITICAL.value:
            severity_pts += 10
        elif sev == Severity.HIGH.value:
            severity_pts += 5
        elif sev == Severity.MEDIUM.value:
            severity_pts += 2

    # Recency applies to all signals - a cluster staying active over time should
    # keep scoring, not be penalised for having more signals than the cap
    kev_present = False
    for sig in signals:
        pub = sig.get("published_at")
        if pub:
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub_dt >= recency_cutoff:
                    recency_pts += 3
            except ValueError:
                pass
        sources.add(sig.get("source", "unknown"))
        if sig.get("source") == "cisa_kev":
            kev_present = True

    source_pts = len(sources) * 5.0
    domain_pts = 10.0 if len(set(all_domains)) >= 2 else 0.0
    # KEV entries have confirmed real-world exploitation. A KEV signal with no CVSS
    # would otherwise score ~10 and never generate a card despite being high priority.
    kev_pts = 20.0 if kev_present else 0.0

    total = base + severity_pts + recency_pts + source_pts + domain_pts + kev_pts
    breakdown = {
        "base": base,
        "severity": severity_pts,
        "recency": recency_pts,
        "source_diversity": source_pts,
        "domain_span": domain_pts,
        "kev_bonus": kev_pts,
        "total": total,
    }
    return total, breakdown


def _max_severity(signals: list[dict[str, Any]]) -> str | None:
    """Return the highest severity value across a list of signal rows."""
    best: int = 0
    best_val: str | None = None
    for sig in signals:
        sev = sig.get("severity")
        if sev and _SEVERITY_RANK.get(sev, 0) > best:
            best = _SEVERITY_RANK[sev]
            best_val = sev
    return best_val


def _window_bounds(signals: list[dict[str, Any]]) -> tuple[str, str]:
    """Return ISO strings for the earliest and latest published_at in the group."""
    dates = []
    for sig in signals:
        pub = sig.get("published_at")
        if pub:
            try:
                dates.append(datetime.fromisoformat(pub.replace("Z", "+00:00")))
            except ValueError:
                pass
    if not dates:
        now_iso = datetime.now(UTC).isoformat()
        return now_iso, now_iso
    return min(dates).isoformat(), max(dates).isoformat()


def _already_clustered_ids_for_domain(db: Any, signal_ids: list[str], domain: "RiskDomain") -> set[str]:
    """
    Return the subset of signal_ids already in a cluster for this domain.

    Includes dismissed clusters intentionally - if a user dismissed a card, its
    signals should stay out of future runs. Only new signals ingested after the
    dismissal can re-trigger a cluster for the same threat.
    """
    if not signal_ids:
        return set()

    result = (
        db.table("signal_clusters")
        .select("signal_ids")
        .eq("risk_domain", domain.value)
        .execute()
    )

    clustered: set[str] = set()
    for row in result.data:
        for sid in row.get("signal_ids", []):
            clustered.add(sid)
    return clustered


_DOMAIN_ORDER = [
    RiskDomain.RANSOMWARE_EXTORTION,
    RiskDomain.DETECTION_RESPONSE,
    RiskDomain.SUPPLY_CHAIN,
    RiskDomain.DATA_EXPOSURE,
    RiskDomain.IDENTITY_CREDENTIAL,
    RiskDomain.VULNERABILITY_PATCH,
]


async def run_clustering() -> int:
    """
    Entry point called by the scheduler and the manual API trigger.
    Returns the number of new clusters written to the DB.

    Each domain clusters independently against all its tagged signals. A signal
    can appear in multiple domains' clusters when it genuinely spans domains -
    a threat intel report about ransomware TTPs and detection gaps belongs in
    both ransomware_extortion and detection_response. Domain order no longer
    affects which domains get coverage.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set - skipping clustering run")
        return 0

    db = get_db()
    window_start = (datetime.now(UTC) - timedelta(days=settings.clustering_window_days)).isoformat()

    # Fetch all signals in window once - partitioned by domain in Python below.
    # cvss_score and tags included because both help the LLM group related CVEs accurately.
    result = (
        db.table("signals")
        .select("id, source, title, summary, severity, cvss_score, risk_domains, published_at, signal_type, tags")
        .gte("published_at", window_start)
        .order("published_at", desc=False)
        .execute()
    )
    all_signals: list[dict[str, Any]] = result.data or []

    if len(all_signals) < 2:
        logger.info("Clustering skipped - fewer than 2 signals in window")
        return 0

    # Compute domains fresh from current domain_mapper rules rather than reading
    # the stored risk_domains column. This means domain rule changes take effect
    # immediately on the next clustering run without needing a backfill.
    for sig in all_signals:
        sig["_live_domains"] = [
            d.value for d in map_domains(
                sig.get("title") or "",
                sig.get("summary"),
                sig.get("tags") or [],
            )
        ]

    logger.info(
        "Clustering %d signals across %d domains (window: %d days)",
        len(all_signals), len(RiskDomain), settings.clustering_window_days,
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    total_written = 0

    for domain in _DOMAIN_ORDER:
        already_clustered = _already_clustered_ids_for_domain(
            db, [s["id"] for s in all_signals], domain
        )
        domain_signals = [
            s for s in all_signals
            if domain.value in s["_live_domains"]
            and s["id"] not in already_clustered
        ]

        if not domain_signals:
            logger.info("Domain %s: no new signals to cluster, skipping", domain.value)
            continue

        written, _ = await _cluster_domain(db, client, domain, domain_signals)
        total_written += written

    logger.info("Clustering complete: %d new clusters written", total_written)
    return total_written


_BATCH_SIZE = 150
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
# Full summary gives the model the context it needs to distinguish related CVEs -
# affected versions, vendor names, attack vectors often appear past the 400-char mark
_SUMMARY_CAP = 800


async def _cluster_domain(
    db: Any,
    client: anthropic.Anthropic,
    domain: "RiskDomain",
    signals: list[dict[str, Any]],
) -> tuple[int, set[str]]:
    """
    Cluster all signals for one domain, chunking into batches of _BATCH_SIZE.
    Signals are sorted by severity then recency so related high-priority signals
    land in the same batch. Returns (total_clusters_written, set_of_clustered_ids).
    """
    sorted_signals = sorted(
        signals,
        key=lambda s: (
            _SEV_RANK.get(s.get("severity") or "", 4),
            -(datetime.fromisoformat(s["published_at"].replace("Z", "+00:00")).timestamp()
              if s.get("published_at") else 0),
        ),
    )
    batches = [sorted_signals[i:i + _BATCH_SIZE] for i in range(0, len(sorted_signals), _BATCH_SIZE)]

    total_written = 0
    total_clustered: set[str] = set()

    for batch_num, batch in enumerate(batches, 1):
        logger.info(
            "Domain %s: batch %d/%d (%d signals)",
            domain.value, batch_num, len(batches), len(batch),
        )
        written, clustered = await _cluster_batch(db, client, domain, batch, batch_num, len(batches))
        total_written += written
        total_clustered.update(clustered)

    return total_written, total_clustered


async def _cluster_batch(
    db: Any,
    client: anthropic.Anthropic,
    domain: "RiskDomain",
    signals: list[dict[str, Any]],
    batch_num: int,
    total_batches: int,
) -> tuple[int, set[str]]:
    """Single LLM call for one batch of signals within a domain."""
    batch_label = f"batch {batch_num}/{total_batches}" if total_batches > 1 else ""

    signal_list = [
        {
            "index": i,
            "id": s["id"],
            "source": s["source"],
            "signal_type": s.get("signal_type"),
            "title": s["title"],
            "summary": (s.get("summary") or "")[:_SUMMARY_CAP],
            "severity": s.get("severity"),
            # cvss_score provides a precise severity anchor - more useful than the
            # bucketed severity string when distinguishing related CVEs
            "cvss_score": s.get("cvss_score"),
            "risk_domains": s.get("risk_domains", []),
            "published_at": s.get("published_at"),
            # tags carry CVE reference sources (NVD), ransomware flags (KEV),
            # and product categories - direct grouping evidence
            "tags": (s.get("tags") or [])[:8],
        }
        for i, s in enumerate(signals)
    ]

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            # temperature=0 makes clustering deterministic - same signals produce the
            # same clusters on every run, preventing variance between daily runs
            temperature=0,
            # 8192 prevents output truncation on busy domains that produce 20+ clusters
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            tools=[_CLUSTER_TOOL],
            tool_choice={"type": "tool", "name": "record_signal_clusters"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Here are {len(signal_list)} cybersecurity signals from the last "
                        f"{settings.clustering_window_days} days in the "
                        f"{domain.value.replace('_', ' ')} risk domain"
                        + (f" ({batch_label})" if batch_label else "")
                        + ". Identify any convergence patterns.\n\n"
                        f"Signals:\n{json.dumps(signal_list, separators=(',', ':'))}"
                    ),
                }
            ],
        )
    except Exception:
        logger.exception("Clustering API call failed for domain %s %s", domain.value, batch_label)
        return 0, set()

    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use_block:
        logger.warning("Domain %s %s: no tool_use block in response", domain.value, batch_label)
        return 0, set()

    clusters_data: list[dict[str, Any]] = tool_use_block.input.get("clusters", [])
    if not clusters_data:
        logger.info("Domain %s %s: model found no convergence patterns", domain.value, batch_label)
        return 0, set()

    written = 0
    claimed: set[str] = set()

    for cluster_def in clusters_data:
        indices: list[int] = cluster_def.get("signal_indices", [])
        if not indices:
            continue

        valid_signals = [signals[i] for i in indices if i < len(signals)]
        if not valid_signals:
            continue

        all_domains: list[str] = cluster_def.get("all_domains", [])
        score, breakdown = _score(valid_signals, all_domains)
        severity_max = _max_severity(valid_signals)
        window_s, window_e = _window_bounds(valid_signals)

        row = {
            "risk_domain": cluster_def["risk_domain"],
            "signal_ids": [s["id"] for s in valid_signals],
            "cluster_summary": cluster_def["cluster_summary"],
            "risk_vector": cluster_def["risk_vector"],
            "score": float(score),
            "signal_count": len(valid_signals),
            "source_count": len({s["source"] for s in valid_signals}),
            "severity_max": severity_max,
            "window_start": window_s,
            "window_end": window_e,
            "status": "pending",
            "metadata": {
                "all_domains": all_domains,
                "score_breakdown": breakdown,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            },
        }

        db.table("signal_clusters").insert(row).execute()
        claimed.update(s["id"] for s in valid_signals)
        written += 1
        logger.info(
            "Cluster written: domain=%s score=%.1f signals=%d sources=%d",
            cluster_def["risk_domain"],
            score,
            len(valid_signals),
            len({s["source"] for s in valid_signals}),
        )

    return written, claimed
