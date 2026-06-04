"""Phone connector adapter tests.

Purpose: prove concrete Twilio and Vonage HTTP voice adapters remain bounded by
    governed worker contracts.
Invariants:
  - Missing connector credentials fail closed before transport.
  - Inbound receive and transcript record produce digest evidence without
    external call effects.
  - Outbound place, transfer, and terminate require an approval witness before
    dispatch.
  - Provider tokens are used only in HTTP headers and never returned in
    observation fields or errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.phone_connector_adapters import (  # noqa: E402
    HttpPhoneAdapter,
    PhoneConnectorCredential,
    build_phone_adapter_from_env,
)
from gateway.phone_worker import PhoneActionRequest  # noqa: E402


def test_twilio_call_place_requires_approval_before_transport() -> None:
    transport = FakeTransport(response_body={"sid": "CA123"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="call-place-no-approval",
        capability_id="phone.call.place.with_approval",
        action="phone.call.place.with_approval",
        connector_id="twilio",
        callees=("+15555550199",),
    ))

    assert observation.succeeded is False
    assert observation.error == "approval witness required for connector call"
    assert observation.external_call is False
    assert transport.calls == []


def test_twilio_call_place_with_approval_uses_basic_auth_form_body() -> None:
    transport = FakeTransport(response_body={"sid": "CA123"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="call-place-approved",
        capability_id="phone.call.place.with_approval",
        action="phone.call.place.with_approval",
        connector_id="twilio",
        callees=("+15555550199",),
        approval_id="approval-1",
    ))

    assert observation.succeeded is True
    assert observation.external_call is True
    assert observation.resource_id == "CA123"
    assert observation.provider_operation == "twilio.calls.create"
    assert "/2010-04-01/Accounts/" in transport.calls[0]["url"]
    assert transport.calls[0]["url"].endswith("/Calls.json")
    assert transport.calls[0]["authorization"].startswith("Basic ")
    assert b"To=%2B15555550199" in transport.calls[0]["raw_body"]
    assert b"From=%2B15555550111" in transport.calls[0]["raw_body"]
    assert "twilio-token" not in observation.error


def test_twilio_call_terminate_requires_approval_before_transport() -> None:
    transport = FakeTransport(response_body={"sid": "CA123", "status": "completed"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="call-terminate-no-approval",
        capability_id="phone.call.terminate",
        action="phone.call.terminate",
        connector_id="twilio",
        call_id="CA123",
    ))

    assert observation.succeeded is False
    assert observation.error == "approval witness required for connector call"
    assert observation.external_call is False
    assert transport.calls == []


def test_twilio_call_terminate_with_approval_updates_call_status() -> None:
    transport = FakeTransport(response_body={"sid": "CA123", "status": "completed"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="call-terminate-1",
        capability_id="phone.call.terminate",
        action="phone.call.terminate",
        connector_id="twilio",
        call_id="CA123",
        approval_id="approval-terminate-1",
    ))

    assert observation.succeeded is True
    assert observation.external_call is False
    assert observation.provider_operation == "twilio.calls.update.terminate"
    assert transport.calls[0]["method"] == "POST"
    assert b"Status=completed" in transport.calls[0]["raw_body"]


def test_twilio_call_receive_uses_get_without_external_effect() -> None:
    transport = FakeTransport(response_body={"sid": "CA123", "from": "+15555550100"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="call-receive-1",
        capability_id="phone.call.receive",
        action="phone.call.receive",
        connector_id="twilio",
        callers=("+15555550100",),
    ))

    assert observation.succeeded is True
    assert observation.external_call is False
    assert observation.provider_operation == "twilio.calls.read"
    assert transport.calls[0]["method"] == "GET"


def test_twilio_transcript_record_uses_local_probe() -> None:
    transport = FakeTransport(response_body={"id": "rec-1"})
    adapter = HttpPhoneAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="transcript-1",
        capability_id="phone.call.transcript_record",
        action="phone.call.transcript_record",
        connector_id="twilio",
        call_id="CA123",
        transcript="caller said hello",
    ))

    assert observation.succeeded is True
    assert observation.external_call is False
    assert observation.provider_operation == "twilio.transcript.record"
    assert transport.calls[0]["url"].endswith("/governed/probe")


def test_vonage_call_place_with_approval_uses_json_body() -> None:
    transport = FakeTransport(response_body={"uuid": "vonage-call-1"})
    adapter = HttpPhoneAdapter(
        credentials={"vonage": _vonage_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="vonage-place-approved",
        capability_id="phone.call.place.with_approval",
        action="phone.call.place.with_approval",
        connector_id="vonage",
        callees=("+15555550199",),
        approval_id="approval-1",
    ))

    assert observation.succeeded is True
    assert observation.external_call is True
    assert observation.resource_id == "vonage-call-1"
    assert observation.provider_operation == "vonage.calls.create"
    assert transport.calls[0]["url"] == "https://vonage.example/v1/calls"
    assert transport.calls[0]["authorization"] == "Bearer vonage-secret"
    assert transport.calls[0]["json_body"]["to"][0]["number"] == "+15555550199"


def test_missing_credential_fails_closed_before_transport() -> None:
    transport = FakeTransport(response_body={})
    adapter = HttpPhoneAdapter(credentials={}, urlopen=transport)

    observation = adapter.perform(_request(
        request_id="missing-credential",
        capability_id="phone.call.receive",
        action="phone.call.receive",
        connector_id="twilio",
        callers=("+15555550100",),
    ))

    assert observation.succeeded is False
    assert observation.error == "phone connector credential unavailable"
    assert transport.calls == []


def test_env_builder_loads_twilio_and_vonage_credentials(monkeypatch) -> None:
    for env in (
        "TWILIO_AUTH_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_VOICE_CALLER_ID",
        "TWILIO_VOICE_CALLBACK_URL",
        "VONAGE_API_KEY",
        "VONAGE_API_SECRET",
        "VONAGE_APPLICATION_ID",
        "VONAGE_VOICE_CALLER_ID",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("MULLU_PHONE_WORKER_ADAPTER", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_VOICE_CALLER_ID", "+15555550111")
    monkeypatch.setenv("TWILIO_VOICE_CALLBACK_URL", "https://example.com/twiml")
    monkeypatch.setenv("VONAGE_API_KEY", "vonage-key")
    monkeypatch.setenv("VONAGE_API_SECRET", "vonage-secret")

    adapter = build_phone_adapter_from_env()

    assert adapter is not None
    assert sorted(adapter._credentials) == ["twilio", "vonage"]


def test_env_builder_rejects_unknown_adapter_name(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_PHONE_WORKER_ADAPTER", "carrier-pigeon")
    try:
        build_phone_adapter_from_env()
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "unsupported phone worker adapter: carrier-pigeon"


def test_env_builder_returns_none_when_no_adapter_configured(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_PHONE_WORKER_ADAPTER", raising=False)
    assert build_phone_adapter_from_env() is None


def _twilio_credential() -> PhoneConnectorCredential:
    return PhoneConnectorCredential(
        connector_id="twilio",
        access_token="twilio-token",
        base_url="https://twilio.example",
        scope_id="scope:twilio.voice",
        extra={
            "account_sid": "AC123",
            "caller_id": "+15555550111",
            "callback_url": "https://example.com/twiml",
        },
    )


def _vonage_credential() -> PhoneConnectorCredential:
    return PhoneConnectorCredential(
        connector_id="vonage",
        access_token="vonage-secret",
        base_url="https://vonage.example",
        scope_id="scope:vonage.voice",
        extra={
            "api_key": "vonage-key",
            "application_id": "app-1",
            "caller_id": "+15555550111",
        },
    )


class FakeTransport:
    """urllib-compatible transport fixture that records bounded HTTP calls."""

    def __init__(self, *, response_body: dict[str, Any], status: int = 200) -> None:
        self._response_body = response_body
        self._status = status
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, *, timeout: float) -> "FakeResponse":
        raw_body = request.data or b""
        json_body: dict[str, Any] = {}
        try:
            if raw_body and request.get_header("Content-type", "").startswith("application/json"):
                json_body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            json_body = {}
        self.calls.append(
            {
                "method": request.get_method(),
                "url": request.full_url,
                "timeout": timeout,
                "authorization": request.get_header("Authorization"),
                "scope": request.get_header("X-mullu-connector-scope"),
                "raw_body": raw_body,
                "json_body": json_body,
            }
        )
        return FakeResponse(status=self._status, body=self._response_body)


class FakeResponse:
    """Minimal HTTP response fixture."""

    def __init__(self, *, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def _request(**overrides: Any) -> PhoneActionRequest:
    payload = {
        "request_id": "phone-request",
        "tenant_id": "tenant-1",
        "capability_id": "phone.call.receive",
        "action": "phone.call.receive",
        "connector_id": "twilio",
        "call_id": "",
        "callees": (),
        "callers": (),
        "transcript": "",
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return PhoneActionRequest(**payload)
