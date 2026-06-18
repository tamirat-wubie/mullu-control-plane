"""Gateway Adapter Worker Clients - signed governed adapter dispatch.

Purpose: Provides typed HTTP clients for browser, document, voice, and
    communication adapter workers without exposing raw worker endpoints as
    gateway capabilities.
Governance scope: signed request transport, signed response validation,
    capability/tenant receipt validation, and fail-closed configuration.
Dependencies: gateway capability signing helpers and adapter worker contracts.
Invariants:
  - Worker URL and signing secret must be configured together.
  - Every response signature is verified before response parsing.
  - Every response must carry a receipt for the requested capability.
  - External effect success requires dry-run proof or provider receipt evidence.
  - Blocked or failed worker results remain observable governed outcomes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature
from gateway.proxy_policy import assert_proxy_environment_allowed


ADAPTER_EFFECT_PLAN_ONLY = "plan_only"
ADAPTER_EFFECT_DRY_RUN = "dry_run"
ADAPTER_EFFECT_LIVE_PROVIDER = "live_provider"
ADAPTER_EFFECT_MODES = (
    ADAPTER_EFFECT_PLAN_ONLY,
    ADAPTER_EFFECT_DRY_RUN,
    ADAPTER_EFFECT_LIVE_PROVIDER,
)
ADAPTER_EXTERNAL_WRITE_CAPABILITIES = frozenset(
    {
        "browser.submit",
        "email.send",
        "email.send.with_approval",
        "calendar.schedule",
        "calendar.reschedule",
        "calendar.invite",
        "messaging.sms.send.with_approval",
        "messaging.chat.send.with_approval",
        "phone.call.place.with_approval",
        "phone.call.transfer.with_approval",
        "phone.call.terminate",
    }
)
ADAPTER_EFFECT_RECEIPT_FIELDS = frozenset(
    {
        "effect_mode",
        "external_effect_claimed",
        "external_write",
        "external_send",
        "external_call",
        "provider_receipt_hash",
        "provider_receipt_ref",
        "idempotency_key",
        "rollback_or_recovery_ref",
        "replay_or_rollback_ref",
        "forbidden_effects_observed",
        "secret_values_disclosed",
    }
)
SHA256_RECEIPT_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AdapterExternalEffectEvidence:
    """Worker receipt evidence for dry-run or live-provider effect claims."""

    request_id: str
    tenant_id: str
    capability_id: str
    status: str
    verification_status: str
    effect_mode: str = ADAPTER_EFFECT_PLAN_ONLY
    external_effect_claimed: bool = False
    provider_receipt_hash: str = ""
    provider_receipt_ref: str = ""
    idempotency_key: str = ""
    rollback_or_recovery_ref: str = ""
    evidence_refs: tuple[str, ...] = ()
    effect_boundary_declared: bool = False
    approval_ref: str = ""
    forbidden_effects_observed: bool = False
    secret_values_disclosed: bool = False


@dataclass(frozen=True, slots=True)
class AdapterExternalEffectAssessment:
    """Deterministic decision for adapter worker external-effect evidence."""

    request_id: str
    tenant_id: str
    capability_id: str
    status: str
    verification_status: str
    effect_mode: str
    external_effect_claimed: bool
    provider_receipt_hash: str
    provider_receipt_ref: str
    idempotency_key: str
    rollback_or_recovery_ref: str
    evidence_refs: tuple[str, ...]
    effect_boundary_declared: bool
    approval_ref: str
    forbidden_effects_observed: bool
    secret_values_disclosed: bool
    execution_success_claim_allowed: bool
    plan_only: bool
    blocked_reasons: tuple[str, ...]
    network_call_performed: bool = False
    request_authentication_performed: bool = False


@dataclass(frozen=True, slots=True)
class AdapterWorkerResponse:
    """Validated response returned by a restricted adapter worker."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: dict[str, Any]
    error: str
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AdapterWorkerClients:
    """Optional configured worker clients for adapter-backed planes."""

    browser: BrowserWorkerClient | None = None
    document: DocumentWorkerClient | None = None
    voice: VoiceWorkerClient | None = None
    email_calendar: EmailCalendarWorkerClient | None = None
    messaging: MessagingWorkerClient | None = None
    phone: PhoneWorkerClient | None = None


