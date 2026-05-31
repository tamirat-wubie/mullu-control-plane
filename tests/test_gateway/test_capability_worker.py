"""Capability worker endpoint tests.

Tests: signed restricted-worker execution requests, response signatures, and
receipt-bearing capability execution responses.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
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
from gateway.skill_dispatch import SkillDispatcher, register_computer_capabilities  # noqa: E402


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


class RecordingProofBridge:
    """Captures capability worker boundary certification calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def certify_governance_decision(self, **kwargs: Any) -> None:
        self.calls.append(dict(kwargs))


class StubSandboxRunner:
    """Sandbox runner fixture that emits a bounded sandbox execution receipt."""

    def __init__(self) -> None:
        self.requests: list[Any] = []

    def execute(self, request):
        from gateway.sandbox_runner import SandboxCommandResult, SandboxExecutionReceipt

        self.requests.append(request)
        stdout = "Python 3\n"
        stderr = ""
        command_hash = canonical_hash({
            "argv": list(request.argv),
            "cwd": request.cwd,
            "environment": dict(request.environment),
        })
        docker_args_hash = canonical_hash({
            "image": "mullu-agent-runner:latest",
            "network_disabled": True,
            "read_only_rootfs": True,
            "workspace_mount": "/workspace",
        })
        receipt = SandboxExecutionReceipt(
            receipt_id=f"sandbox-receipt-{command_hash[:16]}",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            capability_id=request.capability_id,
            sandbox_id="docker-rootless",
            image="mullu-agent-runner:latest",
            command_hash=command_hash,
            docker_args_hash=docker_args_hash,
            stdout_hash=canonical_hash(stdout),
            stderr_hash=canonical_hash(stderr),
            returncode=0,
            network_disabled=True,
            read_only_rootfs=True,
            capabilities_dropped=True,
            seccomp_profile_applied="bundled-default",
            workspace_mount="/workspace",
            forbidden_effects_observed=False,
            changed_file_count=0,
            changed_file_refs=(),
            verification_status="passed",
            evidence_refs=("sandbox_execution:capability-worker",),
        )
        return SandboxCommandResult(status="succeeded", stdout=stdout, stderr=stderr, receipt=receipt)


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


