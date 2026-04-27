"""UCJA L0-L9 layer + pipeline tests."""
from __future__ import annotations

import pytest

from mcoi_runtime.ucja import (
    JobDraft,
    LayerResult,
    LayerVerdict,
    UCJAPipeline,
    l0_qualification,
    l1_purpose_boundary,
    l4_decomposition,
    l9_closure,
)


# Minimal valid request that should pass all 10 layers
def _full_payload() -> dict:
    return {
        "purpose_statement": "eliminate_defect: fix broken auth",
        "initial_state_descriptor": {"phase": "broken"},
        "target_state_descriptor": {"phase": "fixed"},
        "boundary_specification": {
            "inside_predicate": "auth_module",
            "interface_points": ["login.py"],
            "permeability": "selective",
        },
        "authority_required": ["repo_write_access"],
        "acceptance_criteria": ["auth_test_passes", "no_regression"],
        "blast_radius": "module",
        "causation_mechanism": "patch",
    }


# ---- LayerResult contract ----


def test_layer_result_reject_requires_reason():
    with pytest.raises(ValueError, match="requires a reason"):
        LayerResult(verdict=LayerVerdict.REJECT, reason="")


def test_layer_result_reclassify_requires_reason():
    with pytest.raises(ValueError, match="requires a reason"):
        LayerResult(verdict=LayerVerdict.RECLASSIFY, reason="")


def test_layer_result_pass_no_reason_required():
    r = LayerResult(verdict=LayerVerdict.PASS)
    assert r.reason == ""


# ---- L0 qualification ----


def test_l0_rejects_empty_purpose():
    draft = JobDraft(request_payload={})
    _, result = l0_qualification(draft)
    assert result.verdict == LayerVerdict.REJECT
    assert "purpose_statement" in result.reason


def test_l0_reclassifies_empty_initial_state():
    draft = JobDraft(request_payload={"purpose_statement": "do something"})
    _, result = l0_qualification(draft)
    assert result.verdict == LayerVerdict.RECLASSIFY


def test_l0_reclassifies_empty_target_state():
    draft = JobDraft(
        request_payload={
            "purpose_statement": "do",
            "initial_state_descriptor": {"x": 1},
        }
    )
    _, result = l0_qualification(draft)
    assert result.verdict == LayerVerdict.RECLASSIFY


def test_l0_rejects_unbounded_transformation():
    draft = JobDraft(
        request_payload={
            "purpose_statement": "do",
            "initial_state_descriptor": {"x": 1},
            "target_state_descriptor": {"x": 2},
            "boundary_specification": {},
        }
    )
    _, result = l0_qualification(draft)
    assert result.verdict == LayerVerdict.REJECT
    assert "boundary" in result.reason.lower()


def test_l0_passes_complete_request():
    draft = JobDraft(request_payload=_full_payload())
    new_draft, result = l0_qualification(draft)
    assert result.verdict == LayerVerdict.PASS
    assert new_draft.qualified is True


# ---- L1 ----


def test_l1_reclassifies_when_no_authority():
    draft = JobDraft(request_payload={"purpose_statement": "p"})
    _, result = l1_purpose_boundary(draft)
    assert result.verdict == LayerVerdict.RECLASSIFY


def test_l1_passes_with_authority():
    payload = _full_payload()
    draft = JobDraft(request_payload=payload)
    new_draft, result = l1_purpose_boundary(draft)
    assert result.verdict == LayerVerdict.PASS
    assert new_draft.purpose_statement == payload["purpose_statement"]
    assert new_draft.authority_required == ("repo_write_access",)


# ---- L4 ----


def test_l4_creates_one_task_per_criterion():
    payload = _full_payload()
    draft = JobDraft(request_payload=payload)
    new_draft, result = l4_decomposition(draft)
    assert result.verdict == LayerVerdict.PASS
    assert len(new_draft.task_descriptions) == len(payload["acceptance_criteria"])