class SignedAdapterWorkerTransport:
    """Signed HTTP transport for one adapter worker endpoint."""

    def __init__(
        self,
        *,
        adapter_id: str,
        endpoint_url: str,
        signing_secret: str,
        request_signature_header: str,
        response_signature_header: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._adapter_id = _require_text(adapter_id, "adapter_id")
        self._endpoint_url = _require_text(endpoint_url, f"{adapter_id} worker endpoint")
        self._signing_secret = _require_text(signing_secret, f"{adapter_id} worker signing secret")
        self._request_signature_header = _require_text(request_signature_header, "request_signature_header")
        self._response_signature_header = _require_text(response_signature_header, "response_signature_header")
        if timeout_seconds <= 0:
            raise ValueError(f"{adapter_id} worker timeout must be > 0")
        self._timeout_seconds = timeout_seconds

    def submit(
        self,
        payload: Mapping[str, Any],
        *,
        expected_request_id: str,
        expected_tenant_id: str,
        expected_capability_id: str,
    ) -> AdapterWorkerResponse:
        """Submit one adapter request and validate the signed worker response."""
        body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = sign_capability_payload(body, self._signing_secret)
        http_request = urllib.request.Request(
            self._endpoint_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                self._request_signature_header: signature,
            },
            method="POST",
        )
        try:
            assert_proxy_environment_allowed()
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
                response_signature = response.headers.get(self._response_signature_header, "")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self._adapter_id} worker transport failed: {type(exc).__name__}") from exc
        if not verify_capability_signature(response_body, response_signature, self._signing_secret):
            raise RuntimeError(f"{self._adapter_id} worker response signature invalid")
        try:
            raw_response = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{self._adapter_id} worker returned invalid JSON") from exc
        if not isinstance(raw_response, dict):
            raise RuntimeError(f"{self._adapter_id} worker response must be an object")
        return _adapter_response_from_mapping(
            raw_response,
            adapter_id=self._adapter_id,
            expected_request_id=expected_request_id,
            expected_tenant_id=expected_tenant_id,
            expected_capability_id=expected_capability_id,
        )


class BrowserWorkerClient:
    """Client for the restricted browser worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one browser action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="browser")


class DocumentWorkerClient:
    """Client for the restricted document worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one document/data action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="document")


class VoiceWorkerClient:
    """Client for the restricted voice worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one voice action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="voice")


class EmailCalendarWorkerClient:
    """Client for the restricted email/calendar worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one email/calendar action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="email/calendar")


class MessagingWorkerClient:
    """Client for the restricted messaging worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one messaging action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="messaging")


class PhoneWorkerClient:
    """Client for the restricted phone worker."""

    def __init__(self, transport: SignedAdapterWorkerTransport) -> None:
        self._transport = transport

    def execute(self, payload: Mapping[str, Any]) -> AdapterWorkerResponse:
        """Execute one phone action through the signed worker."""
        return _execute_with_transport(self._transport, payload, adapter_id="phone")


def build_adapter_worker_clients_from_env() -> AdapterWorkerClients:
    """Build all configured adapter worker clients from environment."""
    return AdapterWorkerClients(
        browser=build_browser_worker_client_from_env(),
        document=build_document_worker_client_from_env(),
        voice=build_voice_worker_client_from_env(),
        email_calendar=build_email_calendar_worker_client_from_env(),
        messaging=build_messaging_worker_client_from_env(),
        phone=build_phone_worker_client_from_env(),
    )


def build_browser_worker_client_from_env() -> BrowserWorkerClient | None:
    """Build the browser worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="browser",
        url_env="MULLU_BROWSER_WORKER_URL",
        secret_env="MULLU_BROWSER_WORKER_SECRET",
        timeout_env="MULLU_BROWSER_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
    )
    return BrowserWorkerClient(transport) if transport is not None else None


