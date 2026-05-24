"""Φ_gov decision observability — dedicated metric family (USCL v3.3 / A1).

The construct write path records the OVERALL Φ_gov verdict into dedicated
counters (`phi_gov_decisions`, `phi_gov_denials_by_category`) that are kept
SEPARATE from the chain counters — they never enter `total_runs` /
`total_denials` / `recent_rejections` / `denials_by_guard`. That separation is
what makes this additive rather than a metrics-contract change, and is the
core property these tests lock.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.app.routers.constructs._governance import (
    _record_phi_gov_decision,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY,
    VERDICT_ALLOWED,
    VERDICT_DENIED,
)
from mcoi_runtime.substrate.phi_gov import Judgment, ProofState


@pytest.fixture(autouse=True)
def _reset_metrics():
    REGISTRY.reset()
    yield
    REGISTRY.reset()


# ---- dedicated counters ----


def test_allowed_decision_counted():
    REGISTRY.record_phi_gov_decision(verdict=VERDICT_ALLOWED)
    snap = REGISTRY.snapshot()
    assert snap.phi_gov_decisions == {"allowed": 1}
    assert snap.phi_gov_denials_by_category == {}


def test_denied_decision_counted_with_category():
    REGISTRY.record_phi_gov_decision(
        verdict=VERDICT_DENIED, category="cascade_escalated"
    )
    snap = REGISTRY.snapshot()
    assert snap.phi_gov_decisions == {"denied": 1}
    assert snap.phi_gov_denials_by_category == {"cascade_escalated": 1}


def test_denied_without_category_falls_back_to_unknown():
    REGISTRY.record_phi_gov_decision(verdict=VERDICT_DENIED)
    snap = REGISTRY.snapshot()
    assert snap.phi_gov_denials_by_category == {"unknown": 1}


def test_invalid_verdict_rejected():
    with pytest.raises(ValueError):
        REGISTRY.record_phi_gov_decision(verdict="maybe")


# ---- the core safety property: chain aggregates are untouched ----


def test_phi_gov_counters_do_not_touch_chain_aggregates():
    REGISTRY.record_phi_gov_decision(
        verdict=VERDICT_DENIED, category="phi_agent_blocked_at"
    )
    snap = REGISTRY.snapshot()
    assert snap.total_runs() == 0
    assert snap.total_denials() == 0
    assert snap.recent_rejections == ()
    assert snap.denials_by_guard == {}
    assert snap.runs_by_surface_verdict == {}


# ---- helper maps a Judgment to the counters ----


def test_helper_maps_judgment_to_counters():
    _record_phi_gov_decision(
        Judgment(state=ProofState.PASS, reason="all deltas approved")
    )
    _record_phi_gov_decision(
        Judgment(
            state=ProofState.FAIL,
            reason="cascade_escalated:2_unresolved_invariant_violation",
        )
    )
    snap = REGISTRY.snapshot()
    assert snap.phi_gov_decisions == {"allowed": 1, "denied": 1}
    assert snap.phi_gov_denials_by_category == {"cascade_escalated": 1}


# ---- prometheus exposition ----


def test_prometheus_exposition_includes_phi_gov_families():
    REGISTRY.record_phi_gov_decision(verdict=VERDICT_ALLOWED)
    REGISTRY.record_phi_gov_decision(
        verdict=VERDICT_DENIED, category="cascade_escalated"
    )
    body = REGISTRY.snapshot().to_prometheus_text()
    assert 'mullu_phi_gov_decisions_total{verdict="allowed"} 1' in body
    assert 'mullu_phi_gov_decisions_total{verdict="denied"} 1' in body
    assert 'mullu_phi_gov_denials_total{category="cascade_escalated"} 1' in body
