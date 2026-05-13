"""Gateway problem signature.

Purpose: Type a problem before any candidate pipeline is composed for it.
Governance scope: structured problem intake for the capability forge — domain,
    goal, inputs, constraints, risk, success and failure metrics, evidence
    requirements, budget, and method admissibility. The signature is the
    single typed input to candidate composition; without it, comparison is
    unfair and promotion claims have no anchor.
Dependencies: standard-library dataclasses and canonical command-spine hashing
    for deterministic signature identity.
Invariants:
  - A signature is frozen after creation; its hash identifies the problem class.
  - A signature names success metrics, failure metrics, and evidence requirements
    explicitly; no candidate may invent its own success criteria.
  - A signature names allowed and forbidden method families; the composer must
    respect both lists.
  - Risk class is one of: low, medium, high, physical. Physical risk requires
    physical-safety evidence references in addition to standard evidence.
  - Budget and timeout are non-negative; absent values mean unbounded only when
    risk is low.
  - Signatures never carry actionable authority — they describe a problem, not a
    permission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from gateway.command_spine import canonical_hash


RISK_CLASSES = ("low", "medium", "high", "physical")
_VALID_RISK = set(RISK_CLASSES)


@dataclass(frozen=True, slots=True)
class ProblemMetric:
    """One success or failure metric required by the problem signature."""

    metric_id: str
    metric_kind: str  # "success" or "failure"
    direction: str  # "maximize" or "minimize"
    threshold: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id.strip():
            raise ValueError("metric_id_required")
        if self.metric_kind not in ("success", "failure"):
            raise ValueError("metric_kind_must_be_success_or_failure")
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction_must_be_maximize_or_minimize")
        object.__setattr__(self, "metric_id", self.metric_id.strip())


@dataclass(frozen=True, slots=True)
class ProblemEvidenceRequirement:
    """One evidence reference that any candidate must produce."""

    requirement_id: str
    evidence_type: str
    required: bool = True
    schema_ref: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("requirement_id_required")
        if not self.evidence_type.strip():
            raise ValueError("evidence_type_required")


@dataclass(frozen=True, slots=True)
class ProblemSignature:
    """Typed problem statement consumed by the candidate composer.

    Two signatures with identical fields produce identical signature_hash
    values; this makes the comparison ledger addressable by problem class.
    """

    problem_id: str
    domain: str
    goal: str
    inputs: tuple[str, ...]
    constraints: tuple[str, ...]
    risk: str
    metrics: tuple[ProblemMetric, ...]
    required_evidence: tuple[ProblemEvidenceRequirement, ...]
    budget_units: float = 0.0
    timeout_seconds: float = 0.0
    allowed_method_families: tuple[str, ...] = ()
    forbidden_method_families: tuple[str, ...] = ()
    baseline_method_family: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    signature_hash: str = ""

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("problem_id_required")
        if not self.domain.strip():
            raise ValueError("domain_required")
        if not self.goal.strip():
            raise ValueError("goal_required")
        if self.risk not in _VALID_RISK:
            raise ValueError(f"risk_must_be_one_of:{','.join(RISK_CLASSES)}")
        if self.budget_units < 0:
            raise ValueError("budget_units_must_be_non_negative")
        if self.timeout_seconds < 0:
            raise ValueError("timeout_seconds_must_be_non_negative")
        if self.risk != "low" and (self.budget_units == 0 or self.timeout_seconds == 0):
            raise ValueError("non_low_risk_requires_explicit_budget_and_timeout")
        if not self.metrics:
            raise ValueError("at_least_one_success_or_failure_metric_required")
        if not any(m.metric_kind == "success" for m in self.metrics):
            raise ValueError("at_least_one_success_metric_required")
        if self.risk == "physical":
            evidence_types = {req.evidence_type for req in self.required_evidence}
            if "physical_safety" not in evidence_types:
                raise ValueError("physical_risk_requires_physical_safety_evidence")
        overlap = set(self.allowed_method_families) & set(self.forbidden_method_families)
        if overlap:
            raise ValueError(f"method_family_in_both_lists:{sorted(overlap)}")
        if self.baseline_method_family and self.forbidden_method_families:
            if self.baseline_method_family in self.forbidden_method_families:
                raise ValueError("baseline_method_family_in_forbidden_list")

        object.__setattr__(self, "problem_id", self.problem_id.strip())
        object.__setattr__(self, "domain", self.domain.strip())
        object.__setattr__(self, "goal", self.goal.strip())
        object.__setattr__(self, "inputs", tuple(str(value) for value in self.inputs))
        object.__setattr__(self, "constraints", tuple(str(value) for value in self.constraints))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence))
        object.__setattr__(self, "allowed_method_families", tuple(self.allowed_method_families))
        object.__setattr__(self, "forbidden_method_families", tuple(self.forbidden_method_families))

        if not self.signature_hash:
            object.__setattr__(self, "signature_hash", compute_signature_hash(self))

    def admits_method_family(self, family: str) -> bool:
        """Return True when a method family is admissible under this signature."""
        if family in self.forbidden_method_families:
            return False
        if self.allowed_method_families and family not in self.allowed_method_families:
            return False
        return True

    def success_metrics(self) -> tuple[ProblemMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.metric_kind == "success")

    def failure_metrics(self) -> tuple[ProblemMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.metric_kind == "failure")


def compute_signature_hash(signature: ProblemSignature) -> str:
    """Return the canonical hash that identifies a problem class."""
    payload = {
        "problem_id": signature.problem_id,
        "domain": signature.domain,
        "goal": signature.goal,
        "inputs": list(signature.inputs),
        "constraints": list(signature.constraints),
        "risk": signature.risk,
        "metrics": [asdict(m) for m in signature.metrics],
        "required_evidence": [asdict(e) for e in signature.required_evidence],
        "budget_units": signature.budget_units,
        "timeout_seconds": signature.timeout_seconds,
        "allowed_method_families": list(signature.allowed_method_families),
        "forbidden_method_families": list(signature.forbidden_method_families),
        "baseline_method_family": signature.baseline_method_family,
    }
    return canonical_hash(payload)


def signature_from_mapping(payload: dict[str, Any]) -> ProblemSignature:
    """Reconstruct a ProblemSignature from a stored dict (e.g. from JSON)."""
    metrics = tuple(
        ProblemMetric(**metric) if isinstance(metric, dict) else metric
        for metric in payload.get("metrics", ())
    )
    required_evidence = tuple(
        ProblemEvidenceRequirement(**req) if isinstance(req, dict) else req
        for req in payload.get("required_evidence", ())
    )
    return ProblemSignature(
        problem_id=payload["problem_id"],
        domain=payload["domain"],
        goal=payload["goal"],
        inputs=tuple(payload.get("inputs", ())),
        constraints=tuple(payload.get("constraints", ())),
        risk=payload["risk"],
        metrics=metrics,
        required_evidence=required_evidence,
        budget_units=float(payload.get("budget_units", 0.0)),
        timeout_seconds=float(payload.get("timeout_seconds", 0.0)),
        allowed_method_families=tuple(payload.get("allowed_method_families", ())),
        forbidden_method_families=tuple(payload.get("forbidden_method_families", ())),
        baseline_method_family=payload.get("baseline_method_family", ""),
        metadata=dict(payload.get("metadata", {})),
        signature_hash=payload.get("signature_hash", ""),
    )