def build_document_worker_client_from_env() -> DocumentWorkerClient | None:
    """Build the document worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="document",
        url_env="MULLU_DOCUMENT_WORKER_URL",
        secret_env="MULLU_DOCUMENT_WORKER_SECRET",
        timeout_env="MULLU_DOCUMENT_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Document-Signature",
        response_signature_header="X-Mullu-Document-Response-Signature",
    )
    return DocumentWorkerClient(transport) if transport is not None else None


def build_voice_worker_client_from_env() -> VoiceWorkerClient | None:
    """Build the voice worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="voice",
        url_env="MULLU_VOICE_WORKER_URL",
        secret_env="MULLU_VOICE_WORKER_SECRET",
        timeout_env="MULLU_VOICE_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Voice-Signature",
        response_signature_header="X-Mullu-Voice-Response-Signature",
    )
    return VoiceWorkerClient(transport) if transport is not None else None


def build_email_calendar_worker_client_from_env() -> EmailCalendarWorkerClient | None:
    """Build the email/calendar worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="email/calendar",
        url_env="MULLU_EMAIL_CALENDAR_WORKER_URL",
        secret_env="MULLU_EMAIL_CALENDAR_WORKER_SECRET",
        timeout_env="MULLU_EMAIL_CALENDAR_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Email-Calendar-Signature",
        response_signature_header="X-Mullu-Email-Calendar-Response-Signature",
    )
    return EmailCalendarWorkerClient(transport) if transport is not None else None


def build_messaging_worker_client_from_env() -> MessagingWorkerClient | None:
    """Build the messaging worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="messaging",
        url_env="MULLU_MESSAGING_WORKER_URL",
        secret_env="MULLU_MESSAGING_WORKER_SECRET",
        timeout_env="MULLU_MESSAGING_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Messaging-Signature",
        response_signature_header="X-Mullu-Messaging-Response-Signature",
    )
    return MessagingWorkerClient(transport) if transport is not None else None


def build_phone_worker_client_from_env() -> PhoneWorkerClient | None:
    """Build the phone worker client from environment configuration."""
    transport = _build_transport_from_env(
        adapter_id="phone",
        url_env="MULLU_PHONE_WORKER_URL",
        secret_env="MULLU_PHONE_WORKER_SECRET",
        timeout_env="MULLU_PHONE_WORKER_TIMEOUT_SECONDS",
        request_signature_header="X-Mullu-Phone-Signature",
        response_signature_header="X-Mullu-Phone-Response-Signature",
    )
    return PhoneWorkerClient(transport) if transport is not None else None


def _build_transport_from_env(
    *,
    adapter_id: str,
    url_env: str,
    secret_env: str,
    timeout_env: str,
    request_signature_header: str,
    response_signature_header: str,
) -> SignedAdapterWorkerTransport | None:
    endpoint_url = os.environ.get(url_env, "").strip()
    signing_secret = os.environ.get(secret_env, "").strip()
    if not endpoint_url and not signing_secret:
        return None
    if endpoint_url and not signing_secret:
        raise ValueError(f"{adapter_id} worker signing secret is required")
    if signing_secret and not endpoint_url:
        raise ValueError(f"{adapter_id} worker endpoint is required")
    timeout_seconds = float(os.environ.get(timeout_env, "10.0"))
    return SignedAdapterWorkerTransport(
        adapter_id=adapter_id,
        endpoint_url=endpoint_url,
        signing_secret=signing_secret,
        request_signature_header=request_signature_header,
        response_signature_header=response_signature_header,
        timeout_seconds=timeout_seconds,
    )


def _execute_with_transport(
    transport: SignedAdapterWorkerTransport,
    payload: Mapping[str, Any],
    *,
    adapter_id: str,
) -> AdapterWorkerResponse:
    request_id = _require_text(str(payload.get("request_id", "")), f"{adapter_id} request_id")
    tenant_id = _require_text(str(payload.get("tenant_id", "")), f"{adapter_id} tenant_id")
    capability_id = _require_text(str(payload.get("capability_id", "")), f"{adapter_id} capability_id")
    return transport.submit(
        payload,
        expected_request_id=request_id,
        expected_tenant_id=tenant_id,
        expected_capability_id=capability_id,
    )


