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
  - Blocked or failed worker results remain observable governed outcomes.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature


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


def build_adapter_worker_clients_from_env() -> AdapterWorkerClients:
    """Build all configured adapter worker clients from environment."""
    return AdapterWorkerClients(
        browser=build_browser_worker_client_from_env(),
        document=build_document_worker_client_from_env(),
        voice=build_voice_worker_client_from_env(),
        email_calendar=build_email_calendar_worker_client_from_env(),
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
    capability_id = _require_text(str(payload.get("capability_id", "")), f"{adapter_id} capability_id")
    return transport.submit(
        payload,
        expected_request_id=request_id,
        expected_capability_id=capability_id,
    )


def _adapter_response_from_mapping(
    raw: dict[str, Any],
    *,
    adapter_id: str,
    expected_request_id: str,
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
    _require_text(str(receipt.get("verification_status", "")), f"{adapter_id} receipt verification_status")
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list | tuple) or not evidence_refs:
        raise RuntimeError(f"{adapter_id} worker receipt requires evidence refs")
    return AdapterWorkerResponse(
        request_id=request_id,
        status=status,
        result=dict(result),
        receipt=dict(receipt),
        error=str(raw.get("error", "")),
        raw=dict(raw),
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
