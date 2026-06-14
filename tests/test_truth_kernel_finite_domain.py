"""Mullu Truth Kernel finite-domain proof tests.

Purpose: verify local finite-domain proof threading before Rust kernel work.
Governance scope: deterministic finite-domain projection, contradiction,
    budget exhaustion, schema-compatible proof emission, and Mfidel atomicity.
Dependencies: mcoi_runtime.truth_kernel_finite_domain and kernel proof schema.
Invariants:
  - Exact finite projection emits a replayable kernel proof.
  - Budget-limited projection cannot become an exact truth result.
  - Constraint and Mfidel violations fail closed before proof emission.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.truth_kernel_adapter import (
    admit_truth_commit_candidate,
    build_truth_commit_candidate_from_proof,
)
from mcoi_runtime.truth_kernel_finite_domain import (
    FiniteTruthConstraint,
    FiniteTruthDomain,
    FiniteTruthKernel,
)


ROOT = Path(__file__).resolve().parent.parent
KERNEL_PROOF_SCHEMA_PATH = ROOT / "schemas" / "kernel_proof.schema.json"
TRUTH_COMMIT_SCHEMA_PATH = ROOT / "schemas" / "truth_commit_candidate.schema.json"
FINITE_PROJECTION_SUMMARY_FIXTURE_PATH = (
    ROOT / "examples" / "truth_kernel" / "truth_kernel_finite_projection_summary.json"
)


def _proof_validator() -> Draft202012Validator:
    schema = json.loads(KERNEL_PROOF_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _commit_validator() -> Draft202012Validator:
    schema = json.loads(TRUTH_COMMIT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _finite_projection_summary(proof, *, variable_id: str, budget_limit: int) -> dict:
    payload = proof.to_json_dict()
    return {
        "summary_id": "truth-kernel-finite-projection-summary-v1",
        "runtime_boundary": "finite-domain-proof-summary",
        "tenant_id": payload["tenant_id"],
        "proof_id": payload["proof_id"],
        "subject_ref": payload["subject_ref"],
        "variable_id": variable_id,
        "proof_state": proof.proof_state,
        "result_kind": proof.result_kind,
        "projection_values": list(proof.projection_values),
        "checked_state_count": proof.checked_state_count,
        "valid_state_count": proof.valid_state_count,
        "budget_limit": budget_limit,
        "limitations": payload["limitations"],
        "sandbox_witness_present": "witness:sandbox-isolated" in payload["witness_refs"],
        "deterministic_replay": payload["replay"]["deterministic"],
        "truth_mutation_authority": "adapter_required",
    }


def _truth_candidate(
    *,
    candidate_id: str,
    parent_kernel_signature: str,
    proof_kind: str = "ProjectionProof",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "tenant_id": "foundation-local",
        "candidate_kind": "constraint_addition",
        "parent_kernel_signature": parent_kernel_signature,
        "proposed_at": "2026-06-14T00:06:00Z",
        "actor_ref": "operator:local-control-studio",
        "source_refs": ["tests/test_truth_kernel_finite_domain.py"],
        "delta": {
            "delta_id": "truth-delta:finite-domain-color",
            "delta_kind": "constraint_addition",
            "operation": {
                "operation_type": "add_constraint",
                "payload": {"constraint_id": "constraint:color-red-blue"},
            },
            "affected_variable_ids": ["var:color"],
            "affected_constraint_ids": ["constraint:color-red-blue"],
            "includes_mfidel": False,
            "mfidel_atomicity_preserved": True,
            "change_summary": "Admit a generated finite-domain projection proof behind the adapter gate.",
        },
        "admission_boundary": {
            "result_authority": "exact_required",
            "requires_exact_result": True,
            "can_mutate_truth": True,
            "requires_governance_ref": True,
            "requires_trace_ref": True,
            "requires_sandbox_isolation": True,
        },
        "proof_obligations": [
            {
                "obligation_id": "proof-obligation:finite-domain-projection",
                "proof_kind": proof_kind,
                "required_for_mutation": True,
            }
        ],
        "status": "proposed",
        "candidate_hash": "truth-candidate-hash:finite-domain-color",
    }


def _color_kernel() -> FiniteTruthKernel:
    return FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(
                variable_id="var:color",
                values=("red", "blue", "green"),
                source_ref="domain:color",
            ),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:color-red-blue",
                scope=("var:color",),
                source_ref="constraint:color-red-blue",
                statement="Color must be red or blue.",
                allowed_assignments=(
                    {"var:color": "red"},
                    {"var:color": "blue"},
                ),
            ),
        ),
    )


def _paired_color_shape_kernel() -> FiniteTruthKernel:
    return FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(
                variable_id="var:color",
                values=("red", "blue", "green"),
                source_ref="domain:color",
            ),
            FiniteTruthDomain(
                variable_id="var:shape",
                values=("circle", "square", "triangle"),
                source_ref="domain:shape",
            ),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:paired-color-shape",
                scope=("var:color", "var:shape"),
                source_ref="constraint:paired-color-shape",
                statement="Only red-circle and blue-square pairs remain valid.",
                allowed_assignments=(
                    {"var:color": "red", "var:shape": "circle"},
                    {"var:color": "blue", "var:shape": "square"},
                ),
            ),
        ),
    )


def test_exact_projection_emits_schema_valid_replayable_proof() -> None:
    kernel = _color_kernel()

    proof = kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:color-projection",
        subject_ref="projection:var:color",
        generated_at="2026-06-14T00:02:00Z",
        budget_limit=8,
    )
    payload = proof.to_json_dict()

    _proof_validator().validate(payload)
    assert proof.proof_state == "Pass"
    assert proof.result_kind == "ExactResult"
    assert proof.projection_values == ("blue", "red")
    assert proof.checked_state_count == 3
    assert proof.valid_state_count == 2
    assert payload["conclusion"]["supports_truth_mutation"] is True
    assert payload["replay"]["deterministic"] is True
    assert payload["proof_hash"] == proof.proof_hash


def test_projection_proof_is_deterministic_for_same_kernel_and_request() -> None:
    first_kernel = _color_kernel()
    second_kernel = _color_kernel()

    first = first_kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:color-projection",
        subject_ref="projection:var:color",
        generated_at="2026-06-14T00:02:00Z",
        budget_limit=8,
    )
    second = second_kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:color-projection",
        subject_ref="projection:var:color",
        generated_at="2026-06-14T00:02:00Z",
        budget_limit=8,
    )

    assert first.kernel_signature == second.kernel_signature
    assert first.proof_hash == second.proof_hash
    assert first.to_json_dict() == second.to_json_dict()
    assert first.projection_values == second.projection_values


def test_python_finite_projection_summary_matches_cross_language_fixture() -> None:
    kernel = _color_kernel()
    budget_limit = 8

    proof = kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:finite-domain-color-parity",
        subject_ref="truth-candidate:finite-domain-color-parity",
        generated_at="2026-06-14T00:12:00Z",
        budget_limit=budget_limit,
    )
    expected = json.loads(FINITE_PROJECTION_SUMMARY_FIXTURE_PATH.read_text(encoding="utf-8"))
    summary = _finite_projection_summary(proof, variable_id="var:color", budget_limit=budget_limit)

    assert summary == expected
    assert summary["sandbox_witness_present"] is True
    assert summary["truth_mutation_authority"] == "adapter_required"
    assert summary["projection_values"] == ["blue", "red"]


def test_forced_value_projection_has_single_exact_value() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(
                variable_id="var:shape",
                values=("circle", "square"),
                source_ref="domain:shape",
            ),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:shape-circle",
                scope=("var:shape",),
                source_ref="constraint:shape-circle",
                statement="Shape must be circle.",
                allowed_assignments=({"var:shape": "circle"},),
            ),
        ),
    )

    proof = kernel.exact_projection(
        variable_id="var:shape",
        tenant_id="foundation-local",
        proof_id="kernel-proof:shape-forced",
        subject_ref="projection:var:shape",
        generated_at="2026-06-14T00:03:00Z",
        budget_limit=4,
    )

    assert proof.result_kind == "ExactResult"
    assert proof.projection_values == ("circle",)
    assert proof.valid_state_count == 1
    assert proof.to_json_dict()["conclusion"]["required_next_action"] == "commit_candidate"
    _proof_validator().validate(proof.to_json_dict())


def test_contradiction_projection_blocks_truth_mutation_support() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(
                variable_id="var:color",
                values=("red", "blue"),
                source_ref="domain:color",
            ),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:forbid-all-colors",
                scope=("var:color",),
                source_ref="constraint:forbid-all-colors",
                statement="No color remains valid.",
                forbidden_assignments=(
                    {"var:color": "red"},
                    {"var:color": "blue"},
                ),
            ),
        ),
    )

    proof = kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:color-contradiction",
        subject_ref="projection:var:color",
        generated_at="2026-06-14T00:04:00Z",
        budget_limit=4,
    )
    payload = proof.to_json_dict()

    _proof_validator().validate(payload)
    assert proof.proof_state == "Pass"
    assert proof.result_kind == "ContradictionResult"
    assert proof.projection_values == ()
    assert proof.valid_state_count == 0
    assert payload["conclusion"]["supports_truth_mutation"] is False
    assert payload["conclusion"]["required_next_action"] == "plan_sensing"
    assert payload["witness_refs"] == ["witness:sandbox-isolated", "witness:no-valid-state"]


def test_budget_exhaustion_cannot_emit_exact_projection() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:left", values=("a", "b", "c"), source_ref="domain:left"),
            FiniteTruthDomain(variable_id="var:right", values=("x", "y", "z"), source_ref="domain:right"),
        ),
    )

    proof = kernel.exact_projection(
        variable_id="var:left",
        tenant_id="foundation-local",
        proof_id="kernel-proof:budget-limited",
        subject_ref="projection:var:left",
        generated_at="2026-06-14T00:05:00Z",
        budget_limit=4,
    )
    payload = proof.to_json_dict()

    _proof_validator().validate(payload)
    assert proof.proof_state == "BudgetUnknown"
    assert proof.result_kind == "BudgetExceededResult"
    assert proof.projection_values == ()
    assert proof.checked_state_count == 4
    assert payload["conclusion"]["supports_truth_mutation"] is False
    assert payload["limitations"] == ["budget_exceeded_before_exact_projection"]
    assert payload["budget"]["used"] == 4


def test_invalid_constraint_assignment_fails_before_proof_emission() -> None:
    with pytest.raises(RuntimeCoreInvariantError) as exc:
        FiniteTruthKernel(
            domains=(
                FiniteTruthDomain(
                    variable_id="var:color",
                    values=("red", "blue"),
                    source_ref="domain:color",
                ),
            ),
            constraints=(
                FiniteTruthConstraint(
                    constraint_id="constraint:unknown-color",
                    scope=("var:color",),
                    source_ref="constraint:unknown-color",
                    statement="Color must be green.",
                    allowed_assignments=({"var:color": "green"},),
                ),
            ),
        )

    assert "constraint assignment value must exist in domain" in str(exc.value)
    assert exc.type is RuntimeCoreInvariantError
    assert "green" not in str(exc.value)


def test_constraint_assignment_key_order_does_not_change_scope_binding() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:color", values=("red", "blue"), source_ref="domain:color"),
            FiniteTruthDomain(variable_id="var:shape", values=("circle", "square"), source_ref="domain:shape"),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:ordered-scope",
                scope=("var:color", "var:shape"),
                source_ref="constraint:ordered-scope",
                statement="Only the red-circle pair remains valid.",
                allowed_assignments=({"var:shape": "circle", "var:color": "red"},),
            ),
        ),
    )

    proof = kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:ordered-scope",
        subject_ref="projection:ordered-scope",
        generated_at="2026-06-14T00:06:30Z",
        budget_limit=4,
    )

    assert proof.proof_state == "Pass"
    assert proof.result_kind == "ExactResult"
    assert proof.projection_values == ("red",)
    assert proof.valid_state_count == 1
    _proof_validator().validate(proof.to_json_dict())


def test_mfidel_domain_requires_atomicity_preservation() -> None:
    with pytest.raises(RuntimeCoreInvariantError) as exc:
        FiniteTruthDomain(
            variable_id="var:mfidel-symbol",
            values=("f[1][1]",),
            source_ref="domain:mfidel-symbol",
            includes_mfidel=True,
            mfidel_atomicity_preserved=False,
        )

    assert "mfidel atomicity must be preserved" in str(exc.value)
    assert exc.type is RuntimeCoreInvariantError
    assert "var:mfidel-symbol" not in str(exc.value)


def test_generated_exact_projection_builds_and_admits_commit_candidate() -> None:
    kernel = _color_kernel()
    candidate_id = "truth-candidate:finite-domain-color"
    proof = kernel.exact_projection(
        variable_id="var:color",
        tenant_id="foundation-local",
        proof_id="kernel-proof:finite-domain-color",
        subject_ref=candidate_id,
        generated_at="2026-06-14T00:06:00Z",
        budget_limit=8,
    )
    truth_candidate = _truth_candidate(
        candidate_id=candidate_id,
        parent_kernel_signature=proof.kernel_signature,
    )

    commit_candidate = build_truth_commit_candidate_from_proof(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        governance_ref="governance:finite-domain-proof-thread",
        trace_ref="trace:finite-domain-color",
        rollback_ref="rollback:finite-domain-color-parent",
        new_kernel_signature="truth-kernel-signature:finite-domain-color-next",
        journal_event_ref="journal:finite-domain-color",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        truth_commit_candidate=commit_candidate,
    )

    _commit_validator().validate(commit_candidate)
    assert commit_candidate["proof_ref"]["proof_hash"] == proof.proof_hash
    assert commit_candidate["truth_admission"]["mutation_allowed"] is True
    assert commit_candidate["journal"]["expected_replay_hash"] == proof.to_json_dict()["replay"]["expected_hash"]
    assert admission.accepted is True
    assert admission.reason == "truth_commit_candidate_admitted"
    assert admission.commit_candidate_id == commit_candidate["commit_candidate_id"]


def test_generated_budget_limited_projection_builds_but_fails_adapter_gate() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:left", values=("a", "b", "c"), source_ref="domain:left"),
            FiniteTruthDomain(variable_id="var:right", values=("x", "y", "z"), source_ref="domain:right"),
        ),
    )
    candidate_id = "truth-candidate:budget-limited"
    proof = kernel.exact_projection(
        variable_id="var:left",
        tenant_id="foundation-local",
        proof_id="kernel-proof:budget-limited-adapter",
        subject_ref=candidate_id,
        generated_at="2026-06-14T00:07:00Z",
        budget_limit=4,
    )
    truth_candidate = _truth_candidate(
        candidate_id=candidate_id,
        parent_kernel_signature=proof.kernel_signature,
    )

    commit_candidate = build_truth_commit_candidate_from_proof(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        governance_ref="governance:finite-domain-proof-thread",
        trace_ref="trace:budget-limited",
        rollback_ref="rollback:budget-limited-parent",
        new_kernel_signature="truth-kernel-signature:budget-limited-next",
        journal_event_ref="journal:budget-limited",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        truth_commit_candidate=commit_candidate,
    )

    _commit_validator().validate(commit_candidate)
    assert commit_candidate["truth_admission"]["mutation_allowed"] is False
    assert commit_candidate["truth_admission"]["proof_state"] == "BudgetUnknown"
    assert commit_candidate["truth_admission"]["result_kind"] == "BudgetExceededResult"
    assert admission.accepted is False
    assert admission.reason == "proof_state_not_pass"
    assert "proof_result_not_exact" in admission.violation_refs
    assert "commit_mutation_not_allowed" in admission.violation_refs


def test_propagation_prunes_impossible_values_without_mutation() -> None:
    kernel = _paired_color_shape_kernel()

    report = kernel.propagate(budget_limit=16)
    payload = report.to_json_dict()

    assert report.proof_state == "Pass"
    assert report.result_kind == "ExactResult"
    assert report.checked_state_count == 9
    assert report.valid_state_count == 2
    assert report.projected_values["var:color"] == ("blue", "red")
    assert report.projected_values["var:shape"] == ("circle", "square")
    assert report.pruned_values["var:color"] == ("green",)
    assert report.pruned_values["var:shape"] == ("triangle",)
    assert report.forced_values == {}
    assert payload["closure_hash"] == report.closure_hash


def test_closure_report_is_idempotent_for_same_kernel_and_budget() -> None:
    kernel = _paired_color_shape_kernel()

    first = kernel.propagate(budget_limit=16)
    second = kernel.propagate(budget_limit=16)

    assert first.closure_hash == second.closure_hash
    assert first.to_json_dict() == second.to_json_dict()
    assert first.kernel_signature == second.kernel_signature
    assert first.projected_values == second.projected_values
    assert first.pruned_values == second.pruned_values
    assert first.checked_state_count == second.checked_state_count


def test_propagation_is_monotonic_when_constraints_are_added() -> None:
    unconstrained = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:color", values=("red", "blue", "green"), source_ref="domain:color"),
        ),
    )
    constrained = _color_kernel()

    broad = unconstrained.propagate(budget_limit=4)
    narrow = constrained.propagate(budget_limit=4)

    assert set(narrow.projected_values["var:color"]).issubset(broad.projected_values["var:color"])
    assert broad.projected_values["var:color"] == ("blue", "green", "red")
    assert narrow.projected_values["var:color"] == ("blue", "red")
    assert broad.pruned_values["var:color"] == ()
    assert narrow.pruned_values["var:color"] == ("green",)


def test_forced_value_from_closure_uses_projection_proof_and_adapter_gate() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:shape", values=("circle", "square"), source_ref="domain:shape"),
        ),
        constraints=(
            FiniteTruthConstraint(
                constraint_id="constraint:shape-circle",
                scope=("var:shape",),
                source_ref="constraint:shape-circle",
                statement="Shape must be circle.",
                allowed_assignments=({"var:shape": "circle"},),
            ),
        ),
    )
    closure = kernel.propagate(budget_limit=4)
    candidate_id = "truth-candidate:forced-shape"
    proof = kernel.exact_projection(
        variable_id="var:shape",
        tenant_id="foundation-local",
        proof_id="kernel-proof:forced-shape",
        subject_ref=candidate_id,
        generated_at="2026-06-14T00:08:00Z",
        budget_limit=4,
    )
    truth_candidate = _truth_candidate(
        candidate_id=candidate_id,
        parent_kernel_signature=proof.kernel_signature,
    )
    truth_candidate["delta"]["affected_variable_ids"] = ["var:shape"]
    truth_candidate["delta"]["affected_constraint_ids"] = ["constraint:shape-circle"]
    truth_candidate["proof_obligations"][0]["obligation_id"] = "proof-obligation:forced-shape"

    commit_candidate = build_truth_commit_candidate_from_proof(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        governance_ref="governance:forced-shape-proof-thread",
        trace_ref="trace:forced-shape",
        rollback_ref="rollback:forced-shape-parent",
        new_kernel_signature="truth-kernel-signature:forced-shape-next",
        journal_event_ref="journal:forced-shape",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        truth_commit_candidate=commit_candidate,
    )

    assert closure.forced_values == {"var:shape": "circle"}
    assert proof.projection_values == ("circle",)
    assert commit_candidate["truth_admission"]["mutation_allowed"] is True
    assert admission.accepted is True
    assert admission.reason == "truth_commit_candidate_admitted"


def test_budget_limited_propagation_has_no_forced_values_or_exact_projection() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:left", values=("a", "b", "c"), source_ref="domain:left"),
            FiniteTruthDomain(variable_id="var:right", values=("x", "y", "z"), source_ref="domain:right"),
        ),
    )

    report = kernel.propagate(budget_limit=4)

    assert report.proof_state == "BudgetUnknown"
    assert report.result_kind == "BudgetExceededResult"
    assert report.checked_state_count == 4
    assert report.valid_state_count == 0
    assert report.projected_values["var:left"] == ()
    assert report.projected_values["var:right"] == ()
    assert report.forced_values == {}


def test_closure_proof_payload_is_schema_valid_and_multistep() -> None:
    kernel = _paired_color_shape_kernel()

    proof = kernel.closure_proof(
        tenant_id="foundation-local",
        proof_id="kernel-proof:paired-closure",
        subject_ref="closure:paired-color-shape",
        generated_at="2026-06-14T00:09:00Z",
        budget_limit=16,
    )
    payload = proof.to_json_dict()

    _proof_validator().validate(payload)
    assert proof.proof_state == "Pass"
    assert proof.result_kind == "ExactResult"
    assert proof.checked_state_count == 9
    assert proof.valid_state_count == 2
    assert payload["proof_kind"] == "ValidityProof"
    assert [step["step_id"] for step in payload["derivation_steps"]] == [
        "step-enumerate-finite-domain",
        "step-apply-finite-constraints",
        "step-build-finite-closure",
        "step-identify-forced-values",
    ]
    assert payload["conclusion"]["supports_truth_mutation"] is True
    assert payload["proof_hash"] == proof.proof_hash


def test_closure_proof_is_deterministic_for_same_kernel_and_request() -> None:
    first_kernel = _paired_color_shape_kernel()
    second_kernel = _paired_color_shape_kernel()

    first = first_kernel.closure_proof(
        tenant_id="foundation-local",
        proof_id="kernel-proof:paired-closure",
        subject_ref="closure:paired-color-shape",
        generated_at="2026-06-14T00:09:00Z",
        budget_limit=16,
    )
    second = second_kernel.closure_proof(
        tenant_id="foundation-local",
        proof_id="kernel-proof:paired-closure",
        subject_ref="closure:paired-color-shape",
        generated_at="2026-06-14T00:09:00Z",
        budget_limit=16,
    )

    assert first.proof_hash == second.proof_hash
    assert first.closure_hash == second.closure_hash
    assert first.to_json_dict() == second.to_json_dict()
    assert first.kernel_signature == second.kernel_signature


def test_exact_closure_proof_builds_and_admits_validity_commit_candidate() -> None:
    kernel = _paired_color_shape_kernel()
    candidate_id = "truth-candidate:paired-closure"
    proof = kernel.closure_proof(
        tenant_id="foundation-local",
        proof_id="kernel-proof:paired-closure-adapter",
        subject_ref=candidate_id,
        generated_at="2026-06-14T00:10:00Z",
        budget_limit=16,
    )
    truth_candidate = _truth_candidate(
        candidate_id=candidate_id,
        parent_kernel_signature=proof.kernel_signature,
        proof_kind="ValidityProof",
    )
    truth_candidate["delta"]["affected_variable_ids"] = ["var:color", "var:shape"]
    truth_candidate["delta"]["affected_constraint_ids"] = ["constraint:paired-color-shape"]

    commit_candidate = build_truth_commit_candidate_from_proof(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        governance_ref="governance:paired-closure-proof-thread",
        trace_ref="trace:paired-closure",
        rollback_ref="rollback:paired-closure-parent",
        new_kernel_signature="truth-kernel-signature:paired-closure-next",
        journal_event_ref="journal:paired-closure",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        truth_commit_candidate=commit_candidate,
    )

    _commit_validator().validate(commit_candidate)
    assert commit_candidate["proof_ref"]["proof_hash"] == proof.proof_hash
    assert commit_candidate["truth_admission"]["mutation_allowed"] is True
    assert admission.accepted is True
    assert admission.reason == "truth_commit_candidate_admitted"
    assert admission.proof_id == proof.to_json_dict()["proof_id"]


def test_budget_limited_closure_proof_builds_but_fails_adapter_gate() -> None:
    kernel = FiniteTruthKernel(
        domains=(
            FiniteTruthDomain(variable_id="var:left", values=("a", "b", "c"), source_ref="domain:left"),
            FiniteTruthDomain(variable_id="var:right", values=("x", "y", "z"), source_ref="domain:right"),
        ),
    )
    candidate_id = "truth-candidate:budget-limited-closure"
    proof = kernel.closure_proof(
        tenant_id="foundation-local",
        proof_id="kernel-proof:budget-limited-closure",
        subject_ref=candidate_id,
        generated_at="2026-06-14T00:11:00Z",
        budget_limit=4,
    )
    truth_candidate = _truth_candidate(
        candidate_id=candidate_id,
        parent_kernel_signature=proof.kernel_signature,
        proof_kind="ValidityProof",
    )

    commit_candidate = build_truth_commit_candidate_from_proof(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        governance_ref="governance:budget-limited-closure-proof-thread",
        trace_ref="trace:budget-limited-closure",
        rollback_ref="rollback:budget-limited-closure-parent",
        new_kernel_signature="truth-kernel-signature:budget-limited-closure-next",
        journal_event_ref="journal:budget-limited-closure",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=truth_candidate,
        kernel_proof=proof.to_json_dict(),
        truth_commit_candidate=commit_candidate,
    )

    _proof_validator().validate(proof.to_json_dict())
    _commit_validator().validate(commit_candidate)
    assert proof.proof_state == "BudgetUnknown"
    assert proof.result_kind == "BudgetExceededResult"
    assert commit_candidate["truth_admission"]["mutation_allowed"] is False
    assert admission.accepted is False
    assert admission.reason == "proof_state_not_pass"
    assert "proof_limitations_block_truth_mutation" in admission.violation_refs
