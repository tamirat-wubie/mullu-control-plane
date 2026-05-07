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
    BrowserWorkerClient,
    EmailCalendarWorkerClient,
    SignedAdapterWorkerTransport,
    build_browser_worker_client_from_env,
    build_email_calendar_worker_client_from_env,
)
from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402


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


def test_email_calendar_worker_env_requires_complete_signed_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", "email-calendar-secret")
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_URL", raising=False)

    with pytest.raises(ValueError, match="^email/calendar worker endpoint is required$") as excinfo:
        build_email_calendar_worker_client_from_env()

    assert str(excinfo.value) == "email/calendar worker endpoint is required"
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", raising=False)
    assert build_email_calendar_worker_client_from_env() is None
