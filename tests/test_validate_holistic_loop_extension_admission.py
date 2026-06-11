"""Purpose: verify holistic loop extension admission validation.
Governance scope: default loop registration admission, blocker preservation,
non-terminal closure boundary, and proof witness anchoring.
Dependencies: scripts.validate_holistic_loop_extension_admission.
Invariants:
  - Default loop registrations pass extension admission.
  - Missing evidence and authority remain blockers.
  - Admission cannot become terminal closure.
  - Admission witnesses must remain proof-anchored.
"""

from __future__ import annotations

import copy

from scripts import validate_holistic_loop_extension_admission as validator


def test_holistic_loop_extension_admission_guards_default_registry() -> None:
    errors = validator.validate_extension_admission()
    registry = validator.build_default_loop_registry()
    report = validator.build_report()

    assert errors == []
    assert tuple(manifest.loop_id for manifest in registry.list_manifests()) == tuple(
        sorted(validator.REQUIRED_LOOP_IDS)
    )
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True


def test_manifest_admission_rejects_behavior_rewrite_metadata() -> None:
    registry = validator.build_default_loop_registry()
    manifests = dict(registry.manifests)
    target = manifests["deployment_witness_loop"]
    manifests["deployment_witness_loop"] = target.__class__(
        loop_id=target.loop_id,
        name=target.name,
        purpose=target.purpose,
        owner=target.owner,
        risk_class=target.risk_class,
        allowed_modes=target.allowed_modes,
        required_authority=target.required_authority,
        required_evidence=target.required_evidence,
        closure_conditions=target.closure_conditions,
        rollback_policy=target.rollback_policy,
        learning_policy=target.learning_policy,
        canonical_steps=target.canonical_steps,
        metadata={**target.metadata, "behavior_rewrite": True},
    )

    errors = validator.validate_manifest_admission(
        validator.LoopRegistry(manifests=manifests, states=registry.states)
    )

    assert "loop deployment_witness_loop metadata behavior_rewrite must be false" in errors
    assert manifests["deployment_witness_loop"].metadata["behavior_rewrite"] is True
    assert len(errors) == 1


def test_summary_admission_rejects_missing_blocker_drift() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_loop = invalid_report["loops"][0]
    removed_blocker = invalid_loop["open_blockers"][0]
    invalid_loop["open_blockers"] = invalid_loop["open_blockers"][1:]

    errors = validator.validate_summary_admission(invalid_report)

    assert any("open blockers must include all missing authority and evidence" in error for error in errors)
    assert removed_blocker not in invalid_loop["open_blockers"]
    assert invalid_loop["missing_authority"] or invalid_loop["missing_evidence"]


def test_summary_admission_rejects_terminal_closure_claim() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_loop = invalid_report["loops"][0]
    loop_id = invalid_loop["loop_id"]
    invalid_loop["status_binding"]["terminal_closure"] = True
    invalid_loop["closure_report"]["closed"] = True

    errors = validator.validate_summary_admission(invalid_report)

    assert f"loop {loop_id} status_binding must not claim terminal closure" in errors
    assert f"loop {loop_id} closure report must not claim closure" in errors
    assert invalid_loop["status_binding"]["terminal_closure"] is True


def test_proof_anchor_admission_requires_runtime_witness() -> None:
    matrix = validator.proof_coverage_matrix()
    holistic_surface = next(
        surface
        for surface in matrix["surfaces"]
        if surface["surface_id"] == validator.HOLISTIC_SURFACE_ID
    )
    holistic_surface["runtime_witnesses"] = [
        witness
        for witness in holistic_surface["runtime_witnesses"]
        if witness != "holistic_loop_extension_admission_guards_default_registry"
    ]

    errors = validator.validate_proof_anchor_admission(matrix)

    assert "holistic loop extension admission witness is missing from proof matrix" in errors
    assert "holistic_loop_extension_admission_guards_default_registry" not in holistic_surface["runtime_witnesses"]
    assert holistic_surface["surface_id"] == validator.HOLISTIC_SURFACE_ID


def test_proof_anchor_admission_rejects_unanchored_witness() -> None:
    matrix = validator.proof_coverage_matrix()
    holistic_surface = next(
        surface
        for surface in matrix["surfaces"]
        if surface["surface_id"] == validator.HOLISTIC_SURFACE_ID
    )
    holistic_surface["runtime_witnesses"].append("unanchored_extension_admission_regression")

    errors = validator.validate_proof_anchor_admission(matrix)

    assert "holistic loop proof surface has unanchored witness labels" in errors
    assert "unanchored_extension_admission_regression" in holistic_surface["runtime_witnesses"]
    assert holistic_surface["surface_id"] == validator.HOLISTIC_SURFACE_ID
