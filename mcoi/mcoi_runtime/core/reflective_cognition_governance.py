"""Bounded reflective cognition governance kernel.

Purpose: provide a deterministic, non-executing metacognitive audit layer for
Mullu reasoning paths. The kernel watches a request or candidate reasoning
artifact for assumptions, unsupported claims, bias markers, contradictions,
edge cases, and correction needs before normal governance renders a verdict.
Governance scope: advisory receipts only; this module does not execute actions,
approve actions, retrieve memory, mutate state, or replace the Mullu governance
verdict.
Dependencies: Python standard library plus runtime invariant helpers.
Invariants: output is redacted by construction, bounded by a reflection budget,
deterministic, rollback-friendly, and explicit about evidence gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


KERNEL_VERSION = "0.1.0"
_DEFAULT_CREATED_AT = "1970-01-01T00:00:00+00:00"


class RiskLevel(StrEnum):
    """Bounded risk levels for choosing reflective depth."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReflectionDepth(StrEnum):
    """How much thinking-about-thinking is allowed for a request."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceStatus(StrEnum):
    """Evidence labels used by the reflective evidence gate."""

    KNOWN = "known"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"


class ValidationStatus(StrEnum):
    """Advisory validation status from reflective governance."""

    PASS = "pass"
    ADVISORY = "advisory"
    NEEDS_EVIDENCE = "needs_evidence"
    NEEDS_REPAIR = "needs_repair"
    BLOCK_RECOMMENDED = "block_recommended"


@dataclass(frozen=True)
class EvidenceClaim:
    """One claim and its evidence state.

    The claim text may be a compact label or redacted summary; receipts expose
    the claim id, status, and evidence refs, not raw private material.
    """

    claim_id: str
    label: str
    status: EvidenceStatus
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise RuntimeCoreInvariantError("claim_id must be non-empty")
        if not self.label.strip():
            raise RuntimeCoreInvariantError("claim label must be non-empty")
        object.__setattr__(self, "status", _coerce_evidence_status(self.status))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref).strip() for ref in self.evidence_refs if str(ref).strip()),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "label": self.label,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class ReflectionBudget:
    """Reflection limits that prevent recursive over-processing."""

    depth: ReflectionDepth
    max_assumptions: int
    max_bias_flags: int
    max_contradictions: int
    max_edge_cases: int
    max_corrections: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "depth", _coerce_depth(self.depth))
        for field_name in (
            "max_assumptions",
            "max_bias_flags",
            "max_contradictions",
            "max_edge_cases",
            "max_corrections",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise RuntimeCoreInvariantError(f"{field_name} must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "depth": self.depth.value,
            "max_assumptions": self.max_assumptions,
            "max_bias_flags": self.max_bias_flags,
            "max_contradictions": self.max_contradictions,
            "max_edge_cases": self.max_edge_cases,
            "max_corrections": self.max_corrections,
        }


@dataclass(frozen=True)
class ReflectiveCognitionReceipt:
    """Redacted metacognitive audit receipt.

    The receipt intentionally stores a request hash instead of raw request text.
    It is advisory and never grants execution authority.
    """

    receipt_id: str
    request_id: str
    request_hash: str
    risk_level: RiskLevel
    reflection_depth: ReflectionDepth
    validation_status: ValidationStatus
    assumptions: tuple[str, ...]
    evidence_gaps: tuple[dict[str, object], ...]
    bias_flags: tuple[str, ...]
    contradictions: tuple[str, ...]
    edge_cases: tuple[str, ...]
    corrections: tuple[str, ...]
    constructive_deltas: tuple[str, ...]
    fracture_deltas: tuple[str, ...]
    unresolved_gaps: tuple[str, ...]
    next_safe_action: str
    reflection_budget: ReflectionBudget
    governance_required: bool = True
    execution_authority: bool = False
    raw_request_text_exposed: bool = False
    private_memory_exposed: bool = False
    kernel_version: str = KERNEL_VERSION
    created_at: str = _DEFAULT_CREATED_AT
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.receipt_id.strip():
            raise RuntimeCoreInvariantError("receipt_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.request_hash.strip():
            raise RuntimeCoreInvariantError("request_hash must be non-empty")
        if self.execution_authority:
            raise RuntimeCoreInvariantError("reflective cognition receipt cannot carry execution authority")
        if not self.governance_required:
            raise RuntimeCoreInvariantError("reflective cognition receipt must require normal governance")
        if self.raw_request_text_exposed or self.private_memory_exposed:
            raise RuntimeCoreInvariantError("reflective cognition receipt must be redacted")
        object.__setattr__(self, "risk_level", _coerce_risk(self.risk_level))
        object.__setattr__(self, "reflection_depth", _coerce_depth(self.reflection_depth))
        object.__setattr__(self, "validation_status", _coerce_validation_status(self.validation_status))
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ReflectiveCognitionReceipt snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "request_hash": self.request_hash,
            "risk_level": self.risk_level.value,
            "reflection_depth": self.reflection_depth.value,
            "validation_status": self.validation_status.value,
            "assumptions": list(self.assumptions),
            "evidence_gaps": [dict(gap) for gap in self.evidence_gaps],
            "bias_flags": list(self.bias_flags),
            "contradictions": list(self.contradictions),
            "edge_cases": list(self.edge_cases),
            "corrections": list(self.corrections),
            "constructive_deltas": list(self.constructive_deltas),
            "fracture_deltas": list(self.fracture_deltas),
            "unresolved_gaps": list(self.unresolved_gaps),
            "next_safe_action": self.next_safe_action,
            "reflection_budget": self.reflection_budget.to_dict(),
            "governance_required": self.governance_required,
            "execution_authority": self.execution_authority,
            "raw_request_text_exposed": self.raw_request_text_exposed,
            "private_memory_exposed": self.private_memory_exposed,
            "kernel_version": self.kernel_version,
            "created_at": self.created_at,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ReflectiveCognitionReceipt":
        receipt_id = self.receipt_id
        if receipt_id == "pending":
            receipt_id = stable_identifier(
                "reflective-cognition-receipt",
                {
                    "request_id": self.request_id,
                    "request_hash": self.request_hash,
                    "risk_level": self.risk_level.value,
                    "reflection_depth": self.reflection_depth.value,
                    "validation_status": self.validation_status.value,
                    "kernel_version": self.kernel_version,
                },
            )
        unsigned = replace(self, receipt_id=receipt_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


@dataclass(frozen=True)
class ReflectiveCognitionAuditInput:
    """Input envelope for the reflective audit.

    This object may contain raw request text internally, but only the hash is
    allowed to cross the public receipt boundary.
    """

    request_id: str
    user_input: str
    stated_goal: str = ""
    candidate_output: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    evidence_claims: tuple[EvidenceClaim, ...] = ()
    created_at: str = _DEFAULT_CREATED_AT

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.user_input.strip():
            raise RuntimeCoreInvariantError("user_input must be non-empty")
        object.__setattr__(self, "risk_level", _coerce_risk(self.risk_level))
        object.__setattr__(self, "evidence_claims", tuple(self.evidence_claims))


HIGH_RISK_TOKENS = (
    "deploy",
    "production",
    "delete",
    "remove",
    "merge",
    "release",
    "migrate",
    "payment",
    "invoice",
    "legal",
    "compliance",
    "credential",
    "secret",
    "admin",
    "send email",
    "external side effect",
)

REFLECTION_TOKENS = (
    "audit",
    "inspect",
    "evaluate",
    "weakness",
    "gap",
    "edge case",
    "refine",
    "metacognition",
    "thinking about thinking",
)

ABSOLUTE_SCOPE_TOKENS = (
    "all important things",
    "everything",
    "fully",
    "guarantee",
    "permanent",
    "100%",
    "never fail",
    "complete forever",
)


BLANK_CLAIMS: tuple[EvidenceClaim, ...] = ()


def audit_reflective_cognition(
    *,
    request_id: str,
    user_input: str,
    stated_goal: str = "",
    candidate_output: str = "",
    risk_level: RiskLevel | str = RiskLevel.MEDIUM,
    evidence_claims: Sequence[EvidenceClaim] = BLANK_CLAIMS,
    created_at: str = _DEFAULT_CREATED_AT,
) -> ReflectiveCognitionReceipt:
    """Run the bounded reflective cognition audit.

    The audit is side-effect free and advisory. It returns a redacted receipt
    that can be logged, displayed, or used by a later governance gate.
    """

    audit_input = ReflectiveCognitionAuditInput(
        request_id=request_id,
        user_input=user_input,
        stated_goal=stated_goal,
        candidate_output=candidate_output,
        risk_level=_coerce_risk(risk_level),
        evidence_claims=tuple(evidence_claims),
        created_at=created_at,
    )
    depth = choose_reflection_depth(audit_input.user_input, audit_input.risk_level)
    budget = reflection_budget_for(depth)
    request_hash = _request_hash(audit_input.user_input)
    assumptions = _limit(extract_assumptions(audit_input), budget.max_assumptions)
    evidence_gaps = tuple(
        claim.to_dict()
        for claim in audit_input.evidence_claims
        if claim.status in {EvidenceStatus.UNCERTAIN, EvidenceStatus.UNSUPPORTED}
    )
    bias_flags = _limit(scan_bias_flags(audit_input), budget.max_bias_flags)
    contradictions = _limit(detect_contradictions(audit_input), budget.max_contradictions)
    edge_cases = _limit(expand_edge_cases(audit_input, bias_flags, contradictions), budget.max_edge_cases)
    corrections = _limit(
        plan_corrections(evidence_gaps, bias_flags, contradictions, edge_cases),
        budget.max_corrections,
    )
    validation_status = classify_validation_status(
        audit_input=audit_input,
        evidence_gaps=evidence_gaps,
        bias_flags=bias_flags,
        contradictions=contradictions,
    )
    constructive_deltas = _constructive_deltas(depth, corrections)
    fracture_deltas = _fracture_deltas(validation_status, evidence_gaps, bias_flags, contradictions)
    unresolved_gaps = _unresolved_gaps(validation_status, evidence_gaps, contradictions)
    next_safe_action = _next_safe_action(validation_status)
    return ReflectiveCognitionReceipt(
        receipt_id="pending",
        request_id=audit_input.request_id,
        request_hash=request_hash,
        risk_level=audit_input.risk_level,
        reflection_depth=depth,
        validation_status=validation_status,
        assumptions=assumptions,
        evidence_gaps=evidence_gaps,
        bias_flags=bias_flags,
        contradictions=contradictions,
        edge_cases=edge_cases,
        corrections=corrections,
        constructive_deltas=constructive_deltas,
        fracture_deltas=fracture_deltas,
        unresolved_gaps=unresolved_gaps,
        next_safe_action=next_safe_action,
        reflection_budget=budget,
        governance_required=True,
        execution_authority=False,
        raw_request_text_exposed=False,
        private_memory_exposed=False,
        created_at=audit_input.created_at,
    ).with_integrity()


def choose_reflection_depth(user_input: str, risk_level: RiskLevel | str) -> ReflectionDepth:
    risk = _coerce_risk(risk_level)
    normalized = user_input.lower()
    if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
        return ReflectionDepth.HIGH
    if _contains_any(normalized, HIGH_RISK_TOKENS):
        return ReflectionDepth.HIGH
    if _contains_any(normalized, REFLECTION_TOKENS) or len(user_input) > 360:
        return ReflectionDepth.MEDIUM
    return ReflectionDepth.LOW


def reflection_budget_for(depth: ReflectionDepth | str) -> ReflectionBudget:
    normalized = _coerce_depth(depth)
    if normalized == ReflectionDepth.HIGH:
        return ReflectionBudget(normalized, 8, 8, 6, 8, 8)
    if normalized == ReflectionDepth.MEDIUM:
        return ReflectionBudget(normalized, 5, 5, 3, 5, 5)
    return ReflectionBudget(normalized, 3, 3, 2, 3, 3)


def extract_assumptions(audit_input: ReflectiveCognitionAuditInput) -> tuple[str, ...]:
    text = audit_input.user_input.lower()
    assumptions: list[str] = []
    if "apply" in text:
        assumptions.append("User likely expects an actual repository or system change, not only a conceptual answer.")
    if "all" in text or "everything" in text:
        assumptions.append("Scope may be broader than the available evidence or safe execution boundary.")
    if any(token in text for token in ("latest", "current", "status", "progress")):
        assumptions.append("Fresh source inspection is required before making current-state claims.")
    if _contains_any(text, HIGH_RISK_TOKENS):
        assumptions.append("The request may affect protected runtime, data, users, or deployment state.")
    if audit_input.stated_goal.strip():
        assumptions.append("The audit should preserve the stated goal while exposing only validated deltas.")
    if not assumptions:
        assumptions.append("Normal governance still needs to validate the final action or answer.")
    return tuple(_dedupe(assumptions))


def scan_bias_flags(audit_input: ReflectiveCognitionAuditInput) -> tuple[str, ...]:
    text = " ".join((audit_input.user_input, audit_input.candidate_output)).lower()
    flags: list[str] = []
    if _contains_any(text, ABSOLUTE_SCOPE_TOKENS):
        flags.append("absolute_scope_overreach")
    if "guarantee" in text or "100%" in text or "permanent" in text:
        flags.append("false_certainty_risk")
    if "apotheosis" in text or "alive" in text or "immortal" in text:
        flags.append("symbolic_inflation_risk")
    if "apply all" in text or "all important things" in text:
        flags.append("scope_creep_risk")
    if "latest" in text or "current" in text:
        flags.append("recency_assumption_risk")
    return tuple(_dedupe(flags))


def detect_contradictions(audit_input: ReflectiveCognitionAuditInput) -> tuple[str, ...]:
    text = " ".join((audit_input.user_input, audit_input.candidate_output)).lower()
    contradictions: list[str] = []
    if "delete" in text and ("preserve" in text or "causal continuity" in text):
        contradictions.append("Destructive action conflicts with preservation or causal-continuity requirements.")
    if "publish" in text and ("private" in text or "secret" in text):
        contradictions.append("Publication intent conflicts with private or secret material boundary.")
    if "autonomous" in text and "approval" in text:
        contradictions.append("Autonomous operation must remain subordinate to explicit approval gates.")
    if "deployed" in text and "design" in text:
        contradictions.append("Deployment claim must not be inferred from design-level integration.")
    return tuple(_dedupe(contradictions))


def expand_edge_cases(
    audit_input: ReflectiveCognitionAuditInput,
    bias_flags: Sequence[str],
    contradictions: Sequence[str],
) -> tuple[str, ...]:
    text = audit_input.user_input.lower()
    cases: list[str] = []
    if "apply" in text:
        cases.append("Tool or repository mutation can fail after partial progress; receipt must report exact boundary.")
    if _contains_any(text, HIGH_RISK_TOKENS):
        cases.append("High-impact action must stay blocked until evidence, approval, and rollback path exist.")
    if bias_flags:
        cases.append("Bias scanner can over-trigger; downstream governance must treat flags as advisory, not verdicts.")
    if contradictions:
        cases.append("Contradictions can indicate either true conflict or ambiguous wording; repair should prefer clarification or safe subset.")
    cases.append("Reflection budget may stop analysis before every weakness is found; unresolved gaps must remain visible.")
    cases.append("Receipts must not expose raw request text, private memory, secrets, or hidden internal traces.")
    return tuple(_dedupe(cases))


def plan_corrections(
    evidence_gaps: Sequence[Mapping[str, object]],
    bias_flags: Sequence[str],
    contradictions: Sequence[str],
    edge_cases: Sequence[str],
) -> tuple[str, ...]:
    corrections: list[str] = []
    if evidence_gaps:
        corrections.append("Attach evidence refs or downgrade unsupported claims before final output.")
    if "absolute_scope_overreach" in bias_flags or "scope_creep_risk" in bias_flags:
        corrections.append("Replace broad claims with bounded constructive deltas, fracture deltas, and unresolved gaps.")
    if "symbolic_inflation_risk" in bias_flags:
        corrections.append("Compress poetic or mystical language into executable architecture, algorithm, and test contracts.")
    if "recency_assumption_risk" in bias_flags:
        corrections.append("Inspect the current source of truth before current-state claims.")
    if contradictions:
        corrections.append("Resolve conflicts before action; prefer safe read-only or advisory output until resolved.")
    if edge_cases:
        corrections.append("Run edge-case validation and preserve rollback path before merge or deployment.")
    if not corrections:
        corrections.append("Proceed to normal governance with receipt logging and no execution authority.")
    return tuple(_dedupe(corrections))


def classify_validation_status(
    *,
    audit_input: ReflectiveCognitionAuditInput,
    evidence_gaps: Sequence[Mapping[str, object]],
    bias_flags: Sequence[str],
    contradictions: Sequence[str],
) -> ValidationStatus:
    text = audit_input.user_input.lower()
    if contradictions and _contains_any(text, ("delete", "publish", "deploy", "production")):
        return ValidationStatus.BLOCK_RECOMMENDED
    if any(gap.get("status") == EvidenceStatus.UNSUPPORTED.value for gap in evidence_gaps):
        return ValidationStatus.NEEDS_EVIDENCE
    if contradictions:
        return ValidationStatus.NEEDS_REPAIR
    if evidence_gaps:
        return ValidationStatus.NEEDS_EVIDENCE
    if bias_flags:
        return ValidationStatus.ADVISORY
    return ValidationStatus.PASS


def _constructive_deltas(depth: ReflectionDepth, corrections: Sequence[str]) -> tuple[str, ...]:
    return (
        f"Selected bounded reflection depth: {depth.value}.",
        "Separated reflective advisory output from final governance verdict.",
        f"Generated {len(corrections)} correction recommendation(s) within the reflection budget.",
    )


def _fracture_deltas(
    status: ValidationStatus,
    evidence_gaps: Sequence[Mapping[str, object]],
    bias_flags: Sequence[str],
    contradictions: Sequence[str],
) -> tuple[str, ...]:
    fractures: list[str] = []
    if status != ValidationStatus.PASS:
        fractures.append(f"Receipt status is {status.value}; final output needs normal governance before action.")
    if evidence_gaps:
        fractures.append("Evidence gate found uncertain or unsupported claims.")
    if bias_flags:
        fractures.append("Bias scanner found advisory risk markers.")
    if contradictions:
        fractures.append("Contradiction detector found unresolved conflict markers.")
    if not fractures:
        fractures.append("No fracture delta detected by the bounded reflective pass.")
    return tuple(fractures)


def _unresolved_gaps(
    status: ValidationStatus,
    evidence_gaps: Sequence[Mapping[str, object]],
    contradictions: Sequence[str],
) -> tuple[str, ...]:
    gaps: list[str] = []
    if status == ValidationStatus.NEEDS_EVIDENCE:
        gaps.append("At least one claim still needs source evidence or downgrade.")
    if status == ValidationStatus.NEEDS_REPAIR:
        gaps.append("At least one reasoning conflict still needs repair.")
    if status == ValidationStatus.BLOCK_RECOMMENDED:
        gaps.append("Action should remain blocked until conflict, evidence, approval, and rollback are resolved.")
    for gap in evidence_gaps:
        gaps.append(f"Evidence gap: {gap.get('claim_id', 'unknown')} is {gap.get('status', 'unknown')}.")
    for contradiction in contradictions:
        gaps.append(f"Conflict gap: {contradiction}")
    if not gaps:
        gaps.append("No unresolved gap detected by the bounded reflective pass.")
    return tuple(_dedupe(gaps))


def _next_safe_action(status: ValidationStatus) -> str:
    if status == ValidationStatus.BLOCK_RECOMMENDED:
        return "Stop before action; collect evidence, approval, and rollback proof."
    if status == ValidationStatus.NEEDS_EVIDENCE:
        return "Attach evidence refs or downgrade claim certainty before final output."
    if status == ValidationStatus.NEEDS_REPAIR:
        return "Repair contradictions and rerun the reflective audit."
    if status == ValidationStatus.ADVISORY:
        return "Proceed only through normal governance with advisory bias flags visible."
    return "Proceed to normal governance; reflective pass did not detect a blocking issue."


def _coerce_risk(value: RiskLevel | str) -> RiskLevel:
    if isinstance(value, RiskLevel):
        return value
    try:
        return RiskLevel(str(value).strip().lower())
    except ValueError as exc:
        raise RuntimeCoreInvariantError("risk_level must be low, medium, high, or critical") from exc


def _coerce_depth(value: ReflectionDepth | str) -> ReflectionDepth:
    if isinstance(value, ReflectionDepth):
        return value
    try:
        return ReflectionDepth(str(value).strip().lower())
    except ValueError as exc:
        raise RuntimeCoreInvariantError("reflection_depth must be low, medium, or high") from exc


def _coerce_evidence_status(value: EvidenceStatus | str) -> EvidenceStatus:
    if isinstance(value, EvidenceStatus):
        return value
    try:
        return EvidenceStatus(str(value).strip().lower())
    except ValueError as exc:
        raise RuntimeCoreInvariantError("evidence status must be known, inferred, uncertain, or unsupported") from exc


def _coerce_validation_status(value: ValidationStatus | str) -> ValidationStatus:
    if isinstance(value, ValidationStatus):
        return value
    try:
        return ValidationStatus(str(value).strip().lower())
    except ValueError as exc:
        raise RuntimeCoreInvariantError("validation_status is not recognized") from exc


def _request_hash(user_input: str) -> str:
    return sha256(user_input.encode("utf-8")).hexdigest()


def _snapshot_hash(value: Mapping[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _contains_any(text: str, tokens: Sequence[str]) -> bool:
    return any(token in text for token in tokens)


def _limit(values: Sequence[str], max_count: int) -> tuple[str, ...]:
    return tuple(values[:max_count])


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            output.append(normalized)
            seen.add(normalized)
    return tuple(output)