def _adapter_response_from_mapping(
    raw: dict[str, Any],
    *,
    adapter_id: str,
    expected_request_id: str,
    expected_tenant_id: str,
    expected_capability_id: str,
) -> AdapterWorkerResponse:
    request_id = _require_text(str(raw.get("request_id", "")), f"{adapter_id} response request_id")
    if request_id != expected_request_id:
        raise RuntimeError(f"{adapter_id} worker response request mismatch")
    status = _require_text(str(raw.get("status", "")), f"{adapter_id} response status")
    result = raw.get("result", {})
    if not isinstance(result, dict):
        raise RuntimeError(f"{adapter_id} worker result must be an object")
    receipt = raw.get("receipt")
    if not isinstance(receipt, dict):
        raise RuntimeError(f"{adapter_id} worker response requires receipt")
    receipt_capability = _require_text(
        str(receipt.get("capability_id", "")),
        f"{adapter_id} receipt capability_id",
    )
    if receipt_capability != expected_capability_id:
        raise RuntimeError(f"{adapter_id} worker receipt capability mismatch")
    receipt_request_id = _require_text(str(receipt.get("request_id", "")), f"{adapter_id} receipt request_id")
    if receipt_request_id != expected_request_id:
        raise RuntimeError(f"{adapter_id} worker receipt request mismatch")
    receipt_tenant_id = _require_text(str(receipt.get("tenant_id", "")), f"{adapter_id} receipt tenant_id")
    if receipt_tenant_id != expected_tenant_id:
        raise RuntimeError(f"{adapter_id} worker receipt tenant mismatch")
    _require_text(str(receipt.get("verification_status", "")), f"{adapter_id} receipt verification_status")
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list | tuple) or not evidence_refs:
        raise RuntimeError(f"{adapter_id} worker receipt requires evidence refs")
    if status.strip().lower() == "succeeded" and _receipt_requires_external_effect_boundary(
        receipt,
        expected_capability_id=expected_capability_id,
    ):
        try:
            assessment = assess_adapter_external_effect_receipt(
                receipt,
                status=status,
                adapter_id=adapter_id,
            )
        except ValueError as exc:
            raise RuntimeError(f"{adapter_id} worker effect receipt invalid:{exc}") from exc
        if assessment.blocked_reasons:
            raise RuntimeError(f"{adapter_id} worker effect receipt invalid:{assessment.blocked_reasons[0]}")
    return AdapterWorkerResponse(
        request_id=request_id,
        status=status,
        result=dict(result),
        receipt=dict(receipt),
        error=str(raw.get("error", "")),
        raw=dict(raw),
    )


