"""Purpose: local finite-domain proof thread for the Mullu Truth Kernel.
Governance scope: deterministic domain membership, constraint evaluation,
    exact projection proof emission, contradiction reporting, and budget-bound
    non-promotion before truth-state mutation.
Dependencies: Python standard-library dataclasses, itertools, and runtime
    invariant helpers.
Test contract: tests/test_truth_kernel_finite_domain.py.
Invariants:
  - Finite-domain proofs are pure and do not mutate truth state.
  - Constraint checks are total over declared finite domains.
  - Budget exhaustion cannot produce an exact truth result.
  - Mfidel-bearing domains must preserve atomicity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


Assignment = Mapping[str, str]
SANDBOX_ISOLATION_WITNESS_REF = "witness:sandbox-isolated"


@dataclass(frozen=True, slots=True)
class FiniteTruthDomain:
    """Finite variable domain admitted for local proof threading."""

    variable_id: str
    values: tuple[str, ...]
    source_ref: str
    includes_mfidel: bool = False
    mfidel_atomicity_preserved: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "variable_id", ensure_non_empty_text("variable_id", self.variable_id))
        object.__setattr__(self, "source_ref", ensure_non_empty_text("source_ref", self.source_ref))
        values = _normalize_text_tuple(self.values, "values")
        if len(values) != len(set(values)):
            raise RuntimeCoreInvariantError("domain values must be unique")
        if self.includes_mfidel and not self.mfidel_atomicity_preserved:
            raise RuntimeCoreInvariantError("mfidel atomicity must be preserved")
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class FiniteTruthConstraint:
    """Finite allowed/forbidden assignment constraint."""

    constraint_id: str
    scope: tuple[str, ...]
    source_ref: str
    statement: str
    allowed_assignments: tuple[Assignment, ...] = ()
    forbidden_assignments: tuple[Assignment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", ensure_non_empty_text("constraint_id", self.constraint_id))
        object.__setattr__(self, "source_ref", ensure_non_empty_text("source_ref", self.source_ref))
        object.__setattr__(self, "statement", ensure_non_empty_text("statement", self.statement))
        scope = _normalize_text_tuple(self.scope, "scope")
        if len(scope) != len(set(scope)):
            raise RuntimeCoreInvariantError("constraint scope variable ids must be unique")
        object.__setattr__(self, "scope", scope)
        if not self.allowed_assignments and not self.forbidden_assignments:
            raise RuntimeCoreInvariantError("constraint must declare allowed or forbidden assignments")
        object.__setattr__(self, "allowed_assignments", _normalize_assignments(self.allowed_assignments))
        object.__setattr__(self, "forbidden_assignments", _normalize_assignments(self.forbidden_assignments))


@dataclass(frozen=True, slots=True)
class FiniteProjectionProof:
    """Projection proof plus schema-compatible kernel proof payload."""

    proof_state: str
    result_kind: str
    projection_values: tuple[str, ...]
    checked_state_count: int
    valid_state_count: int
    kernel_signature: str
    proof_hash: str
    payload: Mapping[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a defensive JSON-compatible copy of the proof payload."""
        return _json_copy(self.payload)


