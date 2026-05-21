"""
Risk intelligence card generator for Pulse.

Takes pending signal clusters above the score threshold and generates a
5-layer risk card for each using Claude.

The 5 layers:
  1. Signal headline     - what is happening right now, present tense
  2. Evidence stack      - the signals that triggered this card, source attributed
  3. Contextual question - "is this true in your organisation?"
  4. Regulatory exposure - which regulations make this commercially consequential
  5. Board talking point - plain English risk summary the CISO can take to the board

The framing is risk-first. Regulations are supporting evidence for why the risk
matters commercially, not the primary lens. A card about an actively exploited RCE
should open with the threat, not the compliance gap.
"""

import logging
from typing import Any

import anthropic

from app.config import settings
from app.db.client import get_db

logger = logging.getLogger(__name__)

_CARD_TOOL: dict[str, Any] = {
    "name": "write_risk_card",
    "description": (
        "Write a 5-layer risk intelligence card for a CISO audience. "
        "Risk is the primary lens. Regulatory context supports the risk story, it does not lead it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "signal_headline": {
                "type": "string",
                "description": (
                    "Present-tense headline describing the threat right now. "
                    "Max 15 words. Lead with what attackers are doing or what is broken, not with regulation. "
                    "Factual, direct, no jargon. "
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
                            "description": "One sentence: what this specific signal adds to the risk picture",
                        },
                    },
                    "required": ["source", "title", "point"],
                },
            },
            "contextual_question": {
                "type": "string",
                "description": (
                    "One direct question the CISO can pose to their security team or board. "
                    "Focus on exposure - do we have this? are we affected? have we verified? "
                    "Should be answerable with yes/no or a specific metric. "
                    "Example: 'Do we have confirmed patch coverage for this CVE across our "
                    "internet-facing Cisco estate, and when was it last verified?'"
                ),
            },
            "compliance_gap": {
                "type": "string",
                "description": (
                    "2-3 sentences explaining which regulations make this risk commercially consequential. "
                    "Frame it as: this risk exposes the organisation to [specific consequence] under [framework]. "
                    "Reference real frameworks: NIS2, UK GDPR, DORA, FCA SYSC 13, ISO 27001, Cyber Essentials. "
                    "This is supporting context for the risk, not the headline."
                ),
            },
            "board_talking_point": {
                "type": "string",
                "description": (
                    "3-4 short sentences a CISO can read almost verbatim to a board of non-technical directors. "
                    "Structure: (1) what is happening in the real world - no jargon, no CVE numbers, "
                    "no product names unless household words; (2) the specific business consequence - "
                    "choose the most credible from: fine with a real figure, insurance denial, "
                    "revenue-affecting downtime, or customer trust damage; "
                    "(3) the single action the board needs to approve or acknowledge. "
                    "Write like a CFO explaining a financial risk, not an engineer explaining a vulnerability. "
                    "No acronyms. No technical terms. Active voice. Short sentences. "
                    "Example: 'Criminals are actively exploiting a flaw in widely-used software to break into "
                    "corporate networks without needing a password. If they reach our systems before we close "
                    "this gap, we face potential fines of up to 4% of global turnover and our cyber insurer "
                    "may decline to pay out on a known unpatched vulnerability. We need to authorise emergency "
                    "patching this week and confirm completion before the next board cycle.'"
                ),
            },
            "affected_teams": {
                "type": "array",
                "description": (
                    "Which security teams are most likely to need to act on this card. "
                    "Pick 1-3 from this exact list: IAM, SOC, AppSec, Cloud/Infra, Network, Endpoint, GRC, Data/Privacy. "
                    "Only include teams with a clear connection to the threat - do not include all teams by default."
                ),
                "items": {"type": "string"},
            },
        },
        "required": [
            "signal_headline",
            "evidence_stack",
            "contextual_question",
            "compliance_gap",
            "board_talking_point",
            "affected_teams",
        ],
    },
}

_SYSTEM_PROMPT = """You are a threat intelligence analyst writing risk briefings for CISOs at large organisations.

Your job is to take clusters of live threat signals and turn them into clear, ranked risk cards.

Risk is always the primary lens. A card about an actively exploited vulnerability should open with
the threat - what attackers are doing, what systems are exposed, how serious the risk is. Regulations
are mentioned only where they make the commercial consequence more concrete.

Core principles:
- Lead every card with the threat, not the compliance angle
- Score and rank by real-world risk: active exploitation, breadth of exposure, severity
- Regulations are evidence of consequence, not the story itself
- The CISO should be able to take this card into any meeting - technical or executive

For the board talking point:
- Write for non-technical directors who think in revenue, liability, and reputation
- Open with what is happening in plain English - no jargon, no CVE numbers, no acronyms
- State the specific business consequence - a real fine figure, insurance impact, or operational risk
- End with one clear ask: what does the board need to approve or acknowledge?
- Three to four sentences. Short. Active voice.

For all other layers, write for the CISO - technically literate, commercially aware.
Reference real frameworks where relevant: NIS2, UK GDPR, DORA, FCA SYSC 13, ISO 27001, NCSC CAF.

Do not fabricate CVE numbers, vendor names, or breach figures beyond what the signals contain."""


async def generate_cards(cluster_ids: list[str] | None = None) -> int:
    """
    Generate provocation cards for pending clusters above the score threshold.

    If cluster_ids is provided, generate cards for only those clusters
    (used by the manual API trigger for targeted re-generation).
    Returns the number of cards written.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set - skipping card generation")
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
        # To switch to Opus, replace the model string and uncomment the thinking line.
        # Thinking is not supported on Haiku - only uncomment it when using Opus.
        model="claude-haiku-4-5-20251001",
        # model="claude-opus-4-7",
        # thinking={"type": "adaptive"},
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        tools=[_CARD_TOOL],
        tool_choice={"type": "tool", "name": "write_risk_card"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_block:
        logger.warning("No tool_use block in card generation response for cluster %s", cluster_id)
        return False

    card_input: dict[str, Any] = tool_block.input

    # Build the evidence stack - use the model's structured output but enrich
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
        "affected_teams": card_input.get("affected_teams", []),
        "risk_domain": cluster["risk_domain"],
        "score": cluster["score"],
        "metadata": {
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "cluster_summary": cluster["cluster_summary"],
            "signal_count": cluster["signal_count"],
            "source_count": cluster["source_count"],
            "severity_max": cluster.get("severity_max"),
            "all_domains": cluster.get("metadata", {}).get("all_domains", [cluster["risk_domain"]]),
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
