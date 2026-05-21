"""
Keyword-based severity inference for sources that don't provide CVSS scores.

CISA KEV, CISA advisories, and NCSC feeds carry no severity field. This module
infers severity from signal text so clustering and card generation have a
consistent severity signal across all sources.

Priority order: CRITICAL > HIGH > MEDIUM > LOW. The first tier whose keywords
match wins — we don't accumulate matches across tiers.

Why keyword inference rather than leaving severity null?
Null severity breaks the additive scoring model in clustering — a KEV entry
confirmed as actively exploited scores the same as a low-noise NVD advisory.
Keyword inference is imperfect but directionally correct: "actively exploited"
almost always means the risk is high, regardless of the formal CVSS score.
"""

import re

from app.models.enums import Severity

# Each tier is a list of patterns. Any match assigns that severity.
_TIERS: list[tuple[Severity, list[str]]] = [
    (
        Severity.CRITICAL,
        [
            "actively exploit",   # "actively exploited", "active exploitation"
            "zero.day",           # "zero-day", "0-day"
            "in the wild",
            "ransomware",
            "critical",
            "nation.state",
            "apt",                # advanced persistent threat
            "wormable",
        ],
    ),
    (
        Severity.HIGH,
        [
            r"\brce\b",           # remote code execution abbreviation
            "remote code execution",
            "unauthenticated",
            "privilege escalat",
            "authentication bypass",
            "auth bypass",
            "arbitrary code",
            r"\bhigh\b",
        ],
    ),
    (
        Severity.MEDIUM,
        [
            r"\bxss\b",
            "cross.site scripting",
            "cross.site request",
            r"\bcsrf\b",
            "information disclosure",
            "directory traversal",
            "path traversal",
            r"\bmedium\b",
        ],
    ),
    (
        Severity.LOW,
        [
            r"\blow\b",
        ],
    ),
]

# Pre-compile all patterns once at import time
_COMPILED: list[tuple[Severity, list[re.Pattern[str]]]] = [
    (sev, [re.compile(p, re.IGNORECASE) for p in patterns])
    for sev, patterns in _TIERS
]


def infer_severity(title: str, summary: str) -> Severity | None:
    """
    Return the highest matching severity tier, or None if no keywords match.

    Searches title first (usually more signal-dense), then summary.
    """
    text = f"{title} {summary}"
    for severity, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return severity
    return None
