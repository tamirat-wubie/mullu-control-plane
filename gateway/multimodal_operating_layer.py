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
from typing import Any, Mapping

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
    "unknown",
)
SENSITIVITY_LEVELS = ("public", "internal", "confidential", "restricted")
RECEIPT_STATUSES = ("allowed", "blocked", "requires_review")
MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")
MATURITY_RANK = {level: index for index, level in enumerate(MATURITY_LEVELS)}
EXTERNAL_SIDE_EFFECT_OPERATIONS = frozenset(
    {
        "send_external",
        "external_message_send",
        "send_with_approval",
        "send_invite",
        "schedule",
        "reschedule",
        "submit",
        "submit_external",
        "credentialed_write",
        "provider_write",
        "publish",
        "export_external",
    }
)
BASE_CONTROLS = ("tenant_binding", "source_reference", "worker_receipt", "terminal_closure")
MULTIMODAL_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:multimodal-operation-receipt:1"


@dataclass(frozen=True, slots=True)
class MultimodalOperationRequest:
    """One modality-bound operation request before worker dispatch."""

    request_id: str
    tenant_id: str
    command_id: str
    capability_id: str
    modality: str
    operation: str
    source_ref: str = ""
    source_hash: str = ""
    sensitivity: str = "internal"
    evidence_refs: tuple[str, ...] = ()
    declared_controls: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.modality, "modality")
        _require_text(self.operation, "operation")
        if self.sensitivity not in SENSITIVITY_LEVELS:
            raise ValueError("sensitivity_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "declared_controls", _normalize_text_tuple(self.declared_controls, "declared_controls", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ModalityWorkerPolicy:
    """Policy and certification envelope for one modality worker family."""

    policy_id: str
    modality: str
    worker_plane: str
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...] = ()
    side_effect_operations: tuple[str, ...] = ()
    external_effects_allowed: bool = False
    receipt_required: bool = True
    preserve_source_reference: bool = True
    sandbox_required: bool = True
    pii_redaction_required: bool = False
    signed_worker_response_required: bool = True
    production_certified: bool = False
    maturity_level: str = "C3"
    receipt_schema_ref: str = MULTIMODAL_RECEIPT_SCHEMA_REF
    policy_refs: tuple[str, ...] = ("policy:tenant-boundary", "policy:receipt-required")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.policy_id, "policy_id")
        _require_text(self.modality, "modality")
        _require_text(self.worker_plane, "worker_plane")
        if self.modality not in MODALITIES:
            raise ValueError("policy_modality_invalid")
        if self.maturity_level not in MATURITY_LEVELS:
            raise ValueError("maturity_level_invalid")
        object.__setattr__(self, "allowed_operations", _normalize_text_tuple(self.allowed_operations, "allowed_operations"))
        object.__setattr__(self, "forbidden_operations", _normalize_text_tuple(self.forbidden_operations, "forbidden_operations", allow_empty=True))
        object.__setattr__(self, "side_effect_operations", _normalize_text_tuple(self.side_effect_operations, "side_effect_operations", allow_empty=True))
        object.__setattr__(self, "policy_refs", _normalize_text_tuple(self.policy_refs, "policy_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class MultimodalOperationReceipt:
    """Deterministic receipt for one multimodal operation admission decision."""

    receipt_id: str
    request_id: str
    tenant_id: str
    command_id: str
    capability_id: str
    modality: str
    operation: str
    sensitivity: str
    status: str
    reason: str
    worker_plane: str
    policy_id: str
    source_ref: str
    source_hash: str
    evidence_refs: tuple[str, ...]
    required_controls: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]
    policy_refs: tuple[str, ...]
    receipt_schema_ref: str
    worker_receipt_required: bool
    source_reference_preserved: bool
    sandbox_required: bool
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in RECEIPT_STATUSES:
            raise ValueError("receipt_status_invalid")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "required_controls", tuple(self.required_controls))
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "review_reasons", tuple(self.review_reasons))
        object.__setattr__(self, "policy_refs", tuple(self.policy_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.terminal_closure_required is not True:
            raise ValueError("multimodal_receipt_requires_terminal_closure")
        if self.worker_receipt_required is not True:
            raise ValueError("multimodal_receipt_requires_worker_receipt")
        if self.source_reference_preserved is not True:
            raise ValueError("source_reference_preservation_required")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-schema compatible projection."""
        return _json_ready(asdict(self))


class MultimodalOperatingLayer:
    """Governed pre-dispatch evaluator for multimodal worker operations."""

    def __init__(self, policies: Mapping[str, ModalityWorkerPolicy] | None = None) -> None:
        resolved = {policy.modality: policy for policy in default_multimodal_worker_policies()}
        if policies is not None:
            for modality, policy in policies.items():
                if modality != policy.modality:
                    raise ValueError("policy_modality_key_mismatch")
                resolved[modality] = policy
        self._policies = dict(resolved)

    def evaluate(self, request: MultimodalOperationRequest) -> MultimodalOperationReceipt:
        """Evaluate one request and emit an admission receipt."""
        policy = self._policies.get(request.modality)
        blocked_reasons: list[str] = []
        review_reasons: list[str] = []

        if policy is None:
            blocked_reasons.append("modality_not_registered")
            return _stamp_receipt(_receipt_from_decision(
                request=request,
                policy=None,
                status="blocked",
                reason="modality_not_registered",
                required_controls=list(BASE_CONTROLS),
                blocked_reasons=blocked_reasons,
                review_reasons=review_reasons,
            ))

        required_controls = _required_controls(policy)
        if request.operation in policy.forbidden_operations:
            blocked_reasons.append("operation_forbidden")
        if request.operation not in policy.allowed_operations:
            blocked_reasons.append("operation_not_allowlisted")
        if not policy.receipt_required:
            blocked_reasons.append("worker_receipt_policy_required")
        if not policy.preserve_source_reference:
            blocked_reasons.append("source_reference_preservation_policy_required")
        if not request.source_ref:
            blocked_reasons.append("source_ref_required")
        if not request.source_hash:
            blocked_reasons.append("source_hash_required")
        if not request.evidence_refs:
            blocked_reasons.append("evidence_refs_required")

        if _sensitive(request, policy):
            _append_unique(required_controls, "pii_redaction")
            if not _has_control_or_evidence(request, "pii_redaction"):
                review_reasons.append("pii_redaction_evidence_required")

        if _is_external_effect(request.operation, policy):
            _append_unique(required_controls, "approval")
            _append_unique(required_controls, "signed_worker_response")
            _append_unique(required_controls, "live_write_receipt")
            if not policy.external_effects_allowed:
                blocked_reasons.append("external_effect_not_allowed")
            if not policy.production_certified:
                blocked_reasons.append("production_certification_required")
            if MATURITY_RANK[policy.maturity_level] < MATURITY_RANK["C6"]:
                blocked_reasons.append("capability_maturity_below_C6")
            if not _has_control_or_evidence(request, "approval"):
                review_reasons.append("approval_evidence_required")
            if policy.signed_worker_response_required and not _has_control_or_evidence(request, "signed_worker_response"):
                review_reasons.append("signed_worker_response_evidence_required")
            if not _has_control_or_evidence(request, "live_write_receipt"):
                review_reasons.append("live_write_receipt_evidence_required")

        blocked_reasons = list(dict.fromkeys(blocked_reasons))
        review_reasons = list(dict.fromkeys(review_reasons))
        if blocked_reasons:
            status = "blocked"
            reason = blocked_reasons[0]
        elif review_reasons:
            status = "requires_review"
            reason = review_reasons[0]
        else:
            status = "allowed"
            reason = "operation_allowed"
        return _stamp_receipt(_receipt_from_decision(
            request=request,
            policy=policy,
            status=status,
            reason=reason,
            required_controls=required_controls,
            blocked_reasons=blocked_reasons,
            review_reasons=review_reasons,
        ))

    def policy_for(self, modality: str) -> ModalityWorkerPolicy | None:
        """Return the registered policy for one modality."""
        return self._policies.get(modality)


def default_multimodal_worker_policies() -> tuple[ModalityWorkerPolicy, ...]:
    """Return conservative built-in policies for governed modalities."""
    return (
        _policy("text", "core", ("classify", "summarize", "extract_claims", "redact_pii"), ("send_external", "publish")),
        _policy("pdf", "document", ("parse", "extract_text", "extract_fields", "extract_tables", "summarize"), ("send_external", "submit_external")),
        _policy("spreadsheet", "document", ("parse", "extract_tables", "validate_formula", "analyze", "generate"), ("send_external", "submit_external")),
        _policy("image", "vision", ("inspect", "extract_text", "classify", "redact"), ("send_external", "publish")),
        _policy(
            "voice",
            "voice",
            ("transcribe", "summarize", "intent_classification", "extract_action_items"),
            ("call_external", "send_external"),
            pii_redaction_required=True,
        ),
        _policy("screen", "browser", ("screenshot", "extract_text", "inspect"), ("credentialed_write", "send_external")),
        _policy("browser", "browser", ("read_page", "screenshot", "extract_text", "open_url"), ("click", "type", "submit", "credentialed_write", "unapproved_url")),
        _policy("email", "email/calendar", ("read", "search", "draft", "classify", "reply_suggest"), ("send_external", "external_message_send")),
        _policy("calendar", "email/calendar", ("read", "conflict_check", "draft_event"), ("send_invite", "schedule", "reschedule")),
        _policy("forms", "document", ("parse", "extract_fields", "validate"), ("submit", "submit_external")),
        _policy("video_frame", "vision", ("inspect", "extract_text", "classify"), ("send_external", "publish")),
    )


def _policy(
    modality: str,
    worker_plane: str,
    allowed_operations: tuple[str, ...],
    forbidden_operations: tuple[str, ...],
    *,
    pii_redaction_required: bool = False,
) -> ModalityWorkerPolicy:
    return ModalityWorkerPolicy(
        policy_id=f"multimodal-policy:{modality}:v1",
        modality=modality,
        worker_plane=worker_plane,
        allowed_operations=allowed_operations,
        forbidden_operations=forbidden_operations,
        side_effect_operations=tuple(operation for operation in forbidden_operations if operation in EXTERNAL_SIDE_EFFECT_OPERATIONS),
        pii_redaction_required=pii_redaction_required,
        production_certified=False,
        maturity_level="C3",
    )


def _receipt_from_decision(
    *,
    request: MultimodalOperationRequest,
    policy: ModalityWorkerPolicy | None,
    status: str,
    reason: str,
    required_controls: list[str],
    blocked_reasons: list[str],
    review_reasons: list[str],
) -> MultimodalOperationReceipt:
    return MultimodalOperationReceipt(
        receipt_id="pending",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        command_id=request.command_id,
        capability_id=request.capability_id,
        modality=request.modality if policy else "unknown",
        operation=request.operation,
        sensitivity=request.sensitivity,
        status=status,
        reason=reason,
        worker_plane=policy.worker_plane if policy else "",
        policy_id=policy.policy_id if policy else "",
        source_ref=request.source_ref,
        source_hash=request.source_hash,
        evidence_refs=request.evidence_refs,
        required_controls=tuple(dict.fromkeys(required_controls)),
        blocked_reasons=tuple(blocked_reasons),
        review_reasons=tuple(review_reasons),
        policy_refs=policy.policy_refs if policy else (),
        receipt_schema_ref=policy.receipt_schema_ref if policy else MULTIMODAL_RECEIPT_SCHEMA_REF,
        worker_receipt_required=True,
        source_reference_preserved=True,
        sandbox_required=policy.sandbox_required if policy else True,
        terminal_closure_required=True,
        metadata={
            "receipt_is_not_terminal_closure": True,
            "policy_maturity_level": policy.maturity_level if policy else "",
            "production_certified": policy.production_certified if policy else False,
            "external_effects_allowed": policy.external_effects_allowed if policy else False,
            "requested_modality": request.modality,
        },
    )


def _stamp_receipt(receipt: MultimodalOperationReceipt) -> MultimodalOperationReceipt:
    payload = asdict(replace(receipt, receipt_id="pending", receipt_hash=""))
    receipt_hash = canonical_hash(payload)
    return replace(receipt, receipt_id=f"multimodal-receipt-{receipt_hash[:16]}", receipt_hash=receipt_hash)


def _required_controls(policy: ModalityWorkerPolicy) -> list[str]:
    controls = list(BASE_CONTROLS)
    if policy.signed_worker_response_required:
        _append_unique(controls, "signed_worker_response")
    if policy.sandbox_required:
        _append_unique(controls, "sandbox")
    if policy.pii_redaction_required:
        _append_unique(controls, "pii_redaction")
    return controls


def _sensitive(request: MultimodalOperationRequest, policy: ModalityWorkerPolicy) -> bool:
    return policy.pii_redaction_required or request.sensitivity in {"confidential", "restricted"}


def _is_external_effect(operation: str, policy: ModalityWorkerPolicy) -> bool:
    return operation in EXTERNAL_SIDE_EFFECT_OPERATIONS or operation in policy.side_effect_operations


def _has_control_or_evidence(request: MultimodalOperationRequest, control_name: str) -> bool:
    return _has_token(request.declared_controls, control_name) or _has_token(request.evidence_refs, control_name)


def _has_token(values: tuple[str, ...], token: str) -> bool:
    prefixes = (f"{token}:", f"{token}#", f"{token}/")
    return any(value == token or value.startswith(prefixes) for value in values)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple | list):
        raise ValueError(f"{field_name}_must_be_array")
    normalized = tuple(str(value).strip() for value in values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if any(not value for value in normalized):
        raise ValueError(f"{field_name}_item_required")
    return normalized


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value
