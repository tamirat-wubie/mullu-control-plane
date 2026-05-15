"""Phone worker contract tests.

Tests: signed bounded connector requests, approval gates, connector allowlists,
receipt redaction, and forbidden call observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402
from gateway.phone_worker import (  # noqa: E402
    PhoneActionObservation,
    PhoneWorkerPolicy,
    _default_adapter,
    create_phone_worker_app,
    execute_phone_request,
    phone_action_request_from_mapping,
)


class FakePhoneAdapter:
    """Connector adapter fixture that returns deterministic observations."""

    def __init__(
        self,
        *,
        connector_id: str = "",
        external_call: bool = False,
    ) -> None:
        self.requests = []
        self._connector_id = connector_id
        self._external_call = external_call

    def perform(self, request):
        self.requests.append(request)
        connector_id = self._connector_id or request.connector_id
        return PhoneActionObservation(
            succeeded=True,
            connector_id=connector_id,
            provider_operation=request.action,
            resource_id=f"resource-{request.request_id}",
            response_digest="digest-1",
            external_call=self._external_call,
        )


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "phone-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "phone.call.receive",
        "action": "phone.call.receive",
        "connector_id": "twilio",
        "call_id": "",
        "callees": [],
        "callers": ["+15555550100"],
        "transcript": "",
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_phone_worker_executes_signed_receive_request() -> None:
    secret = "phone-secret"
    adapter = FakePhoneAdapter()
    app = create_phone_worker_app(adapter=adapter, signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload())

    response = client.post(
        "/phone/execute",
        content=body,
        headers={"X-Mullu-Phone-Signature": sign_capability_payload(body, secret)},
    )

    payload = response.json()
    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Phone-Response-Signature"],
        secret,
    )
    assert payload["status"] == "succeeded"
    assert payload["receipt"]["capability_id"] == "phone.call.receive"
    assert payload["receipt"]["connector_id"] == "twilio"
    assert payload["receipt"]["caller_hashes"] != ["+15555550100"]
    assert payload["receipt"]["verification_status"] == "passed"
    assert adapter.requests[0].tenant_id == "tenant-1"


def test_phone_worker_rejects_bad_signature() -> None:
    app = create_phone_worker_app(adapter=FakePhoneAdapter(), signing_secret="phone-secret")
    client = TestClient(app)

    response = client.post(
        "/phone/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Phone-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid phone request signature"
    assert "X-Mullu-Phone-Response-Signature" not in response.headers


def test_phone_worker_parse_error_detail_is_bounded() -> None:
    secret = "phone-secret"
    body = b'{"request_id":"secret-token-from-phone"'
    app = create_phone_worker_app(adapter=FakePhoneAdapter(), signing_secret=secret)
    client = TestClient(app)

    response = client.post(
        "/phone/execute",
        content=body,
        headers={"X-Mullu-Phone-Signature": sign_capability_payload(body, secret)},
    )
    detail = response.json()["detail"]

    assert response.status_code == 422
    assert detail["error"] == "invalid phone execution request"
    assert detail["error_code"] == "invalid_phone_execution_request"
    assert detail["governed"] is True
    assert "secret-token-from-phone" not in response.text
    assert "X-Mullu-Phone-Response-Signature" not in response.headers


def test_call_place_requires_approval_before_adapter() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-call-place",
            capability_id="phone.call.place.with_approval",
            action="phone.call.place.with_approval",
            callees=["+15555550199"],
            callers=[],
        )
    )
    adapter = FakePhoneAdapter(external_call=True)

    response = execute_phone_request(
        request,
        adapter=adapter,
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "phone action requires approval"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.approval_id == ""
    assert adapter.requests == []


def test_call_place_with_approval_executes_as_external_call() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-call-place-approved",
            capability_id="phone.call.place.with_approval",
            action="phone.call.place.with_approval",
            callees=["+15555550199"],
            callers=[],
            approval_id="approval-1",
        )
    )

    response = execute_phone_request(
        request,
        adapter=FakePhoneAdapter(external_call=True),
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.receipt.external_call is True
    assert response.receipt.approval_id == "approval-1"
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.evidence_refs[0].startswith("phone_action:")


def test_call_transfer_requires_call_id_and_callees() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-transfer-bad",
            capability_id="phone.call.transfer.with_approval",
            action="phone.call.transfer.with_approval",
            call_id="",
            callees=["+15555550199"],
            approval_id="approval-1",
        )
    )

    response = execute_phone_request(
        request,
        adapter=FakePhoneAdapter(external_call=True),
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "phone call transfer requires call_id and callees"
    assert response.receipt.verification_status == "blocked"


def test_call_terminate_requires_call_id() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-terminate-bad",
            capability_id="phone.call.terminate",
            action="phone.call.terminate",
            callees=[],
            callers=[],
            call_id="",
        )
    )

    response = execute_phone_request(
        request,
        adapter=FakePhoneAdapter(),
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "phone action requires call_id"


def test_transcript_record_redacts_transcript() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-transcript",
            capability_id="phone.call.transcript_record",
            action="phone.call.transcript_record",
            callees=[],
            callers=[],
            call_id="call-1",
            transcript="caller said hello",
        )
    )

    response = execute_phone_request(
        request,
        adapter=FakePhoneAdapter(),
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.receipt.transcript_hash != "caller said hello"
    assert response.receipt.transcript_hash != ""
    assert response.receipt.call_id_hash != "call-1"


def test_worker_blocks_unallowlisted_connector_before_adapter() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-bad-connector",
            connector_id="unknown_carrier",
        )
    )
    adapter = FakePhoneAdapter()

    response = execute_phone_request(
        request,
        adapter=adapter,
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "phone connector is not allowlisted"
    assert adapter.requests == []


def test_receive_action_fails_if_adapter_observes_external_call() -> None:
    request = phone_action_request_from_mapping(
        _payload(
            request_id="phone-receive-leaks-call",
            capability_id="phone.call.receive",
            action="phone.call.receive",
        )
    )

    response = execute_phone_request(
        request,
        adapter=FakePhoneAdapter(external_call=True),
        policy=PhoneWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "phone verification failed"
    assert response.receipt.external_call is True
    assert response.receipt.forbidden_effects_observed is True
    assert response.receipt.verification_status == "failed"


def test_default_adapter_is_unconfigured_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_PHONE_WORKER_ADAPTER", raising=False)
    assert _default_adapter() is None