def assess_adapter_external_effect_evidence(
    evidence: AdapterExternalEffectEvidence,
) -> AdapterExternalEffectAssessment:
    """Assess whether a worker receipt can claim dry-run or provider execution success."""
    request_id = _require_text(evidence.request_id, "adapter effect request_id")
    tenant_id = _require_text(evidence.tenant_id, "adapter effect tenant_id")
    capability_id = _require_text(evidence.capability_id, "adapter effect capability_id")
    status = _require_text(evidence.status, "adapter effect status").strip().lower()
    verification_status = _require_text(
        evidence.verification_status,
        "adapter effect verification_status",
    ).strip().lower()
    effect_mode = _require_text(evidence.effect_mode, "adapter effect_mode").strip().lower()
    if effect_mode not in ADAPTER_EFFECT_MODES:
        raise ValueError("effect_mode_invalid")
    if not isinstance(evidence.external_effect_claimed, bool):
        raise ValueError("external_effect_claimed_invalid")
    if not isinstance(evidence.effect_boundary_declared, bool):
        raise ValueError("effect_boundary_declared_invalid")
    if not isinstance(evidence.forbidden_effects_observed, bool):
        raise ValueError("forbidden_effects_observed_invalid")
    if not isinstance(evidence.secret_values_disclosed, bool):
        raise ValueError("secret_values_disclosed_invalid")

    provider_receipt_hash = _optional_receipt_text(
        evidence.provider_receipt_hash,
        "provider_receipt_hash",
    )
    provider_receipt_ref = _optional_receipt_text(
        evidence.provider_receipt_ref,
        "provider_receipt_ref",
    )
    idempotency_key = _optional_receipt_text(evidence.idempotency_key, "idempotency_key")
    rollback_or_recovery_ref = _optional_receipt_text(
        evidence.rollback_or_recovery_ref,
        "rollback_or_recovery_ref",
    )
    approval_ref = _optional_receipt_text(evidence.approval_ref, "approval_ref")
    evidence_refs = _normalize_evidence_refs(evidence.evidence_refs)

    blocked_reasons: list[str] = []
    external_write_capability = adapter_capability_requires_external_effect_evidence(capability_id)
    if external_write_capability and not evidence.effect_boundary_declared:
        blocked_reasons.append("external_effect_boundary_required")
    if evidence.forbidden_effects_observed:
        blocked_reasons.append("forbidden_effects_observed")
    if evidence.secret_values_disclosed:
        blocked_reasons.append("secret_values_disclosed")
    if effect_mode == ADAPTER_EFFECT_PLAN_ONLY:
        if evidence.external_effect_claimed:
            blocked_reasons.append("plan_only_external_effect_claim_forbidden")
        if external_write_capability and status == "succeeded":
            blocked_reasons.append("external_effect_success_evidence_required")
        execution_success_claim_allowed = False
    elif effect_mode == ADAPTER_EFFECT_DRY_RUN:
        _append_common_execution_blockers(
            blocked_reasons,
            status=status,
            verification_status=verification_status,
            evidence_refs=evidence_refs,
            idempotency_key=idempotency_key,
            rollback_or_recovery_ref=rollback_or_recovery_ref,
        )
        if evidence.external_effect_claimed:
            blocked_reasons.append("dry_run_external_effect_claim_forbidden")
        execution_success_claim_allowed = not blocked_reasons
    else:
        _append_common_execution_blockers(
            blocked_reasons,
            status=status,
            verification_status=verification_status,
            evidence_refs=evidence_refs,
            idempotency_key=idempotency_key,
            rollback_or_recovery_ref=rollback_or_recovery_ref,
        )
        if not evidence.external_effect_claimed:
            blocked_reasons.append("external_effect_claim_required")
        if not provider_receipt_hash:
            blocked_reasons.append("provider_receipt_hash_required")
        elif not SHA256_RECEIPT_REF_RE.fullmatch(provider_receipt_hash):
            blocked_reasons.append("provider_receipt_hash_invalid")
        if not provider_receipt_ref:
            blocked_reasons.append("provider_receipt_ref_required")
        if external_write_capability and not approval_ref:
            blocked_reasons.append("approval_ref_required")
        execution_success_claim_allowed = not blocked_reasons

    return AdapterExternalEffectAssessment(
        request_id=request_id,
        tenant_id=tenant_id,
        capability_id=capability_id,
        status=status,
        verification_status=verification_status,
        effect_mode=effect_mode,
        external_effect_claimed=evidence.external_effect_claimed,
        provider_receipt_hash=provider_receipt_hash,
        provider_receipt_ref=provider_receipt_ref,
        idempotency_key=idempotency_key,
        rollback_or_recovery_ref=rollback_or_recovery_ref,
        evidence_refs=evidence_refs,
        effect_boundary_declared=evidence.effect_boundary_declared,
        approval_ref=approval_ref,
        forbidden_effects_observed=evidence.forbidden_effects_observed,
        secret_values_disclosed=evidence.secret_values_disclosed,
        execution_success_claim_allowed=execution_success_claim_allowed,
        plan_only=effect_mode == ADAPTER_EFFECT_PLAN_ONLY,
        blocked_reasons=tuple(blocked_reasons),
        network_call_performed=False,
        request_authentication_performed=False,
    )


def adapter_capability_requires_external_effect_evidence(capability_id: str) -> bool:
    """Return whether a capability must carry explicit external-effect evidence."""
    return str(capability_id).strip() in ADAPTER_EXTERNAL_WRITE_CAPABILITIES


def assess_adapter_external_effect_receipt(
    receipt: Mapping[str, Any],
    *,
    status: str,
    adapter_id: str,
) -> AdapterExternalEffectAssessment:
    """Assess a worker receipt with inferred external-effect boundary fields."""
    return assess_adapter_external_effect_evidence(
        _adapter_external_effect_evidence_from_receipt(
            receipt,
            status=status,
            adapter_id=adapter_id,
        )
    )