@dataclass(frozen=True, slots=True)
class FiniteClosureProof:
    """Closure proof plus schema-compatible kernel proof payload."""

    proof_state: str
    result_kind: str
    closure_hash: str
    checked_state_count: int
    valid_state_count: int
    kernel_signature: str
    proof_hash: str
    payload: Mapping[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a defensive JSON-compatible copy of the proof payload."""
        return _json_copy(self.payload)


@dataclass(frozen=True, slots=True)
class FinitePropagationReport:
    """Deterministic closure and propagation read model for finite domains."""

    proof_state: str
    result_kind: str
    projected_values: Mapping[str, tuple[str, ...]]
    pruned_values: Mapping[str, tuple[str, ...]]
    forced_values: Mapping[str, str]
    checked_state_count: int
    valid_state_count: int
    kernel_signature: str
    closure_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "projected_values",
            {key: tuple(values) for key, values in self.projected_values.items()},
        )
        object.__setattr__(
            self,
            "pruned_values",
            {key: tuple(values) for key, values in self.pruned_values.items()},
        )
        object.__setattr__(self, "forced_values", dict(self.forced_values))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible propagation report."""
        return {
            "proof_state": self.proof_state,
            "result_kind": self.result_kind,
            "projected_values": {
                key: list(values) for key, values in sorted(self.projected_values.items())
            },
            "pruned_values": {
                key: list(values) for key, values in sorted(self.pruned_values.items())
            },
            "forced_values": {key: self.forced_values[key] for key in sorted(self.forced_values)},
            "checked_state_count": self.checked_state_count,
            "valid_state_count": self.valid_state_count,
            "kernel_signature": self.kernel_signature,
            "closure_hash": self.closure_hash,
        }


class FiniteTruthKernel:
    """Pure finite-domain kernel for local exact proof threading."""

    def __init__(
        self,
        *,
        domains: Sequence[FiniteTruthDomain],
        constraints: Sequence[FiniteTruthConstraint] = (),
    ) -> None:
        normalized_domains = tuple(domains)
        normalized_constraints = tuple(constraints)
        if not normalized_domains:
            raise RuntimeCoreInvariantError("at least one finite truth domain is required")
        self._domains = {domain.variable_id: domain for domain in normalized_domains}
        if len(self._domains) != len(normalized_domains):
            raise RuntimeCoreInvariantError("domain variable ids must be unique")
        self._constraints = normalized_constraints
        self._validate_constraints()
        self._kernel_signature = stable_identifier(
            "truth-kernel-signature",
            {
                "domains": [
                    {
                        "variable_id": domain.variable_id,
                        "values": list(domain.values),
                        "source_ref": domain.source_ref,
                        "includes_mfidel": domain.includes_mfidel,
                        "mfidel_atomicity_preserved": domain.mfidel_atomicity_preserved,
                    }
                    for domain in sorted(self._domains.values(), key=lambda item: item.variable_id)
                ],
                "constraints": [_constraint_payload(constraint) for constraint in self._constraints],
            },
        )

    @property
    def kernel_signature(self) -> str:
        """Return the deterministic signature for domains and constraints."""
        return self._kernel_signature

    def exact_projection(
        self,
        *,
        variable_id: str,
        tenant_id: str,
        proof_id: str,
        subject_ref: str,
        generated_at: str,
        budget_limit: int,
    ) -> FiniteProjectionProof:
        """Project possible values for one variable under finite constraints."""
        variable_id = ensure_non_empty_text("variable_id", variable_id)
        tenant_id = ensure_non_empty_text("tenant_id", tenant_id)
        proof_id = ensure_non_empty_text("proof_id", proof_id)
        subject_ref = ensure_non_empty_text("subject_ref", subject_ref)
        generated_at = ensure_non_empty_text("generated_at", generated_at)
        if variable_id not in self._domains:
            raise RuntimeCoreInvariantError("projection variable must be declared")
        if budget_limit < 0:
            raise RuntimeCoreInvariantError("budget limit must be non-negative")

        total_state_count = self._total_state_count()
        if total_state_count > budget_limit:
            return self._build_projection_proof(
                variable_id=variable_id,
                tenant_id=tenant_id,
                proof_id=proof_id,
                subject_ref=subject_ref,
                generated_at=generated_at,
                budget_limit=budget_limit,
                checked_state_count=budget_limit,
                valid_states=(),
                proof_state="BudgetUnknown",
                result_kind="BudgetExceededResult",
                limitations=("budget_exceeded_before_exact_projection",),
            )

        checked_state_count = 0
        valid_states: list[dict[str, str]] = []
        for state in self._candidate_states():
            checked_state_count += 1
            if self._satisfies_constraints(state):
                valid_states.append(state)

        if not valid_states:
            return self._build_projection_proof(
                variable_id=variable_id,
                tenant_id=tenant_id,
                proof_id=proof_id,
                subject_ref=subject_ref,
                generated_at=generated_at,
                budget_limit=budget_limit,
                checked_state_count=checked_state_count,
                valid_states=(),
                proof_state="Pass",
                result_kind="ContradictionResult",
                limitations=(),
            )

        return self._build_projection_proof(
            variable_id=variable_id,
            tenant_id=tenant_id,
            proof_id=proof_id,
            subject_ref=subject_ref,
            generated_at=generated_at,
            budget_limit=budget_limit,
            checked_state_count=checked_state_count,
            valid_states=tuple(valid_states),
            proof_state="Pass",
            result_kind="ExactResult",
            limitations=(),
        )

    def propagate(self, *, budget_limit: int) -> FinitePropagationReport:
        """Return exact finite-domain propagation when the budget permits it."""
        if budget_limit < 0:
            raise RuntimeCoreInvariantError("budget limit must be non-negative")
        total_state_count = self._total_state_count()
        if total_state_count > budget_limit:
            return self._build_propagation_report(
                checked_state_count=budget_limit,
                valid_states=(),
                proof_state="BudgetUnknown",
                result_kind="BudgetExceededResult",
            )

        checked_state_count = 0
        valid_states: list[dict[str, str]] = []
        for state in self._candidate_states():
            checked_state_count += 1
            if self._satisfies_constraints(state):
                valid_states.append(state)

        if not valid_states:
            return self._build_propagation_report(
                checked_state_count=checked_state_count,
                valid_states=(),
                proof_state="Pass",
                result_kind="ContradictionResult",
            )
        return self._build_propagation_report(
            checked_state_count=checked_state_count,
            valid_states=tuple(valid_states),
            proof_state="Pass",
            result_kind="ExactResult",
        )

    def closure_proof(
        self,
        *,
        tenant_id: str,
        proof_id: str,
        subject_ref: str,
        generated_at: str,
        budget_limit: int,
    ) -> FiniteClosureProof:
        """Emit a schema-compatible multi-step finite-closure proof payload."""
        tenant_id = ensure_non_empty_text("tenant_id", tenant_id)
        proof_id = ensure_non_empty_text("proof_id", proof_id)
        subject_ref = ensure_non_empty_text("subject_ref", subject_ref)
        generated_at = ensure_non_empty_text("generated_at", generated_at)
        report = self.propagate(budget_limit=budget_limit)
        limitations = _closure_limitations(report.result_kind)
        supports_truth_mutation = report.result_kind == "ExactResult"
        replay_basis = {
            "kernel_signature": self.kernel_signature,
            "closure_hash": report.closure_hash,
            "result_kind": report.result_kind,
            "checked_state_count": report.checked_state_count,
            "valid_state_count": report.valid_state_count,
            "limitations": list(limitations),
        }
        payload_without_hash = {
            "proof_id": proof_id,
            "tenant_id": tenant_id,
            "proof_kind": "ValidityProof",
            "proof_state": report.proof_state,
            "result_kind": report.result_kind,
            "kernel_signature": self.kernel_signature,
            "subject_ref": subject_ref,
            "generated_at": generated_at,
            "premises": self._premises(),
            "derivation_steps": self._closure_derivation_steps(report),
            "conclusion": {
                "statement": _closure_statement(report),
                "supports_truth_mutation": supports_truth_mutation,
                "required_next_action": "commit_candidate" if supports_truth_mutation else "plan_sensing",
            },
            "witness_refs": _closure_witness_refs(report, limitations),
            "replay": {
                "replay_mode": "observation_only",
                "deterministic": True,
                "source_hash": self.kernel_signature,
                "expected_hash": stable_identifier("truth-kernel-closure-replay", replay_basis),
                "reason_codes": list(limitations),
            },
            "budget": {
                "budget_id": f"budget:{proof_id}",
                "limit": budget_limit,
                "used": report.checked_state_count,
                "unit": "checks",
            },
            "limitations": list(limitations),
        }
        proof_hash = stable_identifier("kernel-closure-proof", payload_without_hash)
        payload = {**payload_without_hash, "proof_hash": proof_hash}
        return FiniteClosureProof(
            proof_state=report.proof_state,
            result_kind=report.result_kind,
            closure_hash=report.closure_hash,
            checked_state_count=report.checked_state_count,
            valid_state_count=report.valid_state_count,
            kernel_signature=self.kernel_signature,
            proof_hash=proof_hash,
            payload=payload,
        )

    def _validate_constraints(self) -> None:
        for constraint in self._constraints:
            for variable_id in constraint.scope:
                if variable_id not in self._domains:
                    raise RuntimeCoreInvariantError("constraint scope references an unknown domain")
            for assignment in (*constraint.allowed_assignments, *constraint.forbidden_assignments):
                if set(assignment) != set(constraint.scope):
                    raise RuntimeCoreInvariantError("constraint assignment scope must match constraint scope")
                for variable_id, value in assignment.items():
                    if value not in self._domains[variable_id].values:
                        raise RuntimeCoreInvariantError("constraint assignment value must exist in domain")

    def _total_state_count(self) -> int:
        total = 1
        for domain in self._domains.values():
            total *= len(domain.values)
        return total

    def _candidate_states(self) -> tuple[dict[str, str], ...]:
        variable_ids = tuple(sorted(self._domains))
        value_sets = tuple(self._domains[variable_id].values for variable_id in variable_ids)
        return tuple(dict(zip(variable_ids, values, strict=True)) for values in product(*value_sets))

    def _satisfies_constraints(self, state: Mapping[str, str]) -> bool:
        return all(_constraint_satisfied(constraint, state) for constraint in self._constraints)

    def _build_propagation_report(
        self,
        *,
        checked_state_count: int,
        valid_states: Sequence[Mapping[str, str]],
        proof_state: str,
        result_kind: str,
    ) -> FinitePropagationReport:
        projected_values: dict[str, tuple[str, ...]] = {}
        pruned_values: dict[str, tuple[str, ...]] = {}
        forced_values: dict[str, str] = {}
        for variable_id, domain in sorted(self._domains.items()):
            projected = tuple(sorted({state[variable_id] for state in valid_states if variable_id in state}))
            pruned = tuple(value for value in domain.values if value not in projected)
            projected_values[variable_id] = projected
            pruned_values[variable_id] = pruned
            if len(projected) == 1 and result_kind == "ExactResult":
                forced_values[variable_id] = projected[0]

        closure_payload = {
            "kernel_signature": self.kernel_signature,
            "proof_state": proof_state,
            "result_kind": result_kind,
            "projected_values": {key: list(projected_values[key]) for key in sorted(projected_values)},
            "pruned_values": {key: list(pruned_values[key]) for key in sorted(pruned_values)},
            "forced_values": {key: forced_values[key] for key in sorted(forced_values)},
            "checked_state_count": checked_state_count,
            "valid_state_count": len(valid_states),
        }
        return FinitePropagationReport(
            proof_state=proof_state,
            result_kind=result_kind,
            projected_values=projected_values,
            pruned_values=pruned_values,
            forced_values=forced_values,
            checked_state_count=checked_state_count,
            valid_state_count=len(valid_states),
            kernel_signature=self.kernel_signature,
            closure_hash=stable_identifier("truth-kernel-closure", closure_payload),
        )

    def _build_projection_proof(
        self,
        *,
        variable_id: str,
        tenant_id: str,
        proof_id: str,
        subject_ref: str,
        generated_at: str,
        budget_limit: int,
        checked_state_count: int,
        valid_states: Sequence[Mapping[str, str]],
        proof_state: str,
        result_kind: str,
        limitations: tuple[str, ...],
    ) -> FiniteProjectionProof:
        projection_values = tuple(
            sorted({state[variable_id] for state in valid_states if variable_id in state})
        )
        supports_truth_mutation = result_kind == "ExactResult"
        replay_basis = {
            "kernel_signature": self.kernel_signature,
            "variable_id": variable_id,
            "projection_values": list(projection_values),
            "valid_state_count": len(valid_states),
            "checked_state_count": checked_state_count,
            "result_kind": result_kind,
            "limitations": list(limitations),
        }
        payload_without_hash = {
            "proof_id": proof_id,
            "tenant_id": tenant_id,
            "proof_kind": "ProjectionProof",
            "proof_state": proof_state,
            "result_kind": result_kind,
            "kernel_signature": self.kernel_signature,
            "subject_ref": subject_ref,
            "generated_at": generated_at,
            "premises": self._premises(),
            "derivation_steps": self._derivation_steps(
                variable_id=variable_id,
                checked_state_count=checked_state_count,
                projection_values=projection_values,
                result_kind=result_kind,
            ),
            "conclusion": {
                "statement": _projection_statement(
                    variable_id=variable_id,
                    projection_values=projection_values,
                    result_kind=result_kind,
                ),
                "supports_truth_mutation": supports_truth_mutation,
                "required_next_action": "commit_candidate" if supports_truth_mutation else "plan_sensing",
            },
            "witness_refs": _witness_refs(valid_states, limitations),
            "replay": {
                "replay_mode": "observation_only",
                "deterministic": True,
                "source_hash": self.kernel_signature,
                "expected_hash": stable_identifier("truth-kernel-replay", replay_basis),
                "reason_codes": list(limitations),
            },
            "budget": {
                "budget_id": f"budget:{proof_id}",
                "limit": budget_limit,
                "used": checked_state_count,
                "unit": "checks",
            },
            "limitations": list(limitations),
        }
        proof_hash = stable_identifier("kernel-proof", payload_without_hash)
        payload = {**payload_without_hash, "proof_hash": proof_hash}
        return FiniteProjectionProof(
            proof_state=proof_state,
            result_kind=result_kind,
            projection_values=projection_values,
            checked_state_count=checked_state_count,
            valid_state_count=len(valid_states),
            kernel_signature=self.kernel_signature,
            proof_hash=proof_hash,
            payload=payload,
        )

    def _premises(self) -> list[dict[str, str]]:
        premises = [
            {
                "premise_id": f"premise-domain:{domain.variable_id}",
                "premise_kind": "domain",
                "source_ref": domain.source_ref,
                "statement": f"{domain.variable_id} has {len(domain.values)} declared finite values.",
            }
            for domain in sorted(self._domains.values(), key=lambda item: item.variable_id)
        ]
        premises.extend(
            {
                "premise_id": f"premise-constraint:{constraint.constraint_id}",
                "premise_kind": "constraint",
                "source_ref": constraint.source_ref,
                "statement": constraint.statement,
            }
            for constraint in self._constraints
        )
        return premises

    def _derivation_steps(
        self,
        *,
        variable_id: str,
        checked_state_count: int,
        projection_values: tuple[str, ...],
        result_kind: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "step_id": "step-enumerate-finite-domain",
                "rule_ref": "rule:finite-domain-enumeration",
                "input_refs": [f"premise-domain:{domain.variable_id}" for domain in self._domains.values()],
                "output_statement": f"Enumerated {checked_state_count} candidate states within declared budget.",
            },
            {
                "step_id": "step-apply-finite-constraints",
                "rule_ref": "rule:total-finite-constraint-check",
                "input_refs": [
                    *(f"premise-constraint:{constraint.constraint_id}" for constraint in self._constraints),
                    "step-enumerate-finite-domain",
                ],
                "output_statement": f"Constraint evaluation produced {result_kind}.",
            },
            {
                "step_id": "step-project-variable",
                "rule_ref": "rule:exact-finite-projection",
                "input_refs": ["step-apply-finite-constraints"],
                "output_statement": f"{variable_id} projects to {list(projection_values)}.",
            },
        ]

    def _closure_derivation_steps(self, report: FinitePropagationReport) -> list[dict[str, Any]]:
        return [
            {
                "step_id": "step-enumerate-finite-domain",
                "rule_ref": "rule:finite-domain-enumeration",
                "input_refs": [f"premise-domain:{domain.variable_id}" for domain in self._domains.values()],
                "output_statement": f"Enumerated {report.checked_state_count} candidate states within declared budget.",
            },
            {
                "step_id": "step-apply-finite-constraints",
                "rule_ref": "rule:total-finite-constraint-check",
                "input_refs": [
                    *(f"premise-constraint:{constraint.constraint_id}" for constraint in self._constraints),
                    "step-enumerate-finite-domain",
                ],
                "output_statement": f"Constraint evaluation produced {report.valid_state_count} valid states.",
            },
            {
                "step_id": "step-build-finite-closure",
                "rule_ref": "rule:finite-closure-projection",
                "input_refs": ["step-apply-finite-constraints"],
                "output_statement": f"Closure hash {report.closure_hash} was derived from projected and pruned values.",
            },
            {
                "step_id": "step-identify-forced-values",
                "rule_ref": "rule:forced-value-uniqueness",
                "input_refs": ["step-build-finite-closure"],
                "output_statement": f"Forced values are {dict(report.forced_values)}.",
            },
        ]


