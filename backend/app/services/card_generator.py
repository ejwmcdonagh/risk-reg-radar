"""
Provocation card generator — Step 3 of the Regulatory Radar build sequence.

Takes pending signal clusters above the score threshold and generates a
5-layer provocation card for each using Claude.

The 5 layers (from the product brief):
  1. Signal headline    - what is happening right now, present tense
  2. Evidence stack     - the signals that triggered this card, source attributed
  3. Compliance gap     - where this falls through the audit landscape
  4. Contextual question - "is this true in your organisation?"
  5. Board talking point - one paragraph the CISO can use almost verbatim

Why tool use for card generation?
The 5 layers need to arrive as structured fields — the dashboard renders each
layer differently (headline as h1, evidence as bullets, talking point as prose).
Tool use guarantees the schema; free-text generation would require brittle parsing.

Why run card generation separately from clustering?
Clustering is a batch operation over many signals. Card generation is a single
focused call per cluster. Keeping them separate lets us re-generate a card
(e.g. after prompt tuning) without re-running clustering.
"""

import logging
from typing import Any

import anthropic

from app.config import settings
from app.db.client import get_db

logger = logging.getLogger(__name__)

_CARD_TOOL: dict[str, Any] = {
    "name": "write_provocation_card",
    "description": (
        "Write a 5-layer provocation card for a CISO audience. "
        "Each layer serves a distinct purpose in a board briefing context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "signal_headline": {
                "type": "string",
                "description": (
                    "Present-tense headline describing what is happening right now. "
                    "Max 15 words. Factual, not alarmist. No jargon. "
                    "Example: 'Attackers are actively exploiting a critical Cisco IOS-XE flaw across UK infrastructure.'"
                ),
            },
            "evidence_stack": {
                "type": "array",
                "description": "The signals that triggered this card, one entry per signal.",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source name (CISA, NVD, NCSC, etc.)"},
                        "title": {"type": "string", "description": "Signal title"},
                        "url": {"type": "string", "description": "Source URL if available"},
                        "point": {
                            "type": "string",
                            "description": "One sentence: what this specific signal adds to the picture",
                        },
                    },
                    "required": ["source", "title", "point"],
                },
            },
            "compliance_gap": {
                "type": "string",
                "description": (
                    "2-3 sentences identifying which regulatory or audit framework "
                    "this threat falls through. Reference specific frameworks by name "
                    "(NIS2, DORA, GDPR, ISO 27001, Cyber Essentials, FCA SYSC, etc.). "
                    "Focus on the gap — what the framework requires vs. what this threat exposes."
                ),
            },
            "contextual_question": {
                "type": "string",
                "description": (
                    "One direct question the CISO can pose to their security team or board. "
                    "Should be answerable with yes/no or a specific metric. "
                    "Example: 'Do we have confirmed patch coverage for this CVE across our "
                    "internet-facing Cisco estate, and when was it last verified?'"
                ),
            },
            "board_talking_point": {
                "type": "string",
                "description": (
                    "One paragraph (4-6 sentences) the CISO can read almost verbatim in a "
                    "board meeting. Connects the technical threat to commercial consequence "
                    "(regulatory fine, insurance impact, operational disruption, reputational risk). "
                    "Plain English, no acronyms without explanation, written for a non-technical audience."
                ),
            },
        },
        "required": [
            "signal_headline",
            "evidence_stack",
            "compliance_gap",
            "contextual_question",
            "board_talking_point",
        ],
    },
}

_SYSTEM_PROMPT = """You are a senior cyber risk advisor writing intelligence briefings for CISOs at
large regulated organisations (financial services, critical national infrastructure, healthcare).

Your job is to translate technical threat signals into board-ready intelligence. The audience
is a CISO who needs to brief a board that is not technically literate but is legally accountable
for cyber risk.

Tone: direct, evidence-based, commercially aware. Not alarmist. Not vague.
The board talking point should connect the threat to something the board cares about:
regulatory liability, insurance premiums, operational continuity, or reputational damage.

Reference real regulatory frameworks by name where relevant:
- UK: NIS2 (if applicable), UK GDPR, FCA SYSC 13, Cyber Essentials, NCSC CAF
- EU: DORA (financial services), NIS2, GDPR
- Global: ISO 27001/27002, NIST CSF, SOC 2

Do not fabricate CVE numbers, vendor names, or specific breach figures.
Only reference what is present in the signals you are given."""


