"""Gateway multimodal operating layer.

Purpose: govern text, document, visual, voice, browser, email, calendar, form,
    and video-frame operations before they reach adapter workers.
Governance scope: modality policy admission, source-reference preservation,
    receipt requirements, sensitive-data controls, external-effect blocking,
    and deterministic operation receipts.
Dependencies: dataclasses, command-spine canonical hashing, and worker policy
    declarations.
Invariants:
  - Every evaluated operation emits a receipt.
  - Unknown modalities fail closed without dispatch authority.
  - Source references and evidence references are preserved on receipts.
  - External effects are blocked unless the worker policy is production
    certified and required evidence controls are present.
  - Multimodal operation receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from gateway.command_spine import canonical_hash


MODALITIES = (
    "text",
    "pdf",
    "spreadsheet",
    "image",
    "voice",
    "screen",
    "browser",
    "email",
    "calendar",
    "forms",
    "video_frame",
)
RECEIPT_MODALITIES = (*MODALITIES, "unknown")
SENSITIVITY_LEVELS = ("public", "internal", "confidential", "restricted")
RECEIPT_STATUSES = ("allowed", "blocked", "requires_review")
MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")
MATURITY_RANK = {level: index for index, level in enumerate(MATURITY_LEVELS)}
EXTERNAL_SIDE_EFFECT_OPERATIONS = frozenset(
    {
        "send_email",
        "send_calendar_invite",
        "submit_form",
        "browser_submit",
        "browser_click",
        "post_message",
        "upload_file",
        "write_record",
        "delete_record",
    }
)
BASE_CONTROLS = (
    "tenant_binding",
    "source_reference",
    "worker_receipt",
    "terminal_closure",
)
EXTERNAL_EFFECT_CONTROLS = (
    "approval",
    "signed_worker_response",
    "live_write_receipt",
)
MULTIMODAL_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:multimodal-operation-receipt:1"


@dataclass(frozen=True, slots=True)
class MultimodalOperationRequest:
    """One modality-bound operation request before worker dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    worker_id: str
    capability: str
    modality: str
    operation: str
    command_id: str
    input_hash: str
    source_ref: str
    source_hash: str
    evidence_refs: list[str] = field(default_factory=list)
    sensitivity_level: str = "internal"
    external_effect: bool = False
    requested_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "worker_id",
            "capability",
            "modality",
            "operation",
            "command_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.sensitivity_level not in SENSITIVITY_LEVELS:
            raise ValueError("sensitivity_level_invalid")
        object.__setattr__(self, "input_hash", str(self.input_hash).strip())
        object.__setattr__(self, "source_ref", str(self.source_ref).strip())
        object.__setattr__(self, "source_hash", str(self.source_hash).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "requested_at", str(self.requested_at).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ModalityWorkerPolicy:
    """Worker policy envelope for one multimodal capability binding."""

    worker_id: str
    capability: str
    modalities: list[str]
    allowed_operations: list[str]
    forbidden_operations: list[str] = field(default_factory=list)
    maturity_level: str = "C3"
    production_certified: bool = False
    preserves_source_reference: bool = True
    emits_worker_receipt: bool = True
    external_effects_allowed: bool = False
    allowed_sensitive_levels: list[str] = field(
        default_factory=lambda: ["public", "internal"]
    )
    required_controls: list[str] = field(default_factory=list)
    required_evidence_refs: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.worker_id.strip():
            raise ValueError("worker_id_required")
        if not self.capability.strip():
            raise ValueError("capability_required")
        if self.maturity_level not in MATURITY_LEVELS:
            raise ValueError("maturity_level_invalid")
        modalities = _normalize_list(self.modalities)
        if not modalities:
            raise ValueError("modalities_required")
        invalid_modalities = [modality for modality in modalities if modality not in MODALITIES]
        if invalid_modalities:
            raise ValueError("policy_modality_invalid")
        allowed_operations = _normalize_list(self.allowed_operations)
        if not allowed_operations:
            raise ValueError("allowed_operations_required")
        allowed_sensitive_levels = _normalize_list(self.allowed_sensitive_levels)
        if any(level not in SENSITIVITY_LEVELS for level in allowed_sensitive_levels):
            raise ValueError("allowed_sensitive_level_invalid")
        object.__setattr__(self, "worker_id", self.worker_id.strip())
        object.__setattr__(self, "capability", self.capability.strip())
        object.__setattr__(self, "modalities", modalities)
        object.__setattr__(self, "allowed_operations", allowed_operations)
        object.__setattr__(
            self,
            "forbidden_operations",
            _normalize_list(self.forbidden_operations),
        )
        object.__setattr__(self, "allowed_sensitive_levels", allowed_sensitive_levels)
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(
            self,
            "required_evidence_refs",
            _normalize_list(self.required_evidence_refs),
        )
        object.__setattr__(self, "policy_refs", _normalize_list(self.policy_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class MultimodalOperationReceipt:
    """Schema-backed non-terminal receipt for one multimodal operation check."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    worker_id: str
    capability: str
    modality: str
    operation: str
    command_id: str
    status: str
    blocked_reasons: list[str]
    review_reasons: list[str]
    required_controls: list[str]
    source_ref: str
    source_hash: str
    input_hash: str
    evidence_refs: list[str]
    policy_refs: list[str]
    requested_at: str
    evaluated_at: str
    receipt_schema_ref: str
    source_reference_preserved: bool
    worker_receipt_required: bool
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.modality not in RECEIPT_MODALITIES:
            raise ValueError("receipt_modality_invalid")
        if self.status not in RECEIPT_STATUSES:
            raise ValueError("receipt_status_invalid")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "review_reasons", _normalize_list(self.review_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "policy_refs", _normalize_list(self.policy_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class MultimodalOperatingLayer:
    """Fail-closed governance envelope for modality-specific worker dispatch."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _default_clock

    def evaluate(
        self,
        request: MultimodalOperationRequest,
        policy: ModalityWorkerPolicy | None,
    ) -> MultimodalOperationReceipt:
        """Return a deterministic receipt before any worker dispatch occurs."""
        evaluated_at = self._clock()
        blocked_reasons: list[str] = []
        review_reasons: list[str] = []
        required_controls = [*BASE_CONTROLS]
        policy_refs: list[str] = []

        if request.modality not in MODALITIES:
            blocked_reasons.append("unknown_modality")
        elif policy is None:
            blocked_reasons.append("worker_policy_missing")
        else:
            policy_refs = [*policy.policy_refs]
            _apply_worker_policy_checks(
                request=request,
                policy=policy,
                blocked_reasons=blocked_reasons,
                review_reasons=review_reasons,
                required_controls=required_controls,
            )

        _apply_source_checks(request, blocked_reasons)
        _apply_evidence_checks(request, blocked_reasons)
        status = _status(blocked_reasons, review_reasons)
        receipt = MultimodalOperationReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            worker_id=request.worker_id,
            capability=request.capability,
            modality=request.modality if request.modality in MODALITIES else "unknown",
            operation=request.operation,
            command_id=request.command_id,
            status=status,
            blocked_reasons=_unique(blocked_reasons),
            review_reasons=_unique(review_reasons),
            required_controls=_unique(required_controls),
            source_ref=request.source_ref,
            source_hash=request.source_hash,
            input_hash=request.input_hash,
            evidence_refs=request.evidence_refs,
            policy_refs=policy_refs,
            requested_at=request.requested_at,
            evaluated_at=evaluated_at,
            receipt_schema_ref=MULTIMODAL_RECEIPT_SCHEMA_REF,
            source_reference_preserved=True,
            worker_receipt_required=True,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "dispatch_allowed": status == "allowed",
                "external_effect": request.external_effect,
                "original_modality": request.modality,
                "sensitivity_level": request.sensitivity_level,
                "policy_maturity_level": policy.maturity_level if policy else "",
                "production_certified": policy.production_certified if policy else False,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"multimodal-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _apply_worker_policy_checks(
    *,
    request: MultimodalOperationRequest,
    policy: ModalityWorkerPolicy,
    blocked_reasons: list[str],
    review_reasons: list[str],
    required_controls: list[str],
) -> None:
    if policy.worker_id != request.worker_id:
        blocked_reasons.append("worker_mismatch")
    if policy.capability != request.capability:
        blocked_reasons.append("capability_mismatch")
    if request.modality not in policy.modalities:
        blocked_reasons.append("policy_modality_not_bound")
    if request.operation in policy.forbidden_operations:
        blocked_reasons.append("operation_forbidden")
    if request.operation not in policy.allowed_operations:
        blocked_reasons.append("operation_not_allowlisted")
    if not policy.emits_worker_receipt:
        blocked_reasons.append("worker_receipt_policy_required")
    if not policy.preserves_source_reference:
        blocked_reasons.append("source_reference_preservation_policy_required")
    if request.sensitivity_level not in policy.allowed_sensitive_levels:
        blocked_reasons.append("sensitivity_level_not_allowed")
    required_controls.extend(policy.required_controls)
    _apply_sensitive_data_controls(request, review_reasons, required_controls)
    _apply_policy_evidence_requirements(request, policy, review_reasons)
    if request.external_effect or request.operation in EXTERNAL_SIDE_EFFECT_OPERATIONS:
        _apply_external_effect_controls(
            request=request,
            policy=policy,
            blocked_reasons=blocked_reasons,
            review_reasons=review_reasons,
            required_controls=required_controls,
        )


def _apply_sensitive_data_controls(
    request: MultimodalOperationRequest,
    review_reasons: list[str],
    required_controls: list[str],
) -> None:
    if request.sensitivity_level not in {"confidential", "restricted"}:
        return
    required_controls.append("pii_redaction")
    if not _has_evidence(request.evidence_refs, ("redaction", "pii_redaction")):
        review_reasons.append("pii_redaction_evidence_required")


def _apply_policy_evidence_requirements(
    request: MultimodalOperationRequest,
    policy: ModalityWorkerPolicy,
    review_reasons: list[str],
) -> None:
    missing_refs = sorted(set(policy.required_evidence_refs) - set(request.evidence_refs))
    if missing_refs:
        review_reasons.append("required_evidence_refs_missing")


def _apply_external_effect_controls(
    *,
    request: MultimodalOperationRequest,
    policy: ModalityWorkerPolicy,
    blocked_reasons: list[str],
    review_reasons: list[str],
    required_controls: list[str],
) -> None:
    required_controls.extend(EXTERNAL_EFFECT_CONTROLS)
    if not policy.external_effects_allowed:
        blocked_reasons.append("external_effect_not_allowed")
    if not policy.production_certified:
        blocked_reasons.append("production_certification_required")
    if MATURITY_RANK[policy.maturity_level] < MATURITY_RANK["C6"]:
        blocked_reasons.append("capability_maturity_below_C6")
    if not _has_evidence(request.evidence_refs, ("approval", "approval:")):
        review_reasons.append("approval_evidence_required")
    if not _has_evidence(
        request.evidence_refs,
        ("signed_worker_response", "worker:signed", "signed-worker"),
    ):
        review_reasons.append("signed_worker_response_required")
    if not _has_evidence(
        request.evidence_refs,
        ("live_write_receipt", "live-write", "live_write"),
    ):
        review_reasons.append("live_write_receipt_required")


def _apply_source_checks(
    request: MultimodalOperationRequest,
    blocked_reasons: list[str],
) -> None:
    if not request.input_hash:
        blocked_reasons.append("input_hash_required")
    if not request.source_ref:
        blocked_reasons.append("source_ref_required")
    if not request.source_hash:
        blocked_reasons.append("source_hash_required")


def _apply_evidence_checks(
    request: MultimodalOperationRequest,
    blocked_reasons: list[str],
) -> None:
    if not request.evidence_refs:
        blocked_reasons.append("evidence_refs_required")


def _status(blocked_reasons: list[str], review_reasons: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if review_reasons:
        return "requires_review"
    return "allowed"


def _has_evidence(evidence_refs: list[str], needles: tuple[str, ...]) -> bool:
    normalized_refs = [ref.lower() for ref in evidence_refs]
    return any(
        needle.lower() in evidence_ref
        for needle in needles
        for evidence_ref in normalized_refs
    )


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _default_clock() -> str:
    return "1970-01-01T00:00:00+00:00"