def _constraint_satisfied(constraint: FiniteTruthConstraint, state: Mapping[str, str]) -> bool:
    scoped = {variable_id: state[variable_id] for variable_id in constraint.scope}
    if constraint.allowed_assignments and scoped not in constraint.allowed_assignments:
        return False
    if scoped in constraint.forbidden_assignments:
        return False
    return True


def _projection_statement(
    *,
    variable_id: str,
    projection_values: tuple[str, ...],
    result_kind: str,
) -> str:
    if result_kind == "BudgetExceededResult":
        return f"Budget ended before exact projection for {variable_id} could be proven."
    if result_kind == "ContradictionResult":
        return f"No valid finite-domain state remains for {variable_id}."
    return f"Exact projection for {variable_id} is {list(projection_values)}."


def _closure_limitations(result_kind: str) -> tuple[str, ...]:
    if result_kind == "BudgetExceededResult":
        return ("budget_exceeded_before_exact_closure",)
    return ()


def _closure_statement(report: FinitePropagationReport) -> str:
    if report.result_kind == "BudgetExceededResult":
        return "Budget ended before exact finite closure could be proven."
    if report.result_kind == "ContradictionResult":
        return "Finite closure found no valid state under declared constraints."
    return f"Exact finite closure has {report.valid_state_count} valid states."


