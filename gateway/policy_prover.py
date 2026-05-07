"""Gateway policy prover.

Purpose: Evaluate explicit policy invariants against bounded cases and emit
    schema-backed proof reports with counterexamples.
Governance scope: policy invariant validation, counterexample reporting,
    evidence anchoring, and non-mutating proof witnesses.
Dependencies: dataclasses and canonical command-spine hashing.
Invariants:
  - Proof reports are derived from explicit cases, never assumed.
  - A violated invariant must emit a concrete counterexample.
  - The prover is read-only and cannot weaken policy to prove success.
  - Empty invariant or case sets are rejected before proof emission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash


@dataclass(frozen=True, slots=True)
class PolicyProofInvariant:
    """One decidable invariant over bounded policy cases."""

    invariant_id: str
    description: str
    required_fields: tuple[str, ...]
    expected_values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invariant_id.strip():
            raise ValueError("invariant_id_required")
        if not self.description.strip():
            raise ValueError("invariant_description_required")
        object.__setattr__(self, "invariant_id", self.invariant_id.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "required_fields", tuple(str(field) for field in self.required_fields))
        object.__setattr__(self, "expected_values", dict(self.expected_values))


@dataclass(frozen=True, slots=True)
class PolicyProofCase:
    """Bounded input case used to search for policy counterexamples."""

    case_id: str
    subject_id: str
    attributes: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id_required")
        if not self.subject_id.strip():
            raise ValueError("subject_id_required")
        object.__setattr__(self, "case_id", self.case_id.strip())
        object.__setattr__(self, "subject_id", self.subject_id.strip())
        object.__setattr__(self, "attributes", dict(self.attributes))
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))


@dataclass(frozen=True, slots=True)
class PolicyCounterexample:
    """Concrete invariant violation discovered by the prover."""

    invariant_id: str
    case_id: str
    subject_id: str
    reason: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))


@dataclass(frozen=True, slots=True)
class PolicyProofReport:
    """Hash-bound policy proof report."""

    report_id: str
    policy_id: str
    status: str
    invariant_count: int
    case_count: int
    counterexample_count: int
    proven_invariants: tuple[str, ...]
    counterexamples: tuple[PolicyCounterexample, ...]
    evidence_refs: tuple[str, ...]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"proved", "counterexample_found"}:
            raise ValueError("policy_proof_status_invalid")
        if self.counterexample_count != len(self.counterexamples):
            raise ValueError("counterexample_count_mismatch")
        if self.status == "proved" and self.counterexamples:
            raise ValueError("proved_report_cannot_have_counterexamples")
        if self.status == "counterexample_found" and not self.counterexamples:
            raise ValueError("counterexample_report_requires_counterexamples")
        object.__setattr__(self, "proven_invariants", tuple(self.proven_invariants))
        object.__setattr__(self, "counterexamples", tuple(self.counterexamples))
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class PolicyProver:
    """Search bounded cases for policy invariant counterexamples."""

    def prove(
        self,
        *,
        policy_id: str,
        invariants: tuple[PolicyProofInvariant, ...],
        cases: tuple[PolicyProofCase, ...],
        evidence_refs: tuple[str, ...] = (),
    ) -> PolicyProofReport:
        """Return a deterministic proof report for explicit invariants and cases."""
        if not policy_id.strip():
            raise ValueError("policy_id_required")
        if not invariants:
            raise ValueError("policy_invariants_required")
        if not cases:
            raise ValueError("policy_cases_required")
        counterexamples = tuple(
            counterexample
            for invariant in invariants
            for case in cases
            for counterexample in _counterexamples_for_case(invariant, case)
        )
        violated = {counterexample.invariant_id for counterexample in counterexamples}
        proven_invariants = tuple(
            invariant.invariant_id for invariant in invariants if invariant.invariant_id not in violated
        )
        status = "proved" if not counterexamples else "counterexample_found"
        report = PolicyProofReport(
            report_id="pending",
            policy_id=policy_id.strip(),
            status=status,
            invariant_count=len(invariants),
            case_count=len(cases),
            counterexample_count=len(counterexamples),
            proven_invariants=proven_invariants,
            counterexamples=counterexamples,
            evidence_refs=evidence_refs,
            metadata={"proof_is_bounded": True, "policy_weakening_allowed": False},
        )
        report_hash = canonical_hash(asdict(report))
        return replace(report, report_id=f"policy-proof-{report_hash[:16]}", report_hash=report_hash)


def _counterexamples_for_case(
    invariant: PolicyProofInvariant,
    case: PolicyProofCase,
) -> tuple[PolicyCounterexample, ...]:
    counterexamples: list[PolicyCounterexample] = []
    for field_name in invariant.required_fields:
        if field_name not in case.attributes:
            counterexamples.append(
                PolicyCounterexample(
                    invariant_id=invariant.invariant_id,
                    case_id=case.case_id,
                    subject_id=case.subject_id,
                    reason=f"missing_required_field:{field_name}",
                    evidence_refs=case.evidence_refs,
                )
            )
    for field_name, expected_value in invariant.expected_values.items():
        if field_name not in case.attributes:
            continue
        observed_value = case.attributes.get(field_name)
        if observed_value != expected_value:
            counterexamples.append(
                PolicyCounterexample(
                    invariant_id=invariant.invariant_id,
                    case_id=case.case_id,
                    subject_id=case.subject_id,
                    reason=f"expected_value_mismatch:{field_name}",
                    evidence_refs=case.evidence_refs,
                )
            )
    return tuple(counterexamples)
