"""Scientific research domain adapter tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from mcoi_runtime.domain_adapters import (
    ResearchActionKind,
    ResearchRequest,
    research_run_with_ucja,
    research_translate_from_universal,
    research_translate_to_universal,
)
from mcoi_runtime.domain_adapters.software_dev import UniversalResult


def _basic_request(**overrides) -> ResearchRequest:
    base = dict(
        kind=ResearchActionKind.HYPOTHESIS_FORMATION,
        summary="caffeine improves typing speed",
        study_id="study-2026-001",
        principal_investigator="dr-alice",
        peer_reviewers=("dr-bob", "dr-carol"),
        affected_corpus=("typing_dataset_v1", "caffeine_metadata"),
        acceptance_criteria=("statistical_significance_reached",),
        confidence_threshold=0.95,
        minimum_replications=2,
        statistical_power_target=0.8,
        blast_radius="study",
    )
    base.update(overrides)
    return ResearchRequest(**base)


# ---- translate_to_universal ----


def test_translate_purpose_for_each_kind():
    for kind in ResearchActionKind:
        req = _basic_request(kind=kind)
        uni = research_translate_to_universal(req)
        assert ":" in uni.purpose_statement


def test_translate_peer_reviewers_become_authority():
    req = _basic_request()
    uni = research_translate_to_universal(req)
    assert "peer_reviewer:dr-bob" in uni.authority_required
    assert "peer_reviewer:dr-carol" in uni.authority_required
    assert "peer_review_committee" in uni.observer_required


def test_translate_no_peer_reviewers_falls_back_to_pi():
    req = _basic_request(peer_reviewers=())
    uni = research_translate_to_universal(req)
    assert uni.authority_required == ("principal_investigator:dr-alice",)
    assert "study_audit_log" in uni.observer_required


def test_translate_emits_statistical_significance_constraint():
    req = _basic_request(confidence_threshold=0.99)
    uni = research_translate_to_universal(req)
    sig_constraints = [
        c for c in uni.constraint_set
        if c["domain"] == "statistical_significance"
    ]
    assert len(sig_constraints) == 1
    assert "0.0100" in sig_constraints[0]["restriction"]
    assert sig_constraints[0]["violation_response"] == "escalate"


def test_translate_emits_replication_constraint_only_when_required():
    req_with = _basic_request(minimum_replications=3)
    uni_with = research_translate_to_universal(req_with)
    rep_with = [c for c in uni_with.constraint_set if c["domain"] == "replication"]
    assert len(rep_with) == 1
    assert "3" in rep_with[0]["restriction"]

    req_without = _basic_request(minimum_replications=0)
    uni_without = research_translate_to_universal(req_without)
    rep_without = [c for c in uni_without.constraint_set if c["domain"] == "replication"]
    assert rep_without == []


def test_translate_power_constraint_is_warn_not_block():
    req = _basic_request()
    uni = research_translate_to_universal(req)
    power = [c for c in uni.constraint_set if c["domain"] == "statistical_power"]
    assert len(power) == 1
    assert power[0]["violation_response"] == "warn"


def test_translate_rejects_invalid_confidence():
    with pytest.raises(ValueError, match="confidence_threshold"):
        research_translate_to_universal(_basic_request(confidence_threshold=0.0))
    with pytest.raises(ValueError, match="confidence_threshold"):
        research_translate_to_universal(_basic_request(confidence_threshold=1.5))


def test_translate_rejects_negative_replications():
    with pytest.raises(ValueError, match="minimum_replications"):
        research_translate_to_universal(_basic_request(minimum_replications=-1))


def test_translate_rejects_invalid_power():
    with pytest.raises(ValueError, match="statistical_power_target"):
        research_translate_to_universal(_basic_request(statistical_power_target=0.0))
    with pytest.raises(ValueError, match="statistical_power_target"):
        research_translate_to_universal(_basic_request(statistical_power_target=1.1))


def test_translate_blast_radius_to_permeability():
    cases = {
        "study":      "closed",
        "subfield":   "selective",
        "field":      "selective",
        "discipline": "open",
    }
    for blast, expected in cases.items():
        uni = research_translate_to_universal(_basic_request(blast_radius=blast))
        assert uni.boundary_specification["permeability"] == expected


# ---- translate_from_universal: risk flags ----


def _result(state: str = "Pass") -> UniversalResult:
    return UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state=state,
    )


def test_no_replications_flagged():
    out = research_translate_from_universal(
        _result(), _basic_request(minimum_replications=0)
    )
    assert any("no_replications_required" in f for f in out.risk_flags)


def test_low_confidence_flagged():
    out = research_translate_from_universal(
        _result(), _basic_request(confidence_threshold=0.85)
    )
    assert any("low_confidence_threshold" in f for f in out.risk_flags)


def test_underpowered_study_flagged():
    out = research_translate_from_universal(
        _result(), _basic_request(statistical_power_target=0.5)
    )
    assert any("underpowered_study" in f for f in out.risk_flags)


def test_discipline_blast_radius_flagged():
    out = research_translate_from_universal(
        _result(), _basic_request(blast_radius="discipline")
    )
    assert any("discipline_blast_radius" in f for f in out.risk_flags)


def test_retraction_flagged_irreversible():
    out = research_translate_from_universal(
        _result(),
        _basic_request(kind=ResearchActionKind.RETRACTION),
    )
    assert any("retraction" in f for f in out.risk_flags)


def test_publication_without_peer_reviewers_flagged():
    out = research_translate_from_universal(
        _result(),
        _basic_request(
            kind=ResearchActionKind.PUBLICATION,
            peer_reviewers=(),
        ),
    )
    assert any("no_peer_reviewers" in f for f in out.risk_flags)


def test_solo_pi_data_collection_does_not_trigger_no_peer_reviewers():
    """no_peer_reviewers only fires for publication/retraction, not data
    collection (which doesn't require external authority)."""
    out = research_translate_from_universal(
        _result(),
        _basic_request(
            kind=ResearchActionKind.DATA_COLLECTION,
            peer_reviewers=(),
        ),
    )
    assert not any("no_peer_reviewers" in f for f in out.risk_flags)


# ---- translate_from_universal: protocol shape ----


def test_protocol_includes_peer_reviewer_routing():
    out = research_translate_from_universal(_result(), _basic_request())
    assert any("dr-bob" in s for s in out.research_protocol)
    assert any("dr-carol" in s for s in out.research_protocol)


def test_protocol_includes_alpha_threshold():
    out = research_translate_from_universal(
        _result(),
        _basic_request(confidence_threshold=0.99),
    )
    assert any("0.0100" in s for s in out.research_protocol)


def test_protocol_publication_includes_doi_step():
    out = research_translate_from_universal(
        _result(),
        _basic_request(kind=ResearchActionKind.PUBLICATION),
    )
    assert any("DOI" in s for s in out.research_protocol)


def test_protocol_retraction_includes_registry_step():
    out = research_translate_from_universal(
        _result(),
        _basic_request(kind=ResearchActionKind.RETRACTION),
    )
    assert any("retracted" in s for s in out.research_protocol)


def test_protocol_replication_includes_comparison_step():
    out = research_translate_from_universal(
        _result(),
        _basic_request(kind=ResearchActionKind.REPLICATION),
    )
    assert any(
        "Compare" in s and "tolerance" in s for s in out.research_protocol
    )


# ---- run_with_ucja end-to-end ----


def test_run_with_ucja_complete_request_passes():
    out = research_run_with_ucja(_basic_request())
    assert out.governance_status == "approved"
    assert any("Capture initial state" in s for s in out.research_protocol)
    assert any("statistical inference" in s for s in out.research_protocol)


def test_run_with_ucja_no_acceptance_criteria_blocks_at_l9():
    out = research_run_with_ucja(_basic_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_with_ucja_retraction_completes_with_irreversible_marker():
    out = research_run_with_ucja(
        _basic_request(kind=ResearchActionKind.RETRACTION),
    )
    assert out.governance_status == "approved"
    assert any("retraction" in f for f in out.risk_flags)


def test_result_carries_threshold_and_replications():
    out = research_run_with_ucja(
        _basic_request(confidence_threshold=0.99, minimum_replications=5),
    )
    assert out.confidence_threshold == 0.99
    assert out.minimum_replications == 5