async def generate_cards(cluster_ids: list[str] | None = None) -> int:
    """
    Generate provocation cards for pending clusters above the score threshold.

    If cluster_ids is provided, generate cards for only those clusters
    (used by the manual API trigger for targeted re-generation).
    Returns the number of cards written.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping card generation")
        return 0

    db = get_db()

    if cluster_ids:
        result = (
            db.table("signal_clusters")
            .select("*")
            .in_("id", cluster_ids)
            .execute()
        )
    else:
        result = (
            db.table("signal_clusters")
            .select("*")
            .eq("status", "pending")
            .gte("score", settings.card_score_threshold)
            .order("score", desc=True)
            .execute()
        )

    clusters: list[dict[str, Any]] = result.data or []

    if not clusters:
        logger.info("Card generation: no qualifying clusters found")
        return 0

    logger.info("Generating cards for %d clusters", len(clusters))
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    written = 0

    for cluster in clusters:
        try:
            card_written = await _generate_one(db, client, cluster)
            if card_written:
                written += 1
        except Exception:
            logger.exception("Card generation failed for cluster %s", cluster["id"])
            # Continue to next cluster rather than aborting the whole run
            continue

    logger.info("Card generation complete: %d cards written", written)
    return written


async def _generate_one(db: Any, client: anthropic.Anthropic, cluster: dict[str, Any]) -> bool:
    """Generate and persist a single provocation card. Returns True if written."""
    cluster_id: str = cluster["id"]
    signal_ids: list[str] = cluster.get("signal_ids", [])

    if not signal_ids:
        return False

    # Fetch the full signals for this cluster
    signals_result = (
        db.table("signals")
        .select("source, title, summary, severity, url, signal_type, risk_domains")
        .in_("id", signal_ids)
        .execute()
    )
    signals: list[dict[str, Any]] = signals_result.data or []

    if not signals:
        return False

    # Build a compact signal list for the prompt
    signal_descriptions = [
        {
            "source": s["source"].upper().replace("_", " "),
            "title": s["title"],
            "summary": (s.get("summary") or "")[:500],
            "severity": s.get("severity"),
            "url": s.get("url") or "",
            "signal_type": s.get("signal_type"),
        }
        for s in signals
    ]

    user_message = (
        f"Generate a provocation card for the following signal cluster.\n\n"
        f"Cluster summary: {cluster['cluster_summary']}\n"
        f"Risk vector: {cluster['risk_vector']}\n"
        f"Primary domain: {cluster['risk_domain']}\n"
        f"All domains: {', '.join(cluster.get('metadata', {}).get('all_domains', [cluster['risk_domain']]))}\n"
        f"Signal count: {cluster['signal_count']}\n"
        f"Source count: {cluster['source_count']}\n"
        f"Highest severity: {cluster.get('severity_max') or 'unknown'}\n\n"
        f"Signals:\n"
        + "\n".join(
            f"- [{s['source']}] {s['title']}"
            + (f" (severity: {s['severity']})" if s.get("severity") else "")
            + (f"\n  {s['summary']}" if s.get("summary") else "")
            for s in signal_descriptions
        )
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        tools=[_CARD_TOOL],
        tool_choice={"type": "tool", "name": "write_provocation_card"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_block:
        logger.warning("No tool_use block in card generation response for cluster %s", cluster_id)
        return False

    card_input: dict[str, Any] = tool_block.input

    # Build the evidence stack — use the model's structured output but enrich
    # with the actual signal URLs from the DB which are more reliable
    evidence_stack = card_input.get("evidence_stack", [])
    url_by_title = {s["title"]: s.get("url", "") for s in signal_descriptions}
    for item in evidence_stack:
        if not item.get("url"):
            item["url"] = url_by_title.get(item.get("title", ""), "")

    card_row = {
        "cluster_id": cluster_id,
        "signal_headline": card_input["signal_headline"],
        "evidence_stack": evidence_stack,
        "compliance_gap": card_input["compliance_gap"],
        "contextual_question": card_input["contextual_question"],
        "board_talking_point": card_input["board_talking_point"],
        "risk_domain": cluster["risk_domain"],
        "score": cluster["score"],
        "metadata": {
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "cluster_summary": cluster["cluster_summary"],
        },
    }

    db.table("provocation_cards").insert(card_row).execute()

    # Mark the cluster so it isn't re-processed on the next run
    db.table("signal_clusters").update({"status": "card_generated"}).eq("id", cluster_id).execute()

    logger.info(
        "Card written: cluster=%s domain=%s score=%.1f",
        cluster_id,
        cluster["risk_domain"],
        cluster["score"],
    )
    return True
