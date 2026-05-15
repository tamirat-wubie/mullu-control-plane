"""Messaging worker contract tests.

Tests: signed bounded connector requests, approval gates, connector allowlists,
receipt redaction, and forbidden send observations.
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
from gateway.messaging_worker import (  # noqa: E402
    MessagingActionObservation,
    MessagingWorkerPolicy,
    _default_adapter,
    create_messaging_worker_app,
    execute_messaging_request,
    messaging_action_request_from_mapping,
)


class FakeMessagingAdapter:
    """Connector adapter fixture that returns deterministic observations."""

    def __init__(
        self,
        *,
        connector_id: str = "",
        external_send: bool = False,
    ) -> None:
        self.requests = []
        self._connector_id = connector_id
        self._external_send = external_send

    def perform(self, request):
        self.requests.append(request)
        connector_id = self._connector_id or request.connector_id
        return MessagingActionObservation(
            succeeded=True,
            connector_id=connector_id,
            provider_operation=request.action,
            resource_id=f"resource-{request.request_id}",
            response_digest="digest-1",
            external_send=self._external_send,
        )


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "messaging-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "messaging.sms.draft",
        "action": "messaging.sms.draft",
        "connector_id": "twilio",
        "body": "Draft body",
        "thread_id": "",
        "query": "",
        "recipients": ["+15555550100"],
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_messaging_worker_executes_signed_draft_request() -> None:
    secret = "messaging-secret"
    adapter = FakeMessagingAdapter()
    app = create_messaging_worker_app(adapter=adapter, signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload())

    response = client.post(
        "/messaging/execute",
        content=body,
        headers={"X-Mullu-Messaging-Signature": sign_capability_payload(body, secret)},
    )

    payload = response.json()
    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Messaging-Response-Signature"],
        secret,
    )
    assert payload["status"] == "succeeded"
    assert payload["receipt"]["capability_id"] == "messaging.sms.draft"
    assert payload["receipt"]["connector_id"] == "twilio"
    assert payload["receipt"]["recipient_hashes"] != ["+15555550100"]
    assert payload["receipt"]["verification_status"] == "passed"
    assert adapter.requests[0].tenant_id == "tenant-1"


def test_messaging_worker_rejects_bad_signature() -> None:
    app = create_messaging_worker_app(adapter=FakeMessagingAdapter(), signing_secret="messaging-secret")
    client = TestClient(app)

    response = client.post(
        "/messaging/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Messaging-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid messaging request signature"
    assert "X-Mullu-Messaging-Response-Signature" not in response.headers


def test_messaging_worker_parse_error_detail_is_bounded() -> None:
    secret = "messaging-secret"
    body = b'{"request_id":"secret-token-from-messaging"'
    app = create_messaging_worker_app(adapter=FakeMessagingAdapter(), signing_secret=secret)
    client = TestClient(app)

    response = client.post(
        "/messaging/execute",
        content=body,
        headers={"X-Mullu-Messaging-Signature": sign_capability_payload(body, secret)},
    )
    detail = response.json()["detail"]

    assert response.status_code == 422
    assert detail["error"] == "invalid messaging execution request"
    assert detail["error_code"] == "invalid_messaging_execution_request"
    assert detail["governed"] is True
    assert "secret-token-from-messaging" not in response.text
    assert "X-Mullu-Messaging-Response-Signature" not in response.headers


def test_sms_send_requires_approval_before_adapter() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-sms-send",
            capability_id="messaging.sms.send.with_approval",
            action="messaging.sms.send.with_approval",
        )
    )
    adapter = FakeMessagingAdapter(external_send=True)

    response = execute_messaging_request(
        request,
        adapter=adapter,
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging action requires approval"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.approval_id == ""
    assert adapter.requests == []


def test_sms_send_with_approval_executes_as_external_send() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-sms-approved",
            capability_id="messaging.sms.send.with_approval",
            action="messaging.sms.send.with_approval",
            approval_id="approval-1",
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(external_send=True),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.receipt.external_send is True
    assert response.receipt.approval_id == "approval-1"
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.evidence_refs[0].startswith("messaging_action:")


def test_chat_send_requires_approval() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-chat-send",
            capability_id="messaging.chat.send.with_approval",
            action="messaging.chat.send.with_approval",
            connector_id="slack",
            recipients=["U0123456"],
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(external_send=True),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging action requires approval"
    assert response.receipt.recipient_hashes != ("U0123456",)
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.forbidden_effects_observed is False


def test_sms_action_rejects_chat_connector() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-sms-bad-connector",
            capability_id="messaging.sms.draft",
            action="messaging.sms.draft",
            connector_id="slack",
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging sms action requires sms-capable connector"
    assert response.receipt.verification_status == "blocked"


def test_chat_action_rejects_sms_connector() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-chat-bad-connector",
            capability_id="messaging.chat.draft",
            action="messaging.chat.draft",
            connector_id="twilio",
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging chat action requires chat-capable connector"


def test_thread_read_requires_thread_id() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-thread-read",
            capability_id="messaging.thread.read",
            action="messaging.thread.read",
            connector_id="slack",
            recipients=[],
            thread_id="",
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging thread read requires thread_id"
    assert response.receipt.verification_status == "blocked"


def test_worker_blocks_unallowlisted_connector_before_adapter() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-bad-connector",
            connector_id="unknown_carrier",
        )
    )
    adapter = FakeMessagingAdapter()

    response = execute_messaging_request(
        request,
        adapter=adapter,
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "messaging connector is not allowlisted"
    assert adapter.requests == []


def test_draft_action_fails_if_adapter_observes_external_send() -> None:
    request = messaging_action_request_from_mapping(
        _payload(
            request_id="messaging-draft-leaks-send",
            capability_id="messaging.sms.draft",
            action="messaging.sms.draft",
        )
    )

    response = execute_messaging_request(
        request,
        adapter=FakeMessagingAdapter(external_send=True),
        policy=MessagingWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "messaging verification failed"
    assert response.receipt.external_send is True
    assert response.receipt.forbidden_effects_observed is True
    assert response.receipt.verification_status == "failed"


def test_default_adapter_is_unconfigured_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_MESSAGING_WORKER_ADAPTER", raising=False)
    assert _default_adapter() is None
