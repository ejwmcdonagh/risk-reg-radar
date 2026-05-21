"""
Signal combination detection - Step 2 of the Regulatory Radar build sequence.

Approach:
- Pull signals from the last N days (configurable, default 7)
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
from app.models.enums import Severity

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

Your job is to find groups of signals that are pointing at the same underlying threat.
A genuine cluster has signals that share a common cause: the same CVE, the same exploit
technique, the same threat actor campaign, the same vendor being targeted across multiple
advisories.

Do not group signals just because they share a broad category like "ransomware" or
"vulnerabilities". The threshold for a multi-signal cluster is: would a CISO reading these
signals together have reason to believe they represent a single developing story?

Single-signal clusters are allowed when a signal is significant enough to stand alone -
for example: a confirmed ransomware campaign advisory, an NCSC alert with no related signals,
or a critical actively-exploited CVE with no peer signals. Use single-signal clusters
sparingly and only for genuinely high-importance signals.

A signal can only belong to one cluster. Signals that are neither part of a convergence
pattern nor significant enough to stand alone should not be clustered."""


def _score(signals: list[dict[str, Any]], all_domains: list[str]) -> tuple[float, dict[str, Any]]:
    """
    Additive scoring model. Returns (total_score, breakdown_dict).

    Components:
    - Base: 2 points per signal
    - Severity: CRITICAL=10, HIGH=5, MEDIUM=2 per signal
    - Recency: +3 per signal published within last 7 days
    - Source diversity: +5 per unique source (cross-source = stronger signal)
    - Domain span: +10 if cluster touches 2+ domains (multi-vector = board-relevant)
    """
    now = datetime.now(UTC)
    recency_cutoff = now - timedelta(days=7)

    base = len(signals) * 2.0
    severity_pts = 0.0
    recency_pts = 0.0
    sources: set[str] = set()

    for sig in signals:
        sev = sig.get("severity")
        if sev == Severity.CRITICAL.value:
            severity_pts += 10
        elif sev == Severity.HIGH.value:
            severity_pts += 5
        elif sev == Severity.MEDIUM.value:
            severity_pts += 2

        pub = sig.get("published_at")
        if pub:
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub_dt >= recency_cutoff:
                    recency_pts += 3
            except ValueError:
                pass

        sources.add(sig.get("source", "unknown"))

    source_pts = len(sources) * 5.0
    domain_pts = 10.0 if len(set(all_domains)) >= 2 else 0.0

    total = base + severity_pts + recency_pts + source_pts + domain_pts
    breakdown = {
        "base": base,
        "severity": severity_pts,
        "recency": recency_pts,
        "source_diversity": source_pts,
        "domain_span": domain_pts,
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


def _already_clustered_ids(db: Any, signal_ids: list[str]) -> set[str]:
    """
    Return the subset of signal_ids that already appear in an active cluster.

    We query the signal_clusters table and look for any row whose signal_ids
    array overlaps ours using Postgres array overlap operator (&&). Signals
    already in a cluster are excluded from re-clustering so we don't generate
    duplicate cluster rows across daily runs.
    """
    if not signal_ids:
        return set()

    # PostgREST doesn't expose the && operator directly, so we fetch all
    # active cluster rows and filter in Python. This is acceptable for V1
    # because the cluster count is small - revisit with an RPC if it grows.
    result = (
        db.table("signal_clusters")
        .select("signal_ids")
        .neq("status", "dismissed")
        .execute()
    )

    clustered: set[str] = set()
    for row in result.data:
        for sid in row.get("signal_ids", []):
            clustered.add(sid)
    return clustered


async def run_clustering() -> int:
    """
    Entry point called by the scheduler and the manual API trigger.
    Returns the number of new clusters written to the DB.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set - skipping clustering run")
        return 0

    db = get_db()
    window_start = (datetime.now(UTC) - timedelta(days=settings.clustering_window_days)).isoformat()

    # Fetch recent signals - condensed to the fields the LLM needs
    result = (
        db.table("signals")
        .select("id, source, title, summary, severity, risk_domains, published_at, signal_type")
        .gte("published_at", window_start)
        .order("published_at", desc=False)
        .execute()
    )
    all_signals: list[dict[str, Any]] = result.data or []

    if len(all_signals) < 2:
        logger.info("Clustering skipped - fewer than 2 signals in window")
        return 0

    # Exclude signals already assigned to an active cluster
    existing_ids = _already_clustered_ids(db, [s["id"] for s in all_signals])
    signals = [s for s in all_signals if s["id"] not in existing_ids]

    if len(signals) < 2:
        logger.info("Clustering skipped - all recent signals already clustered")
        return 0

    logger.info("Running clustering on %d signals (window: %d days)", len(signals), settings.clustering_window_days)

    # Build the signal list we'll hand to Claude - strip raw_data to keep tokens down
    signal_list = [
        {
            "index": i,
            "id": s["id"],
            "source": s["source"],
            "title": s["title"],
            "summary": (s.get("summary") or "")[:400],  # cap per-signal token cost
            "severity": s.get("severity"),
            "risk_domains": s.get("risk_domains", []),
            "published_at": s.get("published_at"),
        }
        for i, s in enumerate(signals)
    ]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        # To switch to Opus, replace the model string and uncomment the thinking line.
        # Thinking is not supported on Haiku - only uncomment it when using Opus.
        model="claude-haiku-4-5-20251001",
        # model="claude-opus-4-7",
        # thinking={"type": "adaptive"},
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[_CLUSTER_TOOL],
        # Force tool use so we always get structured output, never a text refusal
        tool_choice={"type": "tool", "name": "record_signal_clusters"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here are {len(signal_list)} cybersecurity signals from the last "
                    f"{settings.clustering_window_days} days. Identify any convergence patterns.\n\n"
                    f"Signals:\n{json.dumps(signal_list, indent=2)}"
                ),
            }
        ],
    )

    # Extract the tool_use block - forced tool choice means it will always be there
    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if not tool_use_block:
        logger.warning("Clustering: no tool_use block in response")
        return 0

    clusters_data: list[dict[str, Any]] = tool_use_block.input.get("clusters", [])
    if not clusters_data:
        logger.info("Clustering: model found no convergence patterns in this window")
        return 0

    # Build and persist cluster rows
    written = 0
    for cluster_def in clusters_data:
        indices: list[int] = cluster_def.get("signal_indices", [])
        if not indices:
            continue

        # Guard against out-of-range indices from the model
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
        written += 1
        logger.info(
            "Cluster written: domain=%s score=%.1f signals=%d sources=%d",
            cluster_def["risk_domain"],
            score,
            len(valid_signals),
            len({s["source"] for s in valid_signals}),
        )

    logger.info("Clustering complete: %d new clusters written", written)
    return written