def _witness_refs(valid_states: Sequence[Mapping[str, str]], limitations: tuple[str, ...]) -> list[str]:
    if limitations:
        return [SANDBOX_ISOLATION_WITNESS_REF, f"limitation:{limitations[0]}"]
    if not valid_states:
        return [SANDBOX_ISOLATION_WITNESS_REF, "witness:no-valid-state"]
    return [
        SANDBOX_ISOLATION_WITNESS_REF,
        *(
            stable_identifier("witness-state", {key: state[key] for key in sorted(state)})
            for state in valid_states
        ),
    ]


def _closure_witness_refs(report: FinitePropagationReport, limitations: tuple[str, ...]) -> list[str]:
    if limitations:
        return [SANDBOX_ISOLATION_WITNESS_REF, f"limitation:{limitations[0]}"]
    if report.result_kind == "ContradictionResult":
        return [SANDBOX_ISOLATION_WITNESS_REF, "witness:no-valid-state"]
    return [
        SANDBOX_ISOLATION_WITNESS_REF,
        *(
            stable_identifier(
                "witness-closure",
                {
                    "kernel_signature": report.kernel_signature,
                    "closure_hash": report.closure_hash,
                    "variable_id": variable_id,
                    "projected_values": list(report.projected_values[variable_id]),
                    "pruned_values": list(report.pruned_values[variable_id]),
                },
            )
            for variable_id in sorted(report.projected_values)
        ),
    ]


