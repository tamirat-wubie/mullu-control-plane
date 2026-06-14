"""Purpose: schema-bound Mullu Truth Kernel admission adapter.
Governance scope: truth candidate, kernel proof, and truth commit candidate
    admission before any truth-state mutation authority is granted.
Dependencies: Python standard-library mappings and runtime invariant helpers.
Test contract: tests/test_truth_kernel_admission.py.
Invariants:
  - The adapter is pure and does not mutate truth state.
  - Truth mutation requires exact proof, deterministic replay, and governance,
    trace, rollback, and journal bindings.
  - Approximate, bounded, unknown, budget-limited, and contradicted results
    cannot be promoted into truth.
  - Mfidel atomicity must be preserved whenever a truth delta includes Mfidel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


KERNEL_PROOF_SCHEMA_REF = "schemas/kernel_proof.schema.json"
MUTATING_COMMIT_STATUSES = frozenset({"proposed", "validated", "approved"})
SANDBOX_ISOLATION_WITNESS_REF = "witness:sandbox-isolated"


@dataclass(frozen=True, slots=True)
class TruthKernelAdmission:
    """Admission decision for one truth commit candidate."""

    accepted: bool
    reason: str
    candidate_id: str = ""
    proof_id: str = ""
    commit_candidate_id: str = ""
    admission_id: str = ""
    reason_refs: tuple[str, ...] = ()
    violation_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_refs", tuple(self.reason_refs))
        object.__setattr__(self, "violation_refs", tuple(self.violation_refs))


def admit_truth_commit_candidate(
    *,
    truth_candidate: Mapping[str, Any],
    kernel_proof: Mapping[str, Any],
    truth_commit_candidate: Mapping[str, Any],
) -> TruthKernelAdmission:
    """Admit a proof-bound truth commit candidate without mutating state."""
    candidate = _mapping(truth_candidate)
    proof = _mapping(kernel_proof)
    commit = _mapping(truth_commit_candidate)
    candidate_id = _text(candidate, "candidate_id")
    proof_id = _text(proof, "proof_id")
    commit_candidate_id = _text(commit, "commit_candidate_id")
    violations = tuple(
        _admission_violations(
            truth_candidate=truth_candidate,
            kernel_proof=kernel_proof,
            truth_commit_candidate=truth_commit_candidate,
        )
    )
    if violations:
        return TruthKernelAdmission(
            accepted=False,
            reason=violations[0],
            candidate_id=candidate_id,
            proof_id=proof_id,
            commit_candidate_id=commit_candidate_id,
            violation_refs=violations,
        )

    proof_ref = _mapping(commit.get("proof_ref"))
    truth_admission = _mapping(commit.get("truth_admission"))
    admission_id = stable_identifier(
        "truth-kernel-admission",
        {
            "candidate_id": candidate_id,
            "candidate_hash": _text(candidate, "candidate_hash"),
            "proof_id": proof_id,
            "proof_hash": _text(proof_ref, "proof_hash"),
            "commit_candidate_id": commit_candidate_id,
            "commit_hash": _text(commit, "commit_hash"),
            "new_kernel_signature": _text(commit, "new_kernel_signature"),
        },
    )
    return TruthKernelAdmission(
        accepted=True,
        reason="truth_commit_candidate_admitted",
        candidate_id=candidate_id,
        proof_id=proof_id,
        commit_candidate_id=commit_candidate_id,
        admission_id=admission_id,
        reason_refs=_string_tuple(truth_admission.get("admission_reason_refs")),
    )


def build_truth_commit_candidate_from_proof(
    *,
    truth_candidate: Mapping[str, Any],
    kernel_proof: Mapping[str, Any],
    governance_ref: str,
    trace_ref: str,
    rollback_ref: str,
    new_kernel_signature: str,
    journal_event_ref: str,
    status: str = "proposed",
) -> dict[str, Any]:
    """Build a schema-shaped truth commit candidate from one proof payload.

    The builder does not admit, commit, or mutate truth state. Call
    `admit_truth_commit_candidate` with the returned mapping to apply the
    adapter gate.
    """
    candidate = _mapping(truth_candidate)
    proof = _mapping(kernel_proof)
    governance_ref = ensure_non_empty_text("governance_ref", governance_ref)
    trace_ref = ensure_non_empty_text("trace_ref", trace_ref)
    rollback_ref = ensure_non_empty_text("rollback_ref", rollback_ref)
    new_kernel_signature = ensure_non_empty_text("new_kernel_signature", new_kernel_signature)
    journal_event_ref = ensure_non_empty_text("journal_event_ref", journal_event_ref)
    status = ensure_non_empty_text("status", status)

    proof_replay = _mapping(proof.get("replay"))
    proof_conclusion = _mapping(proof.get("conclusion"))
    mutation_allowed = (
        _text(proof, "proof_state") == "Pass"
        and _text(proof, "result_kind") == "ExactResult"
        and _bool(proof_conclusion, "supports_truth_mutation") is True
        and _text(proof_conclusion, "required_next_action") == "commit_candidate"
        and _bool(proof_replay, "deterministic") is True
        and not _string_tuple(proof.get("limitations"))
    )
    payload_without_hash = {
        "commit_candidate_id": stable_identifier(
            "truth-commit",
            {
                "candidate_id": _text(candidate, "candidate_id"),
                "proof_id": _text(proof, "proof_id"),
                "new_kernel_signature": new_kernel_signature,
            },
        ),
        "tenant_id": _text(candidate, "tenant_id"),
        "candidate_id": _text(candidate, "candidate_id"),
        "delta_kind": _text(_mapping(candidate.get("delta")), "delta_kind"),
        "parent_kernel_signature": _text(candidate, "parent_kernel_signature"),
        "new_kernel_signature": new_kernel_signature,
        "proof_ref": {
            "proof_id": _text(proof, "proof_id"),
            "proof_hash": _text(proof, "proof_hash"),
            "proof_schema_ref": KERNEL_PROOF_SCHEMA_REF,
        },
        "governance_ref": governance_ref,
        "trace_ref": trace_ref,
        "rollback_ref": rollback_ref,
        "truth_admission": {
            "proof_state": _text(proof, "proof_state"),
            "result_kind": _text(proof, "result_kind"),
            "mutation_allowed": mutation_allowed,
            "admission_reason_refs": _commit_reason_refs(mutation_allowed),
        },
        "journal": {
            "journal_event_ref": journal_event_ref,
            "replay_required": True,
            "replay_mode": _text(proof_replay, "replay_mode"),
            "expected_replay_hash": _text(proof_replay, "expected_hash"),
        },
        "status": status,
    }
    return {
        **payload_without_hash,
        "commit_hash": stable_identifier("truth-commit-candidate", payload_without_hash),
    }


def _admission_violations(
    *,
    truth_candidate: Mapping[str, Any],
    kernel_proof: Mapping[str, Any],
    truth_commit_candidate: Mapping[str, Any],
) -> tuple[str, ...]:
    violations: list[str] = []
    if not isinstance(truth_candidate, Mapping):
        violations.append("truth_candidate_must_be_mapping")
    if not isinstance(kernel_proof, Mapping):
        violations.append("kernel_proof_must_be_mapping")
    if not isinstance(truth_commit_candidate, Mapping):
        violations.append("truth_commit_candidate_must_be_mapping")
    if violations:
        return tuple(violations)

    candidate = _mapping(truth_candidate)
    proof = _mapping(kernel_proof)
    commit = _mapping(truth_commit_candidate)
    candidate_delta = _mapping(candidate.get("delta"))
    boundary = _mapping(candidate.get("admission_boundary"))
    proof_conclusion = _mapping(proof.get("conclusion"))
    proof_replay = _mapping(proof.get("replay"))
    proof_budget = _mapping(proof.get("budget"))
    proof_ref = _mapping(commit.get("proof_ref"))
    truth_admission = _mapping(commit.get("truth_admission"))
    journal = _mapping(commit.get("journal"))

    violations.extend(_required_text(candidate, ("candidate_id", "tenant_id", "parent_kernel_signature")))
    violations.extend(_required_text(proof, ("proof_id", "tenant_id", "proof_hash", "kernel_signature", "subject_ref")))
    violations.extend(
        _required_text(
            commit,
            (
                "commit_candidate_id",
                "tenant_id",
                "candidate_id",
                "parent_kernel_signature",
                "new_kernel_signature",
                "governance_ref",
                "trace_ref",
                "rollback_ref",
                "commit_hash",
            ),
        )
    )

    candidate_id = _text(candidate, "candidate_id")
    candidate_tenant = _text(candidate, "tenant_id")
    proof_tenant = _text(proof, "tenant_id")
    commit_tenant = _text(commit, "tenant_id")
    if proof_tenant and candidate_tenant and proof_tenant != candidate_tenant:
        violations.append("proof_tenant_mismatch")
    if commit_tenant and candidate_tenant and commit_tenant != candidate_tenant:
        violations.append("commit_tenant_mismatch")
    if _text(proof, "subject_ref") and _text(proof, "subject_ref") != candidate_id:
        violations.append("proof_subject_ref_mismatch")
    if _text(commit, "candidate_id") and _text(commit, "candidate_id") != candidate_id:
        violations.append("commit_candidate_ref_mismatch")

    candidate_kind = _text(candidate, "candidate_kind")
    delta_kind = _text(candidate_delta, "delta_kind")
    commit_delta_kind = _text(commit, "delta_kind")
    if candidate_kind and delta_kind and candidate_kind != delta_kind:
        violations.append("candidate_delta_kind_mismatch")
    if commit_delta_kind and delta_kind and commit_delta_kind != delta_kind:
        violations.append("commit_delta_kind_mismatch")

    parent_signature = _text(candidate, "parent_kernel_signature")
    proof_signature = _text(proof, "kernel_signature")
    commit_parent_signature = _text(commit, "parent_kernel_signature")
    new_signature = _text(commit, "new_kernel_signature")
    if proof_signature and parent_signature and proof_signature != parent_signature:
        violations.append("proof_kernel_signature_mismatch")
    if commit_parent_signature and parent_signature and commit_parent_signature != parent_signature:
        violations.append("commit_parent_kernel_signature_mismatch")
    if new_signature and parent_signature and new_signature == parent_signature:
        violations.append("new_kernel_signature_must_change")

    if _bool(candidate_delta, "includes_mfidel") is True and _bool(candidate_delta, "mfidel_atomicity_preserved") is not True:
        violations.append("mfidel_atomicity_not_preserved")
    if _bool(boundary, "can_mutate_truth") is not True:
        violations.append("candidate_boundary_blocks_truth_mutation")
    if _text(boundary, "result_authority") != "exact_required":
        violations.append("candidate_exact_authority_required")
    if _bool(boundary, "requires_exact_result") is not True:
        violations.append("candidate_exact_result_required")
    if _bool(boundary, "requires_governance_ref") is not True:
        violations.append("candidate_governance_ref_required")
    if _bool(boundary, "requires_trace_ref") is not True:
        violations.append("candidate_trace_ref_required")
    if _bool(boundary, "requires_sandbox_isolation") is not True:
        violations.append("candidate_sandbox_isolation_required")
    elif SANDBOX_ISOLATION_WITNESS_REF not in _string_tuple(proof.get("witness_refs")):
        violations.append("sandbox_isolation_witness_required")

    required_proof_kinds = _required_mutation_proof_kinds(candidate.get("proof_obligations"))
    if not required_proof_kinds:
        violations.append("mutation_proof_obligation_required")
    elif _text(proof, "proof_kind") not in required_proof_kinds:
        violations.append("proof_kind_not_required_for_mutation")

    if _text(proof, "proof_state") != "Pass":
        violations.append("proof_state_not_pass")
    if _text(proof, "result_kind") != "ExactResult":
        violations.append("proof_result_not_exact")
    if _bool(proof_conclusion, "supports_truth_mutation") is not True:
        violations.append("proof_does_not_support_truth_mutation")
    if _text(proof_conclusion, "required_next_action") != "commit_candidate":
        violations.append("proof_next_action_not_commit_candidate")
    if _bool(proof_replay, "deterministic") is not True:
        violations.append("proof_replay_not_deterministic")
    if _string_tuple(proof.get("limitations")):
        violations.append("proof_limitations_block_truth_mutation")

    limit = proof_budget.get("limit")
    used = proof_budget.get("used")
    if not isinstance(limit, int) or not isinstance(used, int):
        violations.append("proof_budget_required")
    elif used > limit:
        violations.append("proof_budget_exceeded")

    if _text(proof_ref, "proof_id") != _text(proof, "proof_id"):
        violations.append("proof_ref_id_mismatch")
    if _text(proof_ref, "proof_hash") != _text(proof, "proof_hash"):
        violations.append("proof_ref_hash_mismatch")
    if _text(proof_ref, "proof_schema_ref") != KERNEL_PROOF_SCHEMA_REF:
        violations.append("proof_schema_ref_mismatch")

    if _bool(truth_admission, "mutation_allowed") is not True:
        violations.append("commit_mutation_not_allowed")
    if _text(truth_admission, "proof_state") != _text(proof, "proof_state"):
        violations.append("commit_proof_state_mismatch")
    if _text(truth_admission, "result_kind") != _text(proof, "result_kind"):
        violations.append("commit_result_kind_mismatch")
    if not _string_tuple(truth_admission.get("admission_reason_refs")):
        violations.append("commit_admission_reason_refs_required")

    if _bool(journal, "replay_required") is not True:
        violations.append("journal_replay_required")
    if _text(journal, "replay_mode") != _text(proof_replay, "replay_mode"):
        violations.append("journal_replay_mode_mismatch")
    if not _text(journal, "expected_replay_hash"):
        violations.append("journal_expected_replay_hash_required")
    elif _text(journal, "expected_replay_hash") != _text(proof_replay, "expected_hash"):
        violations.append("journal_expected_replay_hash_mismatch")

    if _text(commit, "status") not in MUTATING_COMMIT_STATUSES:
        violations.append("commit_status_not_admissible_for_mutation")
    return tuple(dict.fromkeys(violations))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(mapping: Mapping[str, Any], field_name: str) -> str:
    value = mapping.get(field_name)
    return value.strip() if isinstance(value, str) else ""


def _bool(mapping: Mapping[str, Any], field_name: str) -> bool | None:
    value = mapping.get(field_name)
    return value if isinstance(value, bool) else None


def _required_text(mapping: Mapping[str, Any], field_names: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"{field_name}_required" for field_name in field_names if not _text(mapping, field_name))


def _required_mutation_proof_kinds(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    proof_kinds: list[str] = []
    for item in value:
        obligation = _mapping(item)
        if _bool(obligation, "required_for_mutation") is True:
            proof_kind = _text(obligation, "proof_kind")
            if proof_kind:
                proof_kinds.append(proof_kind)
    return tuple(dict.fromkeys(proof_kinds))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(dict.fromkeys(item.strip() for item in value if isinstance(item, str) and item.strip()))


def _commit_reason_refs(mutation_allowed: bool) -> list[str]:
    if mutation_allowed:
        return [
            "reason:exact-proof-pass",
            "reason:deterministic-replay-present",
            "reason:governance-ref-present",
            "reason:trace-ref-present",
            "reason:rollback-ref-present",
        ]
    return ["reason:truth-mutation-not-admitted"]
