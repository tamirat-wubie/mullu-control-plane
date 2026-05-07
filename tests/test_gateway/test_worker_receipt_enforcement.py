"""Worker receipt enforcement tests.

Purpose: verify shell/browser/computer capabilities cannot execute without an
    isolated worker boundary and a kernel-validated receipt.
Governance scope: gateway worker receipt enforcement only.
Dependencies: gateway router, command spine, capability isolation.
Invariants:
  - Worker-bound adapter capabilities receive fail-closed passports.
  - Pilot/prod runtimes block worker-bound capabilities without a worker.
  - Malformed isolated-worker receipts cannot close as successful execution.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_dispatch import CapabilityDispatcher, FunctionCapabilityHandler  # noqa: E402
from gateway.capability_isolation import CapabilityExecutionReceipt, CapabilityIsolationPolicy  # noqa: E402
from gateway.command_spine import capability_passport_for  # noqa: E402
from gateway.router import GatewayMessage, GatewayRouter, TenantMapping  # noqa: E402


class StubPlatform:
    """Minimal governed platform fixture."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "not used", "succeeded": True, "error": ""})()

    def close(self) -> None:
        return None


class BadReceiptWorker:
    """Worker fixture that returns a mismatched receipt."""

    def execute(
        self,
        *,
        intent,
        tenant_id: str,
        identity_id: str,
        boundary,
        command_id: str = "",
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        return {
            "response": "worker should not be trusted",
            "governed": True,
            "receipt_status": "succeeded",
            "command_id": command_id,
        }, CapabilityExecutionReceipt(
            receipt_id="capability-receipt-bad",
            capability_id="browser.open",
            execution_plane="gateway_process",
            isolation_required=False,
            worker_id="bad-worker",
            input_hash="input-hash",
            output_hash="output-hash",
            evidence_refs=("bad-worker:receipt",),
        )


def _dispatcher_with_browser_handler() -> CapabilityDispatcher:
    dispatcher = CapabilityDispatcher()
    dispatcher.register(FunctionCapabilityHandler(
        "browser.open",
        lambda context, params: {
            "response": "browser opened",
            "receipt_status": "succeeded",
            "url": params.get("url", ""),
        },
    ))
    return dispatcher


def test_worker_bound_passports_force_isolated_worker_boundary() -> None:
    browser_passport = capability_passport_for("browser.open")
    computer_passport = capability_passport_for("computer.command.run")
    shell_passport = capability_passport_for("shell.command.run")
    policy = CapabilityIsolationPolicy(environment="production")

    browser_boundary = policy.boundary_for(browser_passport)
    computer_boundary = policy.boundary_for(computer_passport)
    shell_boundary = policy.boundary_for(shell_passport)

    assert browser_passport.requires[-1] == "signed_worker_receipt"
    assert browser_boundary.isolation_required is True
    assert browser_boundary.execution_plane == "isolated_worker"
    assert browser_boundary.network_policy == ("browser_egress_allowlist",)
    assert computer_boundary.isolation_required is True
    assert computer_boundary.network_policy == ("deny_all",)
    assert shell_boundary.isolation_required is True
    assert shell_boundary.network_policy == ("deny_all",)


def test_pilot_browser_capability_blocks_without_isolated_worker() -> None:
    router = GatewayRouter(
        platform=StubPlatform(),
        capability_dispatcher=_dispatcher_with_browser_handler(),
        environment="pilot",
    )
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-1",
        tenant_id="tenant-1",
        identity_id="actor-1",
    ))

    response = router.handle_message(GatewayMessage(
        message_id="msg-worker-1",
        channel="web",
        sender_id="user-1",
        body='/run browser.open {"url":"https://example.com"}',
    ))

    assert response.metadata["error"] == "isolation_worker_required"
    assert response.metadata["receipt_status"] == "isolation_worker_required"
    assert response.metadata["closure_disposition"] == "requires_review"
    assert response.metadata["success_claim_allowed"] is False
    assert response.metadata["capability_execution_boundary"]["execution_plane"] == "isolated_worker"


def test_mismatched_worker_receipt_fails_closed_before_terminal_success() -> None:
    router = GatewayRouter(
        platform=StubPlatform(),
        capability_dispatcher=_dispatcher_with_browser_handler(),
        environment="pilot",
        isolated_capability_executor=BadReceiptWorker(),
    )
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-2",
        tenant_id="tenant-1",
        identity_id="actor-2",
    ))

    response = router.handle_message(GatewayMessage(
        message_id="msg-worker-2",
        channel="web",
        sender_id="user-2",
        body='/run browser.open {"url":"https://example.com"}',
    ))

    assert response.metadata["closure_response_kind"] == "review"
    assert response.metadata["error"] == "capability_worker_receipt_invalid"
    assert response.metadata["success_claim_allowed"] is False
    assert response.metadata["closure_disposition"] == "requires_review"
    assert response.metadata["terminal_certificate_id"]
    assert "capability_execution_receipt" not in response.metadata
    assert router.error_count >= 1