def _constraint_payload(constraint: FiniteTruthConstraint) -> dict[str, Any]:
    return {
        "constraint_id": constraint.constraint_id,
        "scope": list(constraint.scope),
        "source_ref": constraint.source_ref,
        "statement": constraint.statement,
        "allowed_assignments": [_ordered_assignment(assignment) for assignment in constraint.allowed_assignments],
        "forbidden_assignments": [_ordered_assignment(assignment) for assignment in constraint.forbidden_assignments],
    }


def _normalize_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    normalized = tuple(ensure_non_empty_text(field_name, value) for value in values)
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized


def _normalize_assignments(assignments: Sequence[Assignment]) -> tuple[dict[str, str], ...]:
    normalized: list[dict[str, str]] = []
    for assignment in assignments:
        if not isinstance(assignment, Mapping) or not assignment:
            raise RuntimeCoreInvariantError("constraint assignment must be a non-empty mapping")
        normalized_assignment: dict[str, str] = {}
        for key, value in assignment.items():
            normalized_assignment[ensure_non_empty_text("assignment_key", key)] = ensure_non_empty_text(
                "assignment_value",
                value,
            )
        if len(normalized_assignment) != len(assignment):
            raise RuntimeCoreInvariantError("constraint assignment keys must be unique")
        normalized.append(normalized_assignment)
    return tuple(normalized)


def _ordered_assignment(assignment: Mapping[str, str]) -> dict[str, str]:
    return {key: assignment[key] for key in sorted(assignment)}


def _json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            copied[key] = _json_copy(item)
        elif isinstance(item, list):
            copied[key] = [_json_copy(entry) if isinstance(entry, Mapping) else entry for entry in item]
        else:
            copied[key] = item
    return copied
