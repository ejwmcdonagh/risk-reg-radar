"""
Unit tests for the cluster scoring function.

_score() determines whether a cluster ever generates a card (threshold: 30).
These tests pin the contract so a scoring change is explicit, not accidental.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.clustering import _score

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _sig(
    source: str = "nvd",
    severity: str | None = None,
    days_old: int = 10,
    is_kev: bool = False,
) -> dict:
    """Build a minimal signal dict."""
    source_name = "cisa_kev" if is_kev else source
    published = (datetime.now(UTC) - timedelta(days=days_old)).isoformat()
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "source": source_name,
        "severity": severity,
        "published_at": published,
        "risk_domains": ["vulnerability_patch"],
    }


# --------------------------------------------------------------------------
# Base scoring
# --------------------------------------------------------------------------

def test_base_two_points_per_signal():
    sigs = [_sig() for _ in range(3)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["base"] == 6.0  # 3 signals * 2


def test_base_capped_at_five_signals():
    # 8 signals should score the same base as 5
    sigs = [_sig() for _ in range(8)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["base"] == 10.0  # cap at 5 * 2


# --------------------------------------------------------------------------
# Severity scoring
# --------------------------------------------------------------------------

def test_severity_critical():
    sigs = [_sig(severity="critical")]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["severity"] == 10.0


def test_severity_high():
    sigs = [_sig(severity="high")]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["severity"] == 5.0


def test_severity_medium():
    sigs = [_sig(severity="medium")]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["severity"] == 2.0


def test_severity_none():
    sigs = [_sig(severity=None)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["severity"] == 0.0


def test_severity_uses_highest_when_capped():
    # 6 signals: 1 critical + 5 low. Cap is 5. Sorted by severity, the
    # critical is kept and one low is dropped, so severity should be 10.
    sigs = [_sig(severity="critical")] + [_sig(severity="low") for _ in range(5)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["severity"] == 10.0


# --------------------------------------------------------------------------
# Recency scoring
# --------------------------------------------------------------------------

def test_recency_recent_signal():
    sigs = [_sig(days_old=1)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["recency"] == 3.0


def test_recency_old_signal():
    sigs = [_sig(days_old=20)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["recency"] == 0.0


def test_recency_not_capped():
    # Recency is uncapped - 6 recent signals should score 18, not 15
    sigs = [_sig(days_old=1) for _ in range(6)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["recency"] == 18.0


# --------------------------------------------------------------------------
# Source diversity
# --------------------------------------------------------------------------

def test_source_diversity_single():
    sigs = [_sig(source="nvd") for _ in range(3)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["source_diversity"] == 5.0


def test_source_diversity_three_sources():
    sigs = [_sig(source="nvd"), _sig(source="cisa_advisory"), _sig(source="ncsc")]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["source_diversity"] == 15.0


# --------------------------------------------------------------------------
# Domain span bonus
# --------------------------------------------------------------------------

def test_domain_span_single():
    sigs = [_sig()]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["domain_span"] == 0.0


def test_domain_span_multi():
    sigs = [_sig()]
    score, breakdown = _score(sigs, ["vulnerability_patch", "ransomware_extortion"])
    assert breakdown["domain_span"] == 10.0


# --------------------------------------------------------------------------
# KEV bonus
# --------------------------------------------------------------------------

def test_kev_bonus_present():
    sigs = [_sig(is_kev=True)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["kev_bonus"] == 20.0


def test_kev_bonus_absent():
    sigs = [_sig(source="nvd")]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["kev_bonus"] == 0.0


def test_kev_bonus_one_kev_among_many():
    sigs = [_sig(source="nvd"), _sig(source="ncsc"), _sig(is_kev=True)]
    score, breakdown = _score(sigs, ["vulnerability_patch"])
    assert breakdown["kev_bonus"] == 20.0


# --------------------------------------------------------------------------
# Card generation threshold
# --------------------------------------------------------------------------

def test_typical_kev_cluster_exceeds_threshold():
    # KEV entry from two sources, both recent - should comfortably exceed 30
    sigs = [_sig(is_kev=True, days_old=1), _sig(source="cisa_advisory", days_old=2)]
    score, _ = _score(sigs, ["vulnerability_patch"])
    assert score >= 30, f"Expected >= 30 but got {score}"


def test_weak_cluster_below_threshold():
    # Single old signal from one source with no severity - should stay below 30
    sigs = [_sig(severity=None, days_old=25)]
    score, _ = _score(sigs, ["vulnerability_patch"])
    assert score < 30, f"Expected < 30 but got {score}"
