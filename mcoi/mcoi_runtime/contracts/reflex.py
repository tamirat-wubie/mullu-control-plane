"""Purpose: Reflex Engine contracts for governed self-inspection and upgrade proposal.
Governance scope: typed evidence, diagnosis, eval, upgrade, sandbox, promotion,
    and capability-maturity records for bounded self-improvement.
Dependencies: shared contract utilities and Python standard library enums.
Invariants:
  - Reflex candidates are proposals only until certification and promotion gates pass.
  - Protected governance surfaces cannot be auto-promoted.
  - Every diagnosis and eval binds source evidence.
  - All contract outputs are frozen and JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_unit_float,
)


class ReflexRisk(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReflexFailureClass(Enum):
    POLICY_FALSE_ALLOW = "policy_false_allow"
    POLICY_FALSE_DENY = "policy_false_deny"
    APPROVAL_MISSING = "approval_missing"
    RBAC_SCOPE_LEAK = "rbac_scope_leak"
    TENANT_BOUNDARY_LEAK = "tenant_boundary_leak"
    BUDGET_FALSE_ALLOW = "budget_false_allow"
    PII_REDACTION_FAILURE = "pii_redaction_failure"
    PROMPT_INJECTION_FAILURE = "prompt_injection_failure"
    TOOL_SCHEMA_MISMATCH = "tool_schema_mismatch"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_COST_SPIKE = "provider_cost_spike"
    RETRIEVAL_LOW_RELEVANCE = "retrieval_low_relevance"
    MEMORY_BAD_ADMISSION = "memory_bad_admission"
    PROOF_MISSING = "proof_missing"
    VERIFICATION_INCONCLUSIVE = "verification_inconclusive"
    DEPLOYMENT_WITNESS_MISSING = "deployment_witness_missing"
    MODEL_OVERKILL_FOR_LOW_RISK_TASK = "model_overkill_for_low_risk_task"


class ReflexEvalClass(Enum):
    CORRECTNESS = "correctness"
    GOVERNANCE = "governance"
    SAFETY = "safety"
    OPERATIONAL = "operational"


class ReflexPromotionDisposition(Enum):
    AUTO_CANARY_ALLOWED = "auto_canary_allowed"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ReflexEvidenceRef(ContractRecord):
    kind: str = ""
    ref_id: str = ""
    evidence_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", require_non_empty_text(self.kind, "kind"))
        object.__setattr__(self, "ref_id", require_non_empty_text(self.ref_id, "ref_id"))
        if self.evidence_hash is not None:
            object.__setattr__(
                self,
                "evidence_hash",
                require_non_empty_text(self.evidence_hash, "evidence_hash"),
            )


@dataclass(frozen=True, slots=True)
class RuntimeHealthSnapshot(ContractRecord):
    snapshot_id: str = ""
    runtime: str = ""
    time_window: str = ""
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[ReflexEvidenceRef, ...] = ()
    captured_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_id",
            require_non_empty_text(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(self, "runtime", require_non_empty_text(self.runtime, "runtime"))
        object.__setattr__(
            self,
            "time_window",
            require_non_empty_text(self.time_window, "time_window"),
        )
        object.__setattr__(self, "metrics", freeze_value(dict(self.metrics)))
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.captured_at, "captured_at")


@dataclass(frozen=True, slots=True)
class ReflexAnomaly(ContractRecord):
    anomaly_id: str = ""
    metric_name: str = ""
    observed_value: float = 0.0
    threshold_value: float = 0.0
    failure_class: ReflexFailureClass = ReflexFailureClass.VERIFICATION_INCONCLUSIVE
    risk: ReflexRisk = ReflexRisk.MEDIUM
    evidence_refs: tuple[ReflexEvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "anomaly_id",
            require_non_empty_text(self.anomaly_id, "anomaly_id"),
        )
        object.__setattr__(
            self,
            "metric_name",
            require_non_empty_text(self.metric_name, "metric_name"),
        )
        object.__setattr__(
            self,
            "observed_value",
            require_non_negative_float(self.observed_value, "observed_value"),
        )
        object.__setattr__(
            self,
            "threshold_value",
            require_non_negative_float(self.threshold_value, "threshold_value"),
        )
        if not isinstance(self.failure_class, ReflexFailureClass):
            raise ValueError("failure_class must be a ReflexFailureClass")
        if not isinstance(self.risk, ReflexRisk):
            raise ValueError("risk must be a ReflexRisk")
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))


@dataclass(frozen=True, slots=True)
class ReflexDiagnosis(ContractRecord):
    diagnosis_id: str = ""
    surface: str = ""
    symptom: str = ""
    failure_class: ReflexFailureClass = ReflexFailureClass.VERIFICATION_INCONCLUSIVE
    risk: ReflexRisk = ReflexRisk.MEDIUM
    hypothesis: str = ""
    confidence: float = 0.0
    evidence_refs: tuple[ReflexEvidenceRef, ...] = ()
    required_tests: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnosis_id",
            require_non_empty_text(self.diagnosis_id, "diagnosis_id"),
        )
        object.__setattr__(self, "surface", require_non_empty_text(self.surface, "surface"))
        object.__setattr__(self, "symptom", require_non_empty_text(self.symptom, "symptom"))
        if not isinstance(self.failure_class, ReflexFailureClass):
            raise ValueError("failure_class must be a ReflexFailureClass")
        if not isinstance(self.risk, ReflexRisk):
            raise ValueError("risk must be a ReflexRisk")
        object.__setattr__(
            self,
            "hypothesis",
            require_non_empty_text(self.hypothesis, "hypothesis"),
        )
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        object.__setattr__(self, "required_tests", freeze_value(list(self.required_tests)))
        object.__setattr__(self, "missing_evidence", freeze_value(list(self.missing_evidence)))


@dataclass(frozen=True, slots=True)
class ReflexEvalCase(ContractRecord):
    eval_id: str = ""
    diagnosis_id: str = ""
    eval_class: ReflexEvalClass = ReflexEvalClass.GOVERNANCE
    input_payload: Mapping[str, Any] = field(default_factory=dict)
    expected: Mapping[str, Any] = field(default_factory=dict)
    assertions: tuple[str, ...] = ()
    evidence_refs: tuple[ReflexEvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "eval_id", require_non_empty_text(self.eval_id, "eval_id"))
        object.__setattr__(
            self,
            "diagnosis_id",
            require_non_empty_text(self.diagnosis_id, "diagnosis_id"),
        )
        if not isinstance(self.eval_class, ReflexEvalClass):
            raise ValueError("eval_class must be a ReflexEvalClass")
        object.__setattr__(self, "input_payload", freeze_value(dict(self.input_payload)))
        object.__setattr__(self, "expected", freeze_value(dict(self.expected)))
        object.__setattr__(self, "assertions", freeze_value(list(self.assertions)))
        if not self.assertions:
            raise ValueError("assertions must contain at least one item")
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        if not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one item")


@dataclass(frozen=True, slots=True)
class ReflexUpgradeCandidate(ContractRecord):
    candidate_id: str = ""
    diagnosis_id: str = ""
    change_surface: str = ""
    risk: ReflexRisk = ReflexRisk.MEDIUM
    description: str = ""
    affected_files: tuple[str, ...] = ()
    required_replays: tuple[str, ...] = ()
    rollback_plan_ref: str = ""
    eval_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            require_non_empty_text(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(
            self,
            "diagnosis_id",
            require_non_empty_text(self.diagnosis_id, "diagnosis_id"),
        )
        object.__setattr__(
            self,
            "change_surface",
            require_non_empty_text(self.change_surface, "change_surface"),
        )
        if not isinstance(self.risk, ReflexRisk):
            raise ValueError("risk must be a ReflexRisk")
        object.__setattr__(
            self,
            "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(self, "affected_files", freeze_value(list(self.affected_files)))
        object.__setattr__(self, "required_replays", freeze_value(list(self.required_replays)))
        object.__setattr__(
            self,
            "rollback_plan_ref",
            require_non_empty_text(self.rollback_plan_ref, "rollback_plan_ref"),
        )
        object.__setattr__(self, "eval_ids", freeze_value(list(self.eval_ids)))


@dataclass(frozen=True, slots=True)
class ReflexSandboxResult(ContractRecord):
    candidate_id: str = ""
    passed: bool = False
    failed_checks: tuple[str, ...] = ()
    report_refs: tuple[ReflexEvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            require_non_empty_text(self.candidate_id, "candidate_id"),
        )
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        object.__setattr__(self, "failed_checks", freeze_value(list(self.failed_checks)))
        object.__setattr__(self, "report_refs", freeze_value(list(self.report_refs)))
        if self.passed and self.failed_checks:
            raise ValueError("passed sandbox result cannot include failed checks")


@dataclass(frozen=True, slots=True)
class ReflexPromotionDecision(ContractRecord):
    decision_id: str = ""
    candidate_id: str = ""
    disposition: ReflexPromotionDisposition = ReflexPromotionDisposition.HUMAN_APPROVAL_REQUIRED
    reason: str = ""
    requires_human_approval: bool = True
    protected_surface: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "decision_id",
            require_non_empty_text(self.decision_id, "decision_id"),
        )
        object.__setattr__(
            self,
            "candidate_id",
            require_non_empty_text(self.candidate_id, "candidate_id"),
        )
        if not isinstance(self.disposition, ReflexPromotionDisposition):
            raise ValueError("disposition must be a ReflexPromotionDisposition")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.requires_human_approval, bool):
            raise ValueError("requires_human_approval must be a boolean")
        if not isinstance(self.protected_surface, bool):
            raise ValueError("protected_surface must be a boolean")


@dataclass(frozen=True, slots=True)
class CapabilityMaturityScore(ContractRecord):
    capability: str = ""
    correctness_score: float = 0.0
    safety_score: float = 0.0
    governance_score: float = 0.0
    proof_score: float = 0.0
    latency_score: float = 0.0
    cost_score: float = 0.0
    production_evidence_score: float = 0.0
    missing: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability",
            require_non_empty_text(self.capability, "capability"),
        )
        for field_name in (
            "correctness_score",
            "safety_score",
            "governance_score",
            "proof_score",
            "latency_score",
            "cost_score",
            "production_evidence_score",
        ):
            object.__setattr__(
                self,
                field_name,
                require_unit_float(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "missing", freeze_value(list(self.missing)))

    @property
    def verdict(self) -> str:
        if self.production_evidence_score < 0.8 or self.proof_score < 0.8 or self.missing:
            return "not_production_closed"
        return "production_closed"

    @property
    def value_gap(self) -> float:
        scores = (
            self.correctness_score,
            self.safety_score,
            self.governance_score,
            self.proof_score,
            self.latency_score,
            self.cost_score,
            self.production_evidence_score,
        )
        return max(0.0, 1.0 - (sum(scores) / len(scores)))
