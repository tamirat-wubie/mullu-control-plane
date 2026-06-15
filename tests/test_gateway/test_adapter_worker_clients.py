"""Tests for signed adapter worker clients.

Purpose: verify browser, document, and voice worker clients preserve governed
transport signatures and receipt validation before dispatch can claim effects.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.adapter_worker_clients import (  # noqa: E402
    AdapterExternalEffectEvidence,
    BrowserWorkerClient,
    EmailCalendarWorkerClient,
    MessagingWorkerClient,
    PhoneWorkerClient,
    SignedAdapterWorkerTransport,
    assess_adapter_external_effect_evidence,
    build_browser_worker_client_from_env,
    build_email_calendar_worker_client_from_env,
    build_messaging_worker_client_from_env,
    build_phone_worker_client_from_env,
)
from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402


def _valid_effect_evidence(**overrides: Any) -> AdapterExternalEffectEvidence:
    payload = {
        "request_id": "effect-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "email.send",
        "status": "succeeded",
        "verification_status": "passed",
        "effect_mode": "live_provider",
        "external_effect_claimed": True,
        "provider_receipt_hash": "sha256:" + ("a" * 64),
        "provider_receipt_ref": "provider://gmail/messages/send/effect-request-1",
        "idempotency_key": "idem-effect-request-1",
        "rollback_or_recovery_ref": "runbook://gmail/send/recovery",
        "evidence_refs": ("adapter_effect:provider-receipt",),
        "effect_boundary_declared": True,
        "approval_ref": "approval-effect-request-1",
        "forbidden_effects_observed": False,
        "secret_values_disclosed": False,
    }
    payload.update(overrides)
    return AdapterExternalEffectEvidence(**payload)


def test_adapter_external_effect_plan_only_does_not_claim_execution_success() -> None:
    assessment = assess_adapter_external_effect_evidence(
        _valid_effect_evidence(
            effect_mode="plan_only",
            status="blocked",
            external_effect_claimed=False,
            provider_receipt_hash="",
            provider_receipt_ref="",
            idempotency_key="",
            rollback_or_recovery_ref="",
            evidence_refs=(),
        )
    )

    assert assessment.plan_only is True
    assert assessment.execution_success_claim_allowed is False
    assert assessment.blocked_reasons == ()
    assert assessment.network_call_performed is False
    assert assessment.request_authentication_performed is False


def test_adapter_external_effect_live_provider_requires_provider_receipt_hash() -> None:
    assessment = assess_adapter_external_effect_evidence(
        _valid_effect_evidence(
            provider_receipt_hash="",
            provider_receipt_ref="",
        )
    )

    assert assessment.execution_success_claim_allowed is False
    assert "provider_receipt_hash_required" in assessment.blocked_reasons
    assert "provider_receipt_ref_required" in assessment.blocked_reasons
    assert assessment.effect_mode == "live_provider"
    assert assessment.evidence_refs == ("adapter_effect:provider-receipt",)


def test_adapter_external_effect_accepts_live_provider_receipt_evidence() -> None:
    assessment = assess_adapter_external_effect_evidence(_valid_effect_evidence())

    assert assessment.execution_success_claim_allowed is True
    assert assessment.blocked_reasons == ()
    assert assessment.provider_receipt_hash == "sha256:" + ("a" * 64)
    assert assessment.provider_receipt_ref == "provider://gmail/messages/send/effect-request-1"
    assert assessment.approval_ref == "approval-effect-request-1"
    assert assessment.network_call_performed is False
    assert assessment.request_authentication_performed is False


def test_adapter_external_effect_rejects_non_boolean_claim() -> None:
    with pytest.raises(ValueError, match="^external_effect_claimed_invalid$") as excinfo:
        assess_adapter_external_effect_evidence(_valid_effect_evidence(external_effect_claimed="yes"))

    assert str(excinfo.value) == "external_effect_claimed_invalid"
    assert _valid_effect_evidence().external_effect_claimed is True
    assert _valid_effect_evidence(external_effect_claimed=False).external_effect_claimed is False


def test_adapter_external_effect_requires_boundary_for_write_success() -> None:
    assessment = assess_adapter_external_effect_evidence(
        _valid_effect_evidence(
            effect_mode="plan_only",
            external_effect_claimed=False,
            provider_receipt_hash="",
            provider_receipt_ref="",
            idempotency_key="",
            rollback_or_recovery_ref="",
            approval_ref="",
            effect_boundary_declared=False,
        )
    )

    assert assessment.execution_success_claim_allowed is False
    assert "external_effect_boundary_required" in assessment.blocked_reasons
    assert "external_effect_success_evidence_required" in assessment.blocked_reasons
    assert assessment.plan_only is True
    assert assessment.network_call_performed is False


def test_adapter_external_effect_rejects_secret_value_disclosure() -> None:
    assessment = assess_adapter_external_effect_evidence(
        _valid_effect_evidence(secret_values_disclosed=True)
    )

    assert assessment.execution_success_claim_allowed is False
    assert "secret_values_disclosed" in assessment.blocked_reasons
    assert assessment.secret_values_disclosed is True
    assert assessment.provider_receipt_ref == "provider://gmail/messages/send/effect-request-1"
    assert assessment.request_authentication_performed is False


def test_signed_browser_transport_verifies_response_signature_and_receipt(monkeypatch) -> None:
    secret = "browser-transport-secret"
    request_payload = {
        "request_id": "browser-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "browser.extract_text",
        "action": "browser.extract_text",
        "url": "https://docs.mullusi.com/guide",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "browser-request-1",
        "status": "succeeded",
        "result": {"extracted_text": "ok"},
        "receipt": {
            "request_id": "browser-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "browser.extract_text",
            "verification_status": "passed",
            "evidence_refs": ["browser_action:test"],
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    observed_request: dict[str, Any] = {}

    class StubHttpResponse:
        headers = {"X-Mullu-Browser-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    def capture_urlopen(http_request, timeout):
        observed_request["url"] = http_request.full_url
        observed_request["body"] = http_request.data
        observed_request["signature"] = http_request.get_header("X-mullu-browser-signature")
        observed_request["timeout"] = timeout
        return StubHttpResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
    client = BrowserWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="browser",
        endpoint_url="https://worker.invalid/browser/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
        timeout_seconds=3.0,
    ))

    response = client.execute(request_payload)

    assert response.status == "succeeded"
    assert response.receipt["verification_status"] == "passed"
    assert observed_request["url"] == "https://worker.invalid/browser/execute"
    assert observed_request["timeout"] == 3.0
    assert verify_capability_signature(observed_request["body"], observed_request["signature"], secret)


def test_signed_adapter_transport_rejects_bad_response_signature(monkeypatch) -> None:
    request_payload = {
        "request_id": "browser-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "browser.extract_text",
        "action": "browser.extract_text",
        "url": "https://docs.mullusi.com/guide",
        "metadata": {},
    }
    response_body = b'{"request_id":"browser-request-1"}'
    observed_request: dict[str, Any] = {}

    class StubHttpResponse:
        headers = {"X-Mullu-Browser-Response-Signature": "hmac-sha256:bad"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    def capture_urlopen(http_request, timeout):
        observed_request["url"] = http_request.full_url
        observed_request["timeout"] = timeout
        return StubHttpResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
    client = BrowserWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="browser",
        endpoint_url="https://worker.invalid/browser/execute",
        signing_secret="browser-transport-secret",
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
    ))

    with pytest.raises(RuntimeError, match="^browser worker response signature invalid$") as excinfo:
        client.execute(request_payload)

    assert str(excinfo.value) == "browser worker response signature invalid"
    assert observed_request["url"] == "https://worker.invalid/browser/execute"
    assert observed_request["timeout"] == 10.0


def test_signed_adapter_transport_rejects_receipt_tenant_mismatch(monkeypatch) -> None:
    secret = "browser-transport-secret"
    request_payload = {
        "request_id": "browser-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "browser.extract_text",
        "action": "browser.extract_text",
        "url": "https://docs.mullusi.com/guide",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "browser-request-1",
        "status": "succeeded",
        "result": {"extracted_text": "ok"},
        "receipt": {
            "request_id": "browser-request-1",
            "tenant_id": "tenant-2",
            "capability_id": "browser.extract_text",
            "verification_status": "passed",
            "evidence_refs": ["browser_action:test"],
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    class StubHttpResponse:
        headers = {"X-Mullu-Browser-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    client = BrowserWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="browser",
        endpoint_url="https://worker.invalid/browser/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
    ))

    with pytest.raises(RuntimeError, match="^browser worker receipt tenant mismatch$") as excinfo:
        client.execute(request_payload)

    assert str(excinfo.value) == "browser worker receipt tenant mismatch"
    assert request_payload["tenant_id"] == "tenant-1"
    assert worker_payload["receipt"]["tenant_id"] == "tenant-2"


def test_signed_adapter_transport_preserves_failed_effect_receipt_observability(monkeypatch) -> None:
    secret = "browser-transport-secret"
    request_payload = {
        "request_id": "browser-submit-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "browser.submit",
        "action": "browser.submit",
        "selector": "#submit",
        "approval_id": "approval-1",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "browser-submit-request-1",
        "status": "failed",
        "result": {"error": "browser verification failed"},
        "receipt": {
            "request_id": "browser-submit-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "browser.submit",
            "verification_status": "failed",
            "evidence_refs": ["browser_action:failed-submit"],
            "forbidden_effects_observed": True,
        },
        "error": "browser verification failed",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    class StubHttpResponse:
        headers = {"X-Mullu-Browser-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    client = BrowserWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="browser",
        endpoint_url="https://worker.invalid/browser/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Browser-Signature",
        response_signature_header="X-Mullu-Browser-Response-Signature",
    ))

    response = client.execute(request_payload)

    assert response.status == "failed"
    assert response.receipt["forbidden_effects_observed"] is True
    assert response.receipt["verification_status"] == "failed"
    assert response.error == "browser verification failed"


def test_browser_worker_env_requires_complete_signed_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_BROWSER_WORKER_URL", "https://worker.invalid/browser/execute")
    monkeypatch.delenv("MULLU_BROWSER_WORKER_SECRET", raising=False)

    with pytest.raises(ValueError, match="^browser worker signing secret is required$") as excinfo:
        build_browser_worker_client_from_env()

    assert str(excinfo.value) == "browser worker signing secret is required"
    assert os.environ["MULLU_BROWSER_WORKER_URL"] == "https://worker.invalid/browser/execute"
    monkeypatch.delenv("MULLU_BROWSER_WORKER_URL", raising=False)
    assert build_browser_worker_client_from_env() is None


def test_email_calendar_transport_uses_distinct_signature_headers(monkeypatch) -> None:
    secret = "email-calendar-transport-secret"
    request_payload = {
        "request_id": "email-calendar-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "email.draft",
        "action": "email.draft",
        "connector_id": "gmail",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "email-calendar-request-1",
        "status": "succeeded",
        "result": {"resource_id": "draft-1"},
        "receipt": {
            "request_id": "email-calendar-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "email.draft",
            "verification_status": "passed",
            "evidence_refs": ["email_calendar_action:test"],
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    observed_request: dict[str, Any] = {}

    class StubHttpResponse:
        headers = {"X-Mullu-Email-Calendar-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    def capture_urlopen(http_request, timeout):
        observed_request["signature"] = http_request.get_header("X-mullu-email-calendar-signature")
        observed_request["body"] = http_request.data
        return StubHttpResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
    client = EmailCalendarWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="email/calendar",
        endpoint_url="https://worker.invalid/email-calendar/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Email-Calendar-Signature",
        response_signature_header="X-Mullu-Email-Calendar-Response-Signature",
    ))

    response = client.execute(request_payload)

    assert response.status == "succeeded"
    assert response.receipt["capability_id"] == "email.draft"
    assert verify_capability_signature(observed_request["body"], observed_request["signature"], secret)


def test_signed_adapter_transport_rejects_live_effect_without_provider_receipt(monkeypatch) -> None:
    secret = "email-calendar-transport-secret"
    request_payload = {
        "request_id": "email-calendar-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "email.send",
        "action": "email.send",
        "connector_id": "gmail",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "email-calendar-request-1",
        "status": "succeeded",
        "result": {"resource_id": "message-1"},
        "receipt": {
            "request_id": "email-calendar-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "email.send",
            "verification_status": "passed",
            "evidence_refs": ["email_calendar_action:send"],
            "effect_mode": "live_provider",
            "external_effect_claimed": True,
            "idempotency_key": "idem-email-calendar-request-1",
            "rollback_or_recovery_ref": "runbook://gmail/send/recovery",
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    class StubHttpResponse:
        headers = {"X-Mullu-Email-Calendar-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    client = EmailCalendarWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="email/calendar",
        endpoint_url="https://worker.invalid/email-calendar/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Email-Calendar-Signature",
        response_signature_header="X-Mullu-Email-Calendar-Response-Signature",
    ))

    with pytest.raises(
        RuntimeError,
        match="^email/calendar worker effect receipt invalid:provider_receipt_hash_required$",
    ) as excinfo:
        client.execute(request_payload)

    assert str(excinfo.value) == "email/calendar worker effect receipt invalid:provider_receipt_hash_required"
    assert worker_payload["receipt"]["effect_mode"] == "live_provider"
    assert "provider_receipt_hash" not in worker_payload["receipt"]


def test_signed_adapter_transport_accepts_live_effect_with_provider_receipt(monkeypatch) -> None:
    secret = "email-calendar-transport-secret"
    request_payload = {
        "request_id": "email-calendar-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "email.send",
        "action": "email.send",
        "connector_id": "gmail",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "email-calendar-request-1",
        "status": "succeeded",
        "result": {"resource_id": "message-1"},
        "receipt": {
            "request_id": "email-calendar-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "email.send",
            "verification_status": "passed",
            "evidence_refs": ["email_calendar_action:send"],
            "effect_mode": "live_provider",
            "external_effect_claimed": True,
            "provider_receipt_hash": "sha256:" + ("b" * 64),
            "provider_receipt_ref": "provider://gmail/messages/send/email-calendar-request-1",
            "idempotency_key": "idem-email-calendar-request-1",
            "rollback_or_recovery_ref": "runbook://gmail/send/recovery",
            "approval_id": "approval-email-calendar-request-1",
            "forbidden_effects_observed": False,
            "secret_values_disclosed": False,
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    class StubHttpResponse:
        headers = {"X-Mullu-Email-Calendar-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    client = EmailCalendarWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="email/calendar",
        endpoint_url="https://worker.invalid/email-calendar/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Email-Calendar-Signature",
        response_signature_header="X-Mullu-Email-Calendar-Response-Signature",
    ))

    response = client.execute(request_payload)

    assert response.status == "succeeded"
    assert response.receipt["provider_receipt_hash"] == "sha256:" + ("b" * 64)
    assert response.receipt["provider_receipt_ref"] == "provider://gmail/messages/send/email-calendar-request-1"
    assert response.receipt["idempotency_key"] == "idem-email-calendar-request-1"
    assert response.receipt["rollback_or_recovery_ref"] == "runbook://gmail/send/recovery"
    assert response.receipt["approval_id"] == "approval-email-calendar-request-1"


def test_email_calendar_worker_env_requires_complete_signed_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", "email-calendar-secret")
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_URL", raising=False)

    with pytest.raises(ValueError, match="^email/calendar worker endpoint is required$") as excinfo:
        build_email_calendar_worker_client_from_env()

    assert str(excinfo.value) == "email/calendar worker endpoint is required"
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", raising=False)
    assert build_email_calendar_worker_client_from_env() is None


def test_messaging_transport_uses_distinct_signature_headers(monkeypatch) -> None:
    secret = "messaging-transport-secret"
    request_payload = {
        "request_id": "messaging-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "messaging.sms.draft",
        "action": "messaging.sms.draft",
        "connector_id": "twilio",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "messaging-request-1",
        "status": "succeeded",
        "result": {"resource_id": "msg-1"},
        "receipt": {
            "request_id": "messaging-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "messaging.sms.draft",
            "verification_status": "passed",
            "evidence_refs": ["messaging_action:test"],
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    observed_request: dict[str, Any] = {}

    class StubHttpResponse:
        headers = {"X-Mullu-Messaging-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    def capture_urlopen(http_request, timeout):
        observed_request["signature"] = http_request.get_header("X-mullu-messaging-signature")
        observed_request["body"] = http_request.data
        return StubHttpResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
    client = MessagingWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="messaging",
        endpoint_url="https://worker.invalid/messaging/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Messaging-Signature",
        response_signature_header="X-Mullu-Messaging-Response-Signature",
    ))

    response = client.execute(request_payload)

    assert response.status == "succeeded"
    assert response.receipt["capability_id"] == "messaging.sms.draft"
    assert verify_capability_signature(observed_request["body"], observed_request["signature"], secret)


def test_messaging_worker_env_requires_complete_signed_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_MESSAGING_WORKER_SECRET", "messaging-secret")
    monkeypatch.delenv("MULLU_MESSAGING_WORKER_URL", raising=False)

    with pytest.raises(ValueError, match="^messaging worker endpoint is required$") as excinfo:
        build_messaging_worker_client_from_env()

    assert str(excinfo.value) == "messaging worker endpoint is required"
    monkeypatch.delenv("MULLU_MESSAGING_WORKER_SECRET", raising=False)
    assert build_messaging_worker_client_from_env() is None


def test_phone_transport_uses_distinct_signature_headers(monkeypatch) -> None:
    secret = "phone-transport-secret"
    request_payload = {
        "request_id": "phone-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "phone.call.receive",
        "action": "phone.call.receive",
        "connector_id": "twilio",
        "metadata": {},
    }
    worker_payload = {
        "request_id": "phone-request-1",
        "status": "succeeded",
        "result": {"resource_id": "call-1"},
        "receipt": {
            "request_id": "phone-request-1",
            "tenant_id": "tenant-1",
            "capability_id": "phone.call.receive",
            "verification_status": "passed",
            "evidence_refs": ["phone_action:test"],
        },
        "error": "",
    }
    response_body = json.dumps(worker_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    observed_request: dict[str, Any] = {}

    class StubHttpResponse:
        headers = {"X-Mullu-Phone-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    def capture_urlopen(http_request, timeout):
        observed_request["signature"] = http_request.get_header("X-mullu-phone-signature")
        observed_request["body"] = http_request.data
        return StubHttpResponse()

    monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
    client = PhoneWorkerClient(SignedAdapterWorkerTransport(
        adapter_id="phone",
        endpoint_url="https://worker.invalid/phone/execute",
        signing_secret=secret,
        request_signature_header="X-Mullu-Phone-Signature",
        response_signature_header="X-Mullu-Phone-Response-Signature",
    ))

    response = client.execute(request_payload)

    assert response.status == "succeeded"
    assert response.receipt["capability_id"] == "phone.call.receive"
    assert verify_capability_signature(observed_request["body"], observed_request["signature"], secret)


def test_phone_worker_env_requires_complete_signed_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_PHONE_WORKER_SECRET", "phone-secret")
    monkeypatch.delenv("MULLU_PHONE_WORKER_URL", raising=False)

    with pytest.raises(ValueError, match="^phone worker endpoint is required$") as excinfo:
        build_phone_worker_client_from_env()

    assert str(excinfo.value) == "phone worker endpoint is required"
    monkeypatch.delenv("MULLU_PHONE_WORKER_SECRET", raising=False)
    assert build_phone_worker_client_from_env() is None
