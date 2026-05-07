"""Tier 4 governance constructs."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.constructs import (
    Binding,
    Evolution,
    Integrity,
    Source,
    TIER4_RESPONSIBILITIES,
    Tier,
    Validation,
    verify_tier4_disambiguation,
)


def test_tier4_disambiguation():
    verify_tier4_disambiguation()
    assert len(set(TIER4_RESPONSIBILITIES.values())) == 5


# ---- Source ----


def test_source_basic():
    s = Source(
        origin_identifier="board_resolution_2026_03",
        authority_kind="primary",
        scope_description="all financial transactions over $10k",
        legitimacy_basis="bylaws_article_4_section_2",
    )
    assert s.tier == Tier.GOVERNANCE
    assert s.authority_kind == "primary"


def test_source_requires_legitimacy():
    with pytest.raises(ValueError, match="legitimacy"):
        Source(
            origin_identifier="x",
            scope_description="y",
            legitimacy_basis="",
        )


def test_source_invalid_authority_kind():
    with pytest.raises(ValueError):
        Source(
            origin_identifier="x",
            scope_description="y",
            legitimacy_basis="z",
            authority_kind="self_appointed",
        )


# ---- Binding ----


def test_binding_basic():
    chg = uuid4()
    b = Binding(
        agent_identifier="agent-42",
        action_description="approved transaction",
        consequence_change_id=chg,
        accountability_kind="direct",
    )
    assert b.consequence_change_id == chg


def test_binding_requires_consequence():
    with pytest.raises(ValueError, match="consequence"):
        Binding(
            agent_identifier="a",
            action_description="b",
        )


def test_binding_invalid_accountability():
    with pytest.raises(ValueError):
        Binding(
            agent_identifier="a",
            action_description="b",
            consequence_change_id=uuid4(),
            accountability_kind="vague",
        )


# ---- Validation ----


def test_validation_basic():
    v = Validation(
        target_pattern_id=uuid4(),
        criteria=("evidence_present", "schema_match"),
        evidence_refs=("audit_log_42",),
        confidence=0.9,
        decision="pass",
    )
    assert v.decision == "pass"


def test_validation_fail_requires_evidence():
    with pytest.raises(ValueError, match="evidence_refs"):
        Validation(
            target_pattern_id=uuid4(),
            criteria=("c1",),
            evidence_refs=(),
            decision="fail",
        )


def test_validation_fail_passes_with_evidence():
    v = Validation(
        target_pattern_id=uuid4(),
        criteria=("c1",),
        evidence_refs=("e1",),
        decision="fail",
    )
    assert v.decision == "fail"


def test_validation_unknown_decision():
    v = Validation(
        target_pattern_id=uuid4(),
        criteria=("c1",),
        decision="unknown",
    )
    assert v.decision == "unknown"


def test_validation_budget_unknown():
    v = Validation(
        target_pattern_id=uuid4(),
        criteria=("c1",),
        decision="budget_unknown",
    )
    assert v.decision == "budget_unknown"


def test_validation_invalid_decision():
    with pytest.raises(ValueError):
        Validation(
            target_pattern_id=uuid4(),
            criteria=("c1",),
            decision="maybe",
        )


# ---- Evolution ----


def test_evolution_basic():
    cur, prop = uuid4(), uuid4()
    e = Evolution(
        current_constraint_id=cur,
        proposed_constraint_id=prop,
        justification="security audit found gap",
        impact_assessment="affects 3 endpoints, no migrations needed",
        status="proposed",
    )
    assert e.status == "proposed"


def test_evolution_rejects_no_op():
    same = uuid4()
    with pytest.raises(ValueError, match="differ"):
        Evolution(
            current_constraint_id=same,
            proposed_constraint_id=same,
            justification="j",
            impact_assessment="i",
        )


def test_evolution_requires_justification():
    with pytest.raises(ValueError, match="justification"):
        Evolution(
            current_constraint_id=uuid4(),
            proposed_constraint_id=uuid4(),
            justification="",
            impact_assessment="i",
        )


def test_evolution_invalid_status():
    with pytest.raises(ValueError):
        Evolution(
            current_constraint_id=uuid4(),
            proposed_constraint_id=uuid4(),
            justification="j",
            impact_assessment="i",
            status="pending",  # not a valid status
        )


# ---- Integrity ----


def test_integrity_basic():
    p1, p2 = uuid4(), uuid4()
    i = Integrity(
        core_invariant_pattern_ids=(p1, p2),
        violation_detection_kind="continuous_monitor",
        repair_protocol="halt_writes_and_alert_oncall",
    )
    assert i.violation_detection_kind == "continuous_monitor"


def test_integrity_requires_repair_protocol():
    with pytest.raises(ValueError, match="repair_protocol"):
        Integrity(
            core_invariant_pattern_ids=(uuid4(),),
            repair_protocol="",
        )


def test_integrity_rejects_duplicate_invariants():
    p = uuid4()
    with pytest.raises(ValueError, match="distinct"):
        Integrity(
            core_invariant_pattern_ids=(p, p),
            repair_protocol="r",
        )


def test_integrity_invalid_detection_kind():
    with pytest.raises(ValueError):
        Integrity(
            core_invariant_pattern_ids=(uuid4(),),
            violation_detection_kind="vibes",
            repair_protocol="r",
        )