def _capability_request_body(
    *,
    intent: dict[str, Any],
    boundary,
    tenant_id: str = "tenant-1",
    identity_id: str = "identity-1",
    command_id: str = "",
    conversation_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> bytes:
    request_metadata = dict(metadata or {})
    boundary_payload = asdict(boundary)
    input_hash = canonical_hash({
        "intent": intent,
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "command_id": command_id,
        "conversation_id": conversation_id,
        "boundary": boundary_payload,
        "metadata": request_metadata,
    })
    payload = {
        "request_id": f"capability-request-{canonical_hash({'intent': intent, 'input_hash': input_hash})[:16]}",
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "command_id": command_id,
        "conversation_id": conversation_id,
        "intent": intent,
        "boundary": boundary_payload,
        "input_hash": input_hash,
        "metadata": request_metadata,
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


def test_capability_worker_emits_transition_receipt_for_success() -> None:
    secret = "worker-secret"
    proof_bridge = RecordingProofBridge()
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        proof_bridge=proof_bridge,
        signing_secret=secret,
        worker_id="restricted-worker-test",
    )
    client = TestClient(app)
    body = _request_body()

    response = client.post(
        "/capability/execute",
        content=body,
        headers={"X-Mullu-Capability-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 200
    assert len(proof_bridge.calls) == 1
    assert proof_bridge.calls[0]["endpoint"] == "/capability/execute"
    assert proof_bridge.calls[0]["decision"] == "allowed"
    assert proof_bridge.calls[0]["tenant_id"] == "gateway:capability"


def test_capability_worker_runs_computer_command_through_sandbox_receipt() -> None:
    secret = "worker-secret"
    dispatcher = SkillDispatcher()
    sandbox_runner = StubSandboxRunner()
    register_computer_capabilities(dispatcher, sandbox_runner=sandbox_runner)
    app = create_capability_worker_app(
        dispatcher=dispatcher,
        signing_secret=secret,
        worker_id="restricted-sandbox-worker",
    )
    client = TestClient(app)
    boundary = CapabilityIsolationPolicy(environment="pilot").boundary_for(
        capability_passport_for("computer.command.run"),
    )
    intent = {
        "skill": "computer",
        "action": "command.run",
        "params": {
            "request_id": "sandbox-request-capability-worker",
            "argv": ["python", "--version"],
            "cwd": "/workspace",
        },
    }
    body = _capability_request_body(
        intent=intent,
        boundary=boundary,
        command_id="command-sandbox-worker",
        metadata={"purpose": "sandboxed-capability-worker"},
    )

    response = client.post(
        "/capability/execute",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Mullu-Capability-Signature": sign_capability_payload(body, secret),
        },
    )

    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Capability-Response-Signature"],
        secret,
    )
    payload = response.json()
    result = payload["result"]
    sandbox_receipt = result["sandbox_execution_receipt"]
    worker_receipt = payload["receipt"]
    assert payload["status"] == "succeeded"
    assert result["sandbox_status"] == "succeeded"
    assert result["verification_status"] == "passed"
    assert result["sandbox_receipt_id"].startswith("sandbox-receipt-")
    assert sandbox_receipt["network_disabled"] is True
    assert sandbox_receipt["read_only_rootfs"] is True
    assert sandbox_receipt["command_hash"] == canonical_hash({
        "argv": ["python", "--version"],
        "cwd": "/workspace",
        "environment": {},
    })
    assert sandbox_receipt["stdout_hash"] == canonical_hash(result["sandbox_stdout"])
    assert sandbox_receipt["stderr_hash"] == canonical_hash(result["sandbox_stderr"])
    assert sandbox_receipt["evidence_refs"] == ["sandbox_execution:capability-worker"]
    assert worker_receipt["worker_id"] == "restricted-sandbox-worker"
    assert worker_receipt["capability_id"] == "computer.command.run"
    assert worker_receipt["output_hash"] == canonical_hash(result)
    assert worker_receipt["evidence_refs"]
    assert sandbox_runner.requests[0].capability_id == "computer.command.run"
    assert sandbox_runner.requests[0].argv == ("python", "--version")


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


def test_capability_worker_emits_transition_receipt_for_bad_signature() -> None:
    proof_bridge = RecordingProofBridge()
    app = create_capability_worker_app(
        dispatcher=SkillDispatcher(payment_executor=SettlingPaymentExecutor()),
        proof_bridge=proof_bridge,
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
    assert len(proof_bridge.calls) == 1
    assert proof_bridge.calls[0]["endpoint"] == "/capability/execute"
    assert proof_bridge.calls[0]["decision"] == "denied"
    assert proof_bridge.calls[0]["guard_results"][0]["reason"] == "http_403_response"


def test_capability_worker_parse_error_detail_is_bounded() -> None:
    secret = "worker-secret"
    body = b'{"request_id":"secret-token-from-worker"'
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
    detail = response.json()["detail"]

    assert response.status_code == 422
    assert detail["error"] == "invalid capability execution request"
    assert detail["error_code"] == "invalid_capability_execution_request"
    assert detail["governed"] is True
    assert "secret-token-from-worker" not in response.text


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
    detail = response.json()["detail"]
    assert detail["error"] == "capability request input hash mismatch"
    assert detail["error_code"] == "capability_input_hash_mismatch"
    assert detail["governed"] is True


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
    detail = response.json()["detail"]
    assert detail["error"] == "malformed capability request"
    assert detail["error_code"] == "malformed_capability_request"
    assert detail["governed"] is True
    assert "refund" not in response.text


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
    detail = response.json()["detail"]
    assert detail["error"] == "isolated capability boundary required"
    assert detail["error_code"] == "isolated_capability_boundary_required"
    assert detail["governed"] is True
    assert "gateway_process" not in response.text


def test_capability_worker_rejects_gateway_process_boundary_even_when_isolated() -> None:
    secret = "worker-secret"
    payload = json.loads(_request_body().decode("utf-8"))
    payload["boundary"]["isolation_required"] = True
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
    detail = response.json()["detail"]
    assert detail["error"] == "isolated worker execution plane required"
    assert detail["error_code"] == "isolated_worker_execution_plane_required"
    assert detail["governed"] is True
    assert "gateway_process" not in response.text


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