def test_l4_default_task_when_no_criteria():
    draft = JobDraft(request_payload={})
    new_draft, _ = l4_decomposition(draft)
    assert new_draft.task_descriptions == ("apply_transformation",)


# ---- L9 ----


def test_l9_reclassifies_without_acceptance_criteria():
    draft = JobDraft(request_payload={})
    _, result = l9_closure(draft)
    assert result.verdict == LayerVerdict.RECLASSIFY


def test_l9_passes_with_criteria():
    payload = _full_payload()
    draft = JobDraft(request_payload=payload)
    new_draft, result = l9_closure(draft)
    assert result.verdict == LayerVerdict.PASS
    assert len(new_draft.closure_criteria) == 2
    assert len(new_draft.drift_detectors) >= 3


# ---- Pipeline ----


def test_pipeline_full_run_accepts_complete_request():
    pipeline = UCJAPipeline()
    outcome = pipeline.run(_full_payload())
    assert outcome.accepted
    assert outcome.terminal_verdict == LayerVerdict.PASS
    assert outcome.draft.is_complete()
    assert len(outcome.draft.layer_results) == 10


def test_pipeline_halts_on_l0_rejection():
    pipeline = UCJAPipeline()
    outcome = pipeline.run({})
    assert outcome.rejected
    assert outcome.halted_at_layer == "L0_qualification"
    assert len(outcome.draft.layer_results) == 1


def test_pipeline_halts_on_l1_reclassify():
    payload = {
        "purpose_statement": "p",
        "initial_state_descriptor": {"x": 1},
        "target_state_descriptor": {"x": 2},
        "boundary_specification": {"inside_predicate": "scope"},
        # no authority_required → L1 reclassifies
    }
    pipeline = UCJAPipeline()
    outcome = pipeline.run(payload)
    assert outcome.reclassified
    assert outcome.halted_at_layer == "L1_purpose_boundary"


def test_pipeline_layer_results_recorded_in_order():
    pipeline = UCJAPipeline()
    outcome = pipeline.run(_full_payload())
    layer_names = [name for name, _ in outcome.draft.layer_results]
    expected = [
        "L0_qualification",
        "L1_purpose_boundary",
        "L2_transformation",
        "L3_dependency",
        "L4_decomposition",
        "L5_functional",
        "L6_flow_connector",
        "L7_failure_risk",
        "L8_temporal",
        "L9_closure",
    ]
    assert layer_names == expected


def test_pipeline_l7_flags_system_blast_radius():
    payload = _full_payload()
    payload["blast_radius"] = "system"
    pipeline = UCJAPipeline()
    outcome = pipeline.run(payload)
    assert outcome.accepted
    assert any("system_blast_radius" in r for r in outcome.draft.risks)


def test_pipeline_flow_contracts_chain_groups():
    payload = _full_payload()
    # Three criteria → three tasks → three groups → two flow contracts
    payload["acceptance_criteria"] = ["a", "b", "c"]
    pipeline = UCJAPipeline()
    outcome = pipeline.run(payload)
    assert outcome.accepted
    assert len(outcome.draft.functional_groups) == 3
    assert len(outcome.draft.flow_contracts) == 2


def test_pipeline_reclassifies_on_l9_when_no_criteria():
    payload = _full_payload()
    payload["acceptance_criteria"] = []  # blank out
    pipeline = UCJAPipeline()
    outcome = pipeline.run(payload)
    assert outcome.reclassified
    assert outcome.halted_at_layer == "L9_closure"


def test_job_draft_is_complete_only_when_all_layers_pass():
    draft = JobDraft()
    assert not draft.is_complete()
    # Add a mix of pass and reclassify
    draft = draft.with_layer("L0", LayerResult(verdict=LayerVerdict.PASS))
    draft = draft.with_layer("L1", LayerResult(
        verdict=LayerVerdict.RECLASSIFY, reason="x"
    ))
    assert not draft.is_complete()
