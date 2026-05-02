"""Capability worker endpoint tests.

Tests: signed restricted-worker execution requests, response signatures, and
receipt-bearing capability execution responses.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import (  # noqa: E402
    CapabilityIsolationPolicy,
    sign_capability_payload,
    verify_capability_signature,
)
from gateway.capability_worker import _default_app, create_capability_worker_app  # noqa: E402
from gateway.command_spine import canonical_hash, capability_passport_for  # noqa: E402
from gateway.skill_dispatch import SkillDispatcher  # noqa: E402


@dataclass(frozen=True, slots=True)
class PaymentResult:
    success: bool
    tx_id: str
    state: str
    amount: str
    currency: str
    provider_tx_id: str = ""
    requires_approval: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SettlingPaymentExecutor:
    def initiate_payment(self, *, tenant_id, amount, currency, destination, actor_id, description=""):
        return PaymentResult(
            success=True,
            tx_id="tx-worker-1",
            state="pending_approval",
            amount=str(amount),
            currency=currency,
            requires_approval=True,
        )

    def approve_and_execute(self, tx_id, *, approver_id="", api_key=""):
        return PaymentResult(
            success=True,
            tx_id=tx_id,
            state="settled",
            amount="50",
            currency="USD",
            provider_tx_id="provider-worker-1",
            metadata={
                "ledger_hash": "ledger-worker-proof",
                "recipient_hash": "recipient-worker-proof",
                "recipient_ref": "dest:pending",
            },
        )


def _request_body() -> bytes:
    boundary = CapabilityIsolationPolicy(environment="pilot").boundary_for(
        capability_passport_for("financial.send_payment"),
    )
    intent = {"skill": "financial", "action": "send_payment", "params": {"amount": "50"}}
    input_hash = canonical_hash({
        "intent": intent,
        "tenant_id": "tenant-1",
        "identity_id": "identity-1",
        "command_id": "",
        "conversation_id": "",
        "boundary": {
            "capability_id": boundary.capability_id,
            "execution_plane": boundary.execution_plane,
            "isolation_required": boundary.isolation_required,
            "network_policy": boundary.network_policy,
            "filesystem_policy": boundary.filesystem_policy,
            "max_runtime_seconds": boundary.max_runtime_seconds,
            "max_memory_mb": boundary.max_memory_mb,
            "service_account": boundary.service_account,
            "evidence_required": boundary.evidence_required,
        },
        "metadata": {},
    })
    payload = {
        "request_id": "capability-request-test",
        "tenant_id": "tenant-1",
        "identity_id": "identity-1",
        "command_id": "",
        "conversation_id": "",
        "intent": intent,
        "boundary": {
            "capability_id": boundary.capability_id,
            "execution_plane": boundary.execution_plane,
            "isolation_required": boundary.isolation_required,
            "network_policy": list(boundary.network_policy),
            "filesystem_policy": boundary.filesystem_policy,
            "max_runtime_seconds": boundary.max_runtime_seconds,
            "max_memory_mb": boundary.max_memory_mb,
            "service_account": boundary.service_account,
            "evidence_required": list(boundary.evidence_required),
        },
        "input_hash": input_hash,
        "metadata": {},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _body_from_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _rehash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["input_hash"] = canonical_hash({
        "intent": payload["intent"],
        "tenant_id": payload["tenant_id"],
        "identity_id": payload["identity_id"],
        "command_id": payload["command_id"],
        "conversation_id": payload["conversation_id"],
        "boundary": payload["boundary"],
        "metadata": payload["metadata"],
    })
    return payload


def test_capability_worker_executes_signed_payment_request() -> None:
    secret = "worker-secret"
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        signing_secret=secret,
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)
    body = _request_body()
    signature = sign_capability_payload(body, secret)

    response = client.post(
        "/capability/execute",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Mullu-Capability-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Capability-Response-Signature"],
        secret,
    )
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["request_id"] == "capability-request-test"
    assert payload["result"]["receipt_status"] == "settled"
    assert payload["receipt"]["worker_id"] == "restricted-worker-test"
    assert payload["receipt"]["evidence_refs"]


def test_capability_worker_rejects_bad_signature() -> None:
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        signing_secret="worker-secret",
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)

    response = client.post(
        "/capability/execute",
        content=_request_body(),
        headers={"X-Mullu-Capability-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid capability request signature"


def test_capability_worker_rejects_tampered_input_hash() -> None:
    secret = "worker-secret"
    body_payload = json.loads(_request_body().decode("utf-8"))
    body_payload["input_hash"] = "tampered"
    body = json.dumps(body_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        signing_secret=secret,
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)

    response = client.post(
        "/capability/execute",
        content=body,
        headers={"X-Mullu-Capability-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 422
    assert "input hash mismatch" in response.json()["detail"]


def test_capability_worker_rejects_intent_boundary_mismatch() -> None:
    secret = "worker-secret"
    payload = json.loads(_request_body().decode("utf-8"))
    payload["intent"] = {"skill": "financial", "action": "refund", "params": {"transaction_id": "tx-1"}}
    body = _body_from_payload(_rehash_payload(payload))
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        signing_secret=secret,
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)

    response = client.post(
        "/capability/execute",
        content=body,
        headers={"X-Mullu-Capability-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 422
    assert "capability request is malformed" in response.json()["detail"]


def test_capability_worker_rejects_non_isolated_boundary() -> None:
    secret = "worker-secret"
    payload = json.loads(_request_body().decode("utf-8"))
    payload["boundary"]["isolation_required"] = False
    payload["boundary"]["execution_plane"] = "gateway_process"
    body = _body_from_payload(_rehash_payload(payload))
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        signing_secret=secret,
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)

    response = client.post(
        "/capability/execute",
        content=body,
        headers={"X-Mullu-Capability-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 422
    assert "restricted worker requires an isolated capability boundary" in response.json()["detail"]


def test_default_capability_worker_smoke_stub_is_local_only(monkeypatch) -> None:
    secret = "local-worker-secret"
    monkeypatch.setenv("MULLU_ENV", "local_dev")
    monkeypatch.setenv("MULLU_CAPABILITY_WORKER_SECRET", secret)
    monkeypatch.setenv("MULLU_CAPABILITY_WORKER_ENABLE_SMOKE_STUB", "true")
    app = _default_app()
    client = TestClient(app)
    body = _request_body()

    response = client.post(
        "/capability/execute",
        content=body,
        headers={"X-Mullu-Capability-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["transaction_id"] == "tx-smoke-1"
    assert payload["result"]["ledger_hash"] == "ledger-smoke-proof"
