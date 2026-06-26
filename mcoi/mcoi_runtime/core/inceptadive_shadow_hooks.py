"""Non-executing InceptaDive Shadow Pass hooks.

Purpose: provide small interpretation, planning, workflow, and preflight hook
adapters that let normal Mullu processing ask the shadow layer what may be
ambiguous, missing, risky, or blocked.
Governance scope: advisory hook outcomes only; hooks do not execute, approve,
retrieve memory, mutate state, or replace the Mullu governance verdict.
Dependencies: dataclasses, hashing, Protocol typing, shadow shared types, and
stable identifier generation.
Invariants: hook output is redacted by construction, secret-shaped request
identifiers are replaced before runtime inspection, carries no execution
authority, and records whether deeper interrogation, repair, escalation, or
normal governance is required.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Mapping, Protocol, Sequence

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowMode,
    ShadowPassResult,
    ShadowReceipt,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier

_PUBLIC_HOOK_REQUEST_PREFIX = "shadow_hook_request_"
_SAFE_REQUEST_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:")
_SENSITIVE_REQUEST_ID_MARKERS = (
    "secret",
    "token",
    "credential",
    "password",
    "private",
    "apikey",
    "api_key",
    "bearer",
)


class ShadowHookStatus(StrEnum):
    """Bounded hook-level status labels."""

    CLEAR = "clear"
    ADVISORY = "advisory"
    DEEP_REQUIRED = "deep_required"
    REPAIR_REQUIRED = "repair_required"
    BLOCK_RECOMMENDED = "block_recommended"
    ESCALATE = "escalate"


class ShadowRuntimeLike(Protocol):
    """Small runtime protocol needed by non-executing hooks."""

    def inspect_request(self, context: ShadowContext) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        """Inspect interpretation, planning, or workflow context."""

    def preflight_action(
        self,
        context: ShadowContext,
        *,
        required_evidence_refs: tuple[str, ...] = (),
    ) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        """Inspect a candidate action before execution governance."""


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_hash(value: Mapping[str, object]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ShadowHookOutcome:
    """Redacted advisory outcome from one shadow hook invocation."""

    hook_id: str
    request_id: str
    stage: ShadowStage
    status: ShadowHookStatus
    shadow_mode: ShadowMode
    shadow_verdict: ShadowVerdict
    result_id: str
    receipt_id: str
    finding_count: int
    constructive_delta_count: int
    fracture_delta_count: int
    needs_deep_pass: bool
    needs_repair: bool
    needs_escalation: bool
    block_recommended: bool
    allowed_to_continue: bool
    governance_required: bool = True
    execution_authority: bool = False
    created_at: str = "1970-01-01T00:00:00+00:00"
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.hook_id.strip():
            raise RuntimeCoreInvariantError("hook_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if self.finding_count < 0:
            raise RuntimeCoreInvariantError("finding_count must be non-negative")
        if self.constructive_delta_count < 0:
            raise RuntimeCoreInvariantError("constructive_delta_count must be non-negative")
        if self.fracture_delta_count < 0:
            raise RuntimeCoreInvariantError("fracture_delta_count must be non-negative")
        if self.execution_authority:
            raise RuntimeCoreInvariantError("shadow hook cannot carry execution authority")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ShadowHookOutcome snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        """Return a redacted JSON-compatible hook outcome."""

        value: dict[str, object] = {
            "hook_id": self.hook_id,
            "request_id": self.request_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "shadow_mode": self.shadow_mode.value,
            "shadow_verdict": self.shadow_verdict.value,
            "result_id": self.result_id,
            "receipt_id": self.receipt_id,
            "finding_count": self.finding_count,
            "constructive_delta_count": self.constructive_delta_count,
            "fracture_delta_count": self.fracture_delta_count,
            "needs_deep_pass": self.needs_deep_pass,
            "needs_repair": self.needs_repair,
            "needs_escalation": self.needs_escalation,
            "block_recommended": self.block_recommended,
            "allowed_to_continue": self.allowed_to_continue,
            "governance_required": self.governance_required,
            "execution_authority": self.execution_authority,
            "raw_request_text_exposed": False,
            "private_memory_exposed": False,
            "created_at": self.created_at,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        """Return expected deterministic snapshot hash."""

        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ShadowHookOutcome":
        """Return the hook outcome with deterministic id and hash populated."""

        hook_id = self.hook_id
        if hook_id == "pending":
            hook_id = stable_identifier(
                "shadow-hook",
                {
                    "request_id": self.request_id,
                    "stage": self.stage.value,
                    "result_id": self.result_id,
                    "receipt_id": self.receipt_id,
                    "status": self.status.value,
                },
            )
        unsigned = replace(self, hook_id=hook_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


def run_interpretation_shadow_hook(
    runtime: ShadowRuntimeLike,
    *,
    request_id: str,
    user_input: str,
    normal_intent: str = "",
    explicit_target: str = "",
    scope: str = "",
    risk_level: ShadowSeverity = ShadowSeverity.LOW,
    external_side_effect: bool = False,
    memory_contradiction: bool = False,
    retrieval_receipt_ids: Sequence[str] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowHookOutcome:
    """Run the shadow hook before final user-request interpretation."""

    context = _context(
        request_id=_public_hook_request_id(request_id, stage=ShadowStage.INTERPRETATION, created_at=created_at),
        stage=ShadowStage.INTERPRETATION,
        user_input=user_input,
        normal_intent=normal_intent,
        explicit_target=explicit_target,
        scope=scope,
        risk_level=risk_level,
        external_side_effect=external_side_effect,
        memory_contradiction=memory_contradiction,
        retrieval_receipt_ids=retrieval_receipt_ids,
        created_at=created_at,
    )
    result, receipt = runtime.inspect_request(context)
    return _outcome_from_result(context, result, receipt)


def run_planning_shadow_hook(
    runtime: ShadowRuntimeLike,
    *,
    request_id: str,
    user_input: str,
    plan_steps: Sequence[str],
    normal_intent: str = "",
    explicit_target: str = "",
    scope: str = "",
    risk_level: ShadowSeverity = ShadowSeverity.LOW,
    external_side_effect: bool = False,
    memory_contradiction: bool = False,
    retrieval_receipt_ids: Sequence[str] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowHookOutcome:
    """Run the shadow hook after a candidate plan is assembled."""

    context = _context(
        request_id=_public_hook_request_id(request_id, stage=ShadowStage.PLANNING, created_at=created_at),
        stage=ShadowStage.PLANNING,
        user_input=user_input,
        normal_intent=normal_intent,
        normal_plan=tuple(str(step).strip() for step in plan_steps if str(step).strip()),
        explicit_target=explicit_target,
        scope=scope,
        risk_level=risk_level,
        external_side_effect=external_side_effect,
        memory_contradiction=memory_contradiction,
        retrieval_receipt_ids=retrieval_receipt_ids,
        created_at=created_at,
    )
    result, receipt = runtime.inspect_request(context)
    return _outcome_from_result(context, result, receipt)


def run_workflow_shadow_hook(
    runtime: ShadowRuntimeLike,
    *,
    request_id: str,
    user_input: str,
    workflow_steps: Sequence[str],
    normal_intent: str = "",
    explicit_target: str = "",
    scope: str = "",
    risk_level: ShadowSeverity = ShadowSeverity.LOW,
    external_side_effect: bool = False,
    memory_contradiction: bool = False,
    retrieval_receipt_ids: Sequence[str] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowHookOutcome:
    """Run the shadow hook over a multi-step workflow candidate."""

    context = _context(
        request_id=_public_hook_request_id(request_id, stage=ShadowStage.WORKFLOW, created_at=created_at),
        stage=ShadowStage.WORKFLOW,
        user_input=user_input,
        normal_intent=normal_intent,
        normal_plan=tuple(str(step).strip() for step in workflow_steps if str(step).strip()),
        explicit_target=explicit_target,
        scope=scope,
        risk_level=risk_level,
        external_side_effect=external_side_effect,
        memory_contradiction=memory_contradiction,
        retrieval_receipt_ids=retrieval_receipt_ids,
        created_at=created_at,
    )
    result, receipt = runtime.inspect_request(context)
    return _outcome_from_result(context, result, receipt)


def run_preflight_shadow_hook(
    runtime: ShadowRuntimeLike,
    *,
    request_id: str,
    candidate_action: str,
    user_input: str = "",
    normal_intent: str = "",
    explicit_target: str = "",
    scope: str = "",
    risk_level: ShadowSeverity = ShadowSeverity.LOW,
    external_side_effect: bool = False,
    memory_contradiction: bool = False,
    retrieval_receipt_ids: Sequence[str] = (),
    required_evidence_refs: Sequence[str] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowHookOutcome:
    """Run strict shadow preflight for a candidate action."""

    context = _context(
        request_id=_public_hook_request_id(request_id, stage=ShadowStage.PREFLIGHT, created_at=created_at),
        stage=ShadowStage.PREFLIGHT,
        user_input=user_input or candidate_action,
        normal_intent=normal_intent,
        candidate_action=candidate_action,
        explicit_target=explicit_target,
        scope=scope,
        risk_level=risk_level,
        external_side_effect=external_side_effect,
        memory_contradiction=memory_contradiction,
        retrieval_receipt_ids=retrieval_receipt_ids,
        created_at=created_at,
    )
    result, receipt = runtime.preflight_action(
        context,
        required_evidence_refs=tuple(str(ref).strip() for ref in required_evidence_refs if str(ref).strip()),
    )
    return _outcome_from_result(context, result, receipt)


def _context(
    *,
    request_id: str,
    stage: ShadowStage,
    user_input: str,
    normal_intent: str = "",
    normal_plan: tuple[str, ...] = (),
    candidate_action: str = "",
    explicit_target: str = "",
    scope: str = "",
    risk_level: ShadowSeverity = ShadowSeverity.LOW,
    external_side_effect: bool = False,
    memory_contradiction: bool = False,
    retrieval_receipt_ids: Sequence[str] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowContext:
    return ShadowContext(
        request_id=request_id,
        stage=stage,
        user_input=user_input,
        normal_intent=normal_intent,
        normal_plan=normal_plan,
        candidate_action=candidate_action,
        explicit_target=explicit_target,
        scope=scope,
        risk_level=risk_level,
        external_side_effect=external_side_effect,
        memory_contradiction=memory_contradiction,
        retrieval_receipt_ids=tuple(str(ref).strip() for ref in retrieval_receipt_ids if str(ref).strip()),
        created_at=created_at,
    ).with_integrity()


def _public_hook_request_id(request_id: str, *, stage: ShadowStage, created_at: str) -> str:
    """Return a hook request id safe for direct outputs and runtime persistence."""

    normalized = " ".join(str(request_id or "").strip().split())
    if _request_id_is_public_reference(normalized):
        return normalized
    return _PUBLIC_HOOK_REQUEST_PREFIX + stable_identifier(
        "inceptadive-shadow-hook-request",
        {
            "stage": stage.value,
            "request_id": normalized,
            "created_at": created_at,
        },
    )


def _request_id_is_public_reference(value: str) -> bool:
    if not value or len(value) > 128:
        return False
    if value.startswith(_PUBLIC_HOOK_REQUEST_PREFIX):
        return True
    if any(character not in _SAFE_REQUEST_ID_CHARS for character in value):
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in _SENSITIVE_REQUEST_ID_MARKERS)


def _outcome_from_result(
    context: ShadowContext,
    result: ShadowPassResult,
    receipt: ShadowReceipt | None,
) -> ShadowHookOutcome:
    status = _status_from_result(result)
    allowed_to_continue = status in {ShadowHookStatus.CLEAR, ShadowHookStatus.ADVISORY}
    return ShadowHookOutcome(
        hook_id="pending",
        request_id=context.request_id,
        stage=context.stage,
        status=status,
        shadow_mode=result.mode,
        shadow_verdict=result.verdict,
        result_id=result.result_id,
        receipt_id=receipt.receipt_id if receipt is not None else "",
        finding_count=len(result.findings),
        constructive_delta_count=result.constructive_delta_count,
        fracture_delta_count=result.fracture_delta_count,
        needs_deep_pass=result.needs_deep_pass,
        needs_repair=result.needs_repair,
        needs_escalation=result.needs_escalation,
        block_recommended=result.block_recommended,
        allowed_to_continue=allowed_to_continue,
        governance_required=True,
        execution_authority=False,
        created_at=context.created_at,
    ).with_integrity()


def _status_from_result(result: ShadowPassResult) -> ShadowHookStatus:
    if result.block_recommended or result.verdict == ShadowVerdict.BLOCK_RECOMMENDED:
        return ShadowHookStatus.BLOCK_RECOMMENDED
    if result.needs_escalation or result.verdict == ShadowVerdict.ESCALATE:
        return ShadowHookStatus.ESCALATE
    if result.needs_repair or result.verdict == ShadowVerdict.REPAIR_REQUIRED:
        return ShadowHookStatus.REPAIR_REQUIRED
    if result.needs_deep_pass or result.verdict == ShadowVerdict.DEEP_REQUIRED:
        return ShadowHookStatus.DEEP_REQUIRED
    if result.verdict == ShadowVerdict.ADVISORY:
        return ShadowHookStatus.ADVISORY
    return ShadowHookStatus.CLEAR
