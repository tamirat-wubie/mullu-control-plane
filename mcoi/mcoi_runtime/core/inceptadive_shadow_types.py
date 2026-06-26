"""InceptaDive Shadow Pass shared types.

Purpose: define the non-executing shadow interrogation contracts used to audit
interpretation, planning, workflow, preflight, and post-outcome processing.
Governance scope: advisory findings only, deterministic hashes, explicit stage
and mode boundaries, and no action execution authority.
Dependencies: Python standard library and runtime invariant helpers.
Invariants: shadow output may recommend, repair, block, or escalate; it never
executes and never replaces the Mullu governance verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class ShadowStage(StrEnum):
    """Lifecycle points where a shadow pass may run."""

    INTERPRETATION = "interpretation"
    PLANNING = "planning"
    WORKFLOW = "workflow"
    PREFLIGHT = "preflight"
    POST_OUTCOME = "post_outcome"


class ShadowMode(StrEnum):
    """Depth of shadow interrogation."""

    OFF = "off"
    LIGHT = "light"
    DEEP = "deep"
    STRICT_PREFLIGHT = "strict_preflight"


class ShadowSeverity(StrEnum):
    """Finding severity."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ShadowFindingKind(StrEnum):
    """Bounded finding kinds emitted by the shadow layer."""

    AMBIGUITY = "ambiguity"
    MISSING_TARGET = "missing_target"
    MISSING_SCOPE = "missing_scope"
    MISSING_PRECONDITION = "missing_precondition"
    MEMORY_RELEVANT = "memory_relevant"
    MEMORY_CONTRADICTION = "memory_contradiction"
    STALE_MEMORY = "stale_memory"
    RISK_DETECTED = "risk_detected"
    UNSAFE_ACTION = "unsafe_action"
    MISSING_EVIDENCE = "missing_evidence"
    PLAN_GAP = "plan_gap"
    DEPENDENCY_GAP = "dependency_gap"
    REPAIR_REQUIRED = "repair_required"
    ESCALATION_REQUIRED = "escalation_required"
    LOW_CONFIDENCE = "low_confidence"
    SAFE_CLEAR = "safe_clear"


class ShadowVerdict(StrEnum):
    """Shadow recommendation before Mullu governance decides."""

    CLEAR = "clear"
    ADVISORY = "advisory"
    REPAIR_REQUIRED = "repair_required"
    BLOCK_RECOMMENDED = "block_recommended"
    ESCALATE = "escalate"
    DEEP_REQUIRED = "deep_required"


_SEVERITY_RANK = {
    ShadowSeverity.INFO: 0,
    ShadowSeverity.LOW: 1,
    ShadowSeverity.MEDIUM: 2,
    ShadowSeverity.HIGH: 3,
    ShadowSeverity.CRITICAL: 4,
}


def severity_rank(severity: ShadowSeverity) -> int:
    """Return a sortable severity rank."""

    return _SEVERITY_RANK[severity]