def _append_common_execution_blockers(
    blocked_reasons: list[str],
    *,
    status: str,
    verification_status: str,
    evidence_refs: tuple[str, ...],
    idempotency_key: str,
    rollback_or_recovery_ref: str,
) -> None:
    if status != "succeeded":
        blocked_reasons.append("adapter_status_not_succeeded")
    if verification_status != "passed":
        blocked_reasons.append("adapter_receipt_verification_not_passed")
    if not evidence_refs:
        blocked_reasons.append("adapter_external_evidence_refs_required")
    if not idempotency_key:
        blocked_reasons.append("idempotency_key_required")
    if not rollback_or_recovery_ref:
        blocked_reasons.append("rollback_or_recovery_ref_required")


def _adapter_external_effect_evidence_from_receipt(
    receipt: Mapping[str, Any],
    *,
    status: str,
    adapter_id: str,
) -> AdapterExternalEffectEvidence:
    effect_boundary_declared = _receipt_declares_external_effect_boundary(receipt)
    observed_external_effect = _receipt_observed_external_effect(receipt)
    default_effect_mode = ADAPTER_EFFECT_LIVE_PROVIDER if observed_external_effect else ADAPTER_EFFECT_PLAN_ONLY
    return AdapterExternalEffectEvidence(
        request_id=_require_text(str(receipt.get("request_id", "")), f"{adapter_id} effect receipt request_id"),
        tenant_id=_require_text(str(receipt.get("tenant_id", "")), f"{adapter_id} effect receipt tenant_id"),
        capability_id=_require_text(
            str(receipt.get("capability_id", "")),
            f"{adapter_id} effect receipt capability_id",
        ),
        status=status,
        verification_status=_require_text(
            str(receipt.get("verification_status", "")),
            f"{adapter_id} effect receipt verification_status",
        ),
        effect_mode=receipt.get("effect_mode", default_effect_mode),
        external_effect_claimed=receipt.get("external_effect_claimed", observed_external_effect),
        provider_receipt_hash=receipt.get("provider_receipt_hash", ""),
        provider_receipt_ref=receipt.get("provider_receipt_ref", ""),
        idempotency_key=receipt.get("idempotency_key", ""),
        rollback_or_recovery_ref=_first_receipt_text(
            receipt,
            (
                "rollback_or_recovery_ref",
                "replay_or_rollback_ref",
                "rollback_ref",
                "rollback_plan_ref",
                "recovery_ref",
            ),
        ),
        evidence_refs=tuple(receipt.get("evidence_refs", ())),
        effect_boundary_declared=effect_boundary_declared,
        approval_ref=_first_receipt_text(receipt, ("approval_ref", "approval_id", "approval_receipt_ref")),
        forbidden_effects_observed=receipt.get("forbidden_effects_observed", False),
        secret_values_disclosed=receipt.get("secret_values_disclosed", False),
    )


def _receipt_requires_external_effect_boundary(
    receipt: Mapping[str, Any],
    *,
    expected_capability_id: str,
) -> bool:
    return (
        _receipt_declares_external_effect_boundary(receipt)
        or adapter_capability_requires_external_effect_evidence(expected_capability_id)
    )


def _receipt_declares_external_effect_boundary(receipt: Mapping[str, Any]) -> bool:
    return any(field_name in receipt for field_name in ADAPTER_EFFECT_RECEIPT_FIELDS)


def _receipt_observed_external_effect(receipt: Mapping[str, Any]) -> bool:
    return any(
        _optional_receipt_bool(receipt.get(field_name, False), field_name)
        for field_name in ("external_write", "external_send", "external_call")
    )


def _first_receipt_text(receipt: Mapping[str, Any], field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        if field_name not in receipt:
            continue
        value = _optional_receipt_text(receipt.get(field_name, ""), field_name)
        if value:
            return value
    return ""


def _optional_receipt_text(value: object, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name}_invalid")
    return value.strip()


def _optional_receipt_bool(value: object, field_name: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}_invalid")
    return value


def _normalize_evidence_refs(raw_evidence_refs: object) -> tuple[str, ...]:
    if not isinstance(raw_evidence_refs, list | tuple):
        raise ValueError("adapter_external_evidence_refs_invalid")
    evidence_refs: list[str] = []
    for evidence_ref in raw_evidence_refs:
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise ValueError("adapter_external_evidence_refs_invalid")
        evidence_refs.append(evidence_ref.strip())
    return tuple(evidence_refs)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