def _tuple_text(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _tuple_text_object(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise RuntimeCoreInvariantError("expected a list or tuple of text values")
    return _tuple_text(value)


def _mapping_text(value: Mapping[str, object], key: str, *, default: str = "") -> str:
    return str(value.get(key, default) or default)


def _mapping_bool(value: Mapping[str, object], key: str, *, default: bool = False) -> bool:
    item = value.get(key, default)
    if not isinstance(item, bool):
        raise RuntimeCoreInvariantError(f"{key} must be a boolean")
    return item


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_hash(value: Mapping[str, object]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ShadowInterrogationConfig:
    """Static policy for deciding how much shadow interrogation to run."""

    enabled: bool = True
    light_always_on: bool = True
    deep_enabled: bool = True
    strict_preflight_enabled: bool = True
    max_findings: int = 12
    max_depth: int = 3

    def __post_init__(self) -> None:
        if self.max_findings < 1:
            raise RuntimeCoreInvariantError("max_findings must be positive")
        if self.max_depth < 1:
            raise RuntimeCoreInvariantError("max_depth must be positive")


@dataclass(frozen=True)
class ShadowContext:
    """Request, plan, or action context inspected by a shadow pass."""

    request_id: str
    stage: ShadowStage
    user_input: str
    normal_intent: str = ""
    normal_plan: tuple[str, ...] = ()
    candidate_action: str = ""
    explicit_target: str = ""
    scope: str = ""
    risk_level: ShadowSeverity = ShadowSeverity.LOW
    external_side_effect: bool = False
    memory_contradiction: bool = False
    retrieval_receipt_ids: tuple[str, ...] = ()
    created_at: str = "1970-01-01T00:00:00+00:00"
    context_hash: str = ""

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.user_input.strip() and not self.candidate_action.strip():
            raise RuntimeCoreInvariantError("user_input or candidate_action must be non-empty")
        if self.context_hash and self.context_hash != self.expected_hash():
            raise RuntimeCoreInvariantError("ShadowContext context_hash mismatch")

    def text_surface(self) -> str:
        """Return the normalized text inspected by deterministic trigger rules."""

        return " ".join(
            part.strip()
            for part in (
                self.user_input,
                self.normal_intent,
                " ".join(self.normal_plan),
                self.candidate_action,
            )
            if part.strip()
        )

    def to_dict(self, *, include_context_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "request_id": self.request_id,
            "stage": self.stage.value,
            "user_input": self.user_input,
            "normal_intent": self.normal_intent,
            "normal_plan": list(self.normal_plan),
            "candidate_action": self.candidate_action,
            "explicit_target": self.explicit_target,
            "scope": self.scope,
            "risk_level": self.risk_level.value,
            "external_side_effect": self.external_side_effect,
            "memory_contradiction": self.memory_contradiction,
            "retrieval_receipt_ids": list(self.retrieval_receipt_ids),
            "created_at": self.created_at,
        }
        if include_context_hash:
            value["context_hash"] = self.context_hash
        return value

    def expected_hash(self) -> str:
        """Return the expected deterministic hash for this context."""

        return _snapshot_hash(self.to_dict(include_context_hash=False))

    def with_integrity(self) -> "ShadowContext":
        """Return the context with deterministic hash populated."""

        unsigned = replace(self, context_hash="")
        return replace(unsigned, context_hash=unsigned.expected_hash())


@dataclass(frozen=True)
class ShadowFinding:
    """One non-executing shadow finding."""

    finding_id: str
    stage: ShadowStage
    kind: ShadowFindingKind
    severity: ShadowSeverity
    summary: str
    evidence_refs: tuple[str, ...] = ()
    source_note_ids: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    constructive_delta: bool = False
    fracture_delta: bool = False
    repair_required: bool = False
    recommended_action: str = ""
    created_at: str = "1970-01-01T00:00:00+00:00"

    def __post_init__(self) -> None:
        if not self.finding_id.strip():
            raise RuntimeCoreInvariantError("finding_id must be non-empty")
        if not self.summary.strip():
            raise RuntimeCoreInvariantError("summary must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise RuntimeCoreInvariantError("confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "stage": self.stage.value,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "evidence_refs": list(self.evidence_refs),
            "source_note_ids": list(self.source_note_ids),
            "source_event_ids": list(self.source_event_ids),
            "confidence": self.confidence,
            "constructive_delta": self.constructive_delta,
            "fracture_delta": self.fracture_delta,
            "repair_required": self.repair_required,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ShadowFinding":
        """Rebuild a redacted finding from persisted JSONL metadata."""

        try:
            return cls(
                finding_id=_mapping_text(value, "finding_id"),
                stage=ShadowStage(_mapping_text(value, "stage")),
                kind=ShadowFindingKind(_mapping_text(value, "kind")),
                severity=ShadowSeverity(_mapping_text(value, "severity")),
                summary=_mapping_text(value, "summary"),
                evidence_refs=_tuple_text_object(value.get("evidence_refs")),
                source_note_ids=_tuple_text_object(value.get("source_note_ids")),
                source_event_ids=_tuple_text_object(value.get("source_event_ids")),
                confidence=float(value.get("confidence", 1.0)),
                constructive_delta=_mapping_bool(value, "constructive_delta"),
                fracture_delta=_mapping_bool(value, "fracture_delta"),
                repair_required=_mapping_bool(value, "repair_required"),
                recommended_action=_mapping_text(value, "recommended_action"),
                created_at=_mapping_text(value, "created_at", default="1970-01-01T00:00:00+00:00"),
            )
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            raise RuntimeCoreInvariantError("invalid persisted ShadowFinding") from exc

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        stage: ShadowStage,
        kind: ShadowFindingKind,
        severity: ShadowSeverity,
        summary: str,
        evidence_refs: Sequence[str] | None = None,
        source_note_ids: Sequence[str] | None = None,
        source_event_ids: Sequence[str] | None = None,
        confidence: float = 1.0,
        constructive_delta: bool = False,
        fracture_delta: bool = False,
        repair_required: bool = False,
        recommended_action: str = "",
        created_at: str = "1970-01-01T00:00:00+00:00",
    ) -> "ShadowFinding":
        payload = {
            "request_id": request_id,
            "stage": stage.value,
            "kind": kind.value,
            "summary": summary,
            "created_at": created_at,
        }
        return cls(
            finding_id=stable_identifier("shadow-finding", payload),
            stage=stage,
            kind=kind,
            severity=severity,
            summary=summary,
            evidence_refs=_tuple_text(evidence_refs),
            source_note_ids=_tuple_text(source_note_ids),
            source_event_ids=_tuple_text(source_event_ids),
            confidence=confidence,
            constructive_delta=constructive_delta,
            fracture_delta=fracture_delta,
            repair_required=repair_required,
            recommended_action=recommended_action,
            created_at=created_at,
        )


@dataclass(frozen=True)
class ShadowPassResult:
    """Result of a light, deep, or strict shadow pass."""

    result_id: str
    request_id: str
    mode: ShadowMode
    stage: ShadowStage
    verdict: ShadowVerdict
    findings: tuple[ShadowFinding, ...] = ()
    needs_deep_pass: bool = False
    needs_repair: bool = False
    needs_escalation: bool = False
    block_recommended: bool = False
    repaired_plan_candidate: tuple[str, ...] = ()
    created_at: str = "1970-01-01T00:00:00+00:00"
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.result_id.strip():
            raise RuntimeCoreInvariantError("result_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ShadowPassResult snapshot_hash mismatch")

    @property
    def constructive_delta_count(self) -> int:
        return sum(1 for finding in self.findings if finding.constructive_delta)

    @property
    def fracture_delta_count(self) -> int:
        return sum(1 for finding in self.findings if finding.fracture_delta)

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "mode": self.mode.value,
            "stage": self.stage.value,
            "verdict": self.verdict.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "constructive_delta_count": self.constructive_delta_count,
            "fracture_delta_count": self.fracture_delta_count,
            "needs_deep_pass": self.needs_deep_pass,
            "needs_repair": self.needs_repair,
            "needs_escalation": self.needs_escalation,
            "block_recommended": self.block_recommended,
            "repaired_plan_candidate": list(self.repaired_plan_candidate),
            "created_at": self.created_at,
            "execution_authority": False,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ShadowPassResult":
        """Rebuild a redacted result from persisted JSONL metadata."""

        try:
            findings_value = value.get("findings", ())
            if not isinstance(findings_value, (list, tuple)):
                raise RuntimeCoreInvariantError("findings must be a list")
            if not all(isinstance(finding, Mapping) for finding in findings_value):
                raise RuntimeCoreInvariantError("findings must contain mapping values")
            return cls(
                result_id=_mapping_text(value, "result_id"),
                request_id=_mapping_text(value, "request_id"),
                mode=ShadowMode(_mapping_text(value, "mode")),
                stage=ShadowStage(_mapping_text(value, "stage")),
                verdict=ShadowVerdict(_mapping_text(value, "verdict")),
                findings=tuple(
                    ShadowFinding.from_dict(finding)
                    for finding in findings_value
                ),
                needs_deep_pass=_mapping_bool(value, "needs_deep_pass"),
                needs_repair=_mapping_bool(value, "needs_repair"),
                needs_escalation=_mapping_bool(value, "needs_escalation"),
                block_recommended=_mapping_bool(value, "block_recommended"),
                repaired_plan_candidate=_tuple_text_object(value.get("repaired_plan_candidate")),
                created_at=_mapping_text(value, "created_at", default="1970-01-01T00:00:00+00:00"),
                snapshot_hash=_mapping_text(value, "snapshot_hash"),
            )
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            raise RuntimeCoreInvariantError("invalid persisted ShadowPassResult") from exc

    def expected_snapshot_hash(self) -> str:
        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ShadowPassResult":
        result_id = self.result_id
        if result_id == "pending":
            result_id = stable_identifier(
                "shadow-result",
                {
                    "request_id": self.request_id,
                    "mode": self.mode.value,
                    "stage": self.stage.value,
                    "verdict": self.verdict.value,
                    "findings": tuple(finding.finding_id for finding in self.findings),
                },
            )
        unsigned = replace(self, result_id=result_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


@dataclass(frozen=True)
class ShadowInterrogationDecision:
    """Gate decision describing which shadow mode should run."""

    request_id: str
    mode: ShadowMode
    triggers: tuple[str, ...]
    reason: str
    strict_fail_closed: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.reason.strip():
            raise RuntimeCoreInvariantError("reason must be non-empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "mode": self.mode.value,
            "triggers": list(self.triggers),
            "reason": self.reason,
            "strict_fail_closed": self.strict_fail_closed,
            "execution_authority": False,
        }


@dataclass(frozen=True)
class ShadowReceipt:
    """Audit receipt proving how a shadow pass inspected a request or plan."""

    receipt_id: str
    request_id: str
    mode: ShadowMode
    stage: ShadowStage
    context_hash: str
    result_id: str
    finding_ids: tuple[str, ...]
    retrieval_receipt_ids: tuple[str, ...]
    shadow_verdict: ShadowVerdict
    governance_verdict: str = "not_evaluated"
    created_at: str = "1970-01-01T00:00:00+00:00"
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise RuntimeCoreInvariantError("receipt_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.context_hash.strip():
            raise RuntimeCoreInvariantError("context_hash must be non-empty")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ShadowReceipt snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "mode": self.mode.value,
            "stage": self.stage.value,
            "context_hash": self.context_hash,
            "result_id": self.result_id,
            "finding_ids": list(self.finding_ids),
            "retrieval_receipt_ids": list(self.retrieval_receipt_ids),
            "shadow_verdict": self.shadow_verdict.value,
            "governance_verdict": self.governance_verdict,
            "created_at": self.created_at,
            "execution_authority": False,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ShadowReceipt":
        """Rebuild a redacted receipt from persisted JSONL metadata."""

        try:
            return cls(
                receipt_id=_mapping_text(value, "receipt_id"),
                request_id=_mapping_text(value, "request_id"),
                mode=ShadowMode(_mapping_text(value, "mode")),
                stage=ShadowStage(_mapping_text(value, "stage")),
                context_hash=_mapping_text(value, "context_hash"),
                result_id=_mapping_text(value, "result_id"),
                finding_ids=_tuple_text_object(value.get("finding_ids")),
                retrieval_receipt_ids=_tuple_text_object(value.get("retrieval_receipt_ids")),
                shadow_verdict=ShadowVerdict(_mapping_text(value, "shadow_verdict")),
                governance_verdict=_mapping_text(value, "governance_verdict", default="not_evaluated"),
                created_at=_mapping_text(value, "created_at", default="1970-01-01T00:00:00+00:00"),
                snapshot_hash=_mapping_text(value, "snapshot_hash"),
            )
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            raise RuntimeCoreInvariantError("invalid persisted ShadowReceipt") from exc

    def expected_snapshot_hash(self) -> str:
        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ShadowReceipt":
        receipt_id = self.receipt_id
        if receipt_id == "pending":
            receipt_id = stable_identifier(
                "shadow-receipt",
                {
                    "request_id": self.request_id,
                    "result_id": self.result_id,
                    "context_hash": self.context_hash,
                    "shadow_verdict": self.shadow_verdict.value,
                },
            )
        unsigned = replace(self, receipt_id=receipt_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())
