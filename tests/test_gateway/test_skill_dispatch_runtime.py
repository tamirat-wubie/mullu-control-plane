"""Gateway skill dispatcher runtime binding tests.

Tests: platform-backed provider injection for governed skill dispatch.
"""

from decimal import Decimal
from dataclasses import dataclass, field
from typing import Any
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.intent_resolver import CapabilityIntentResolver  # noqa: E402
from gateway.skill_dispatch import (  # noqa: E402
    SkillDispatcher,
    SkillIntent,
    build_skill_dispatcher_from_platform,
    register_computer_capabilities,
)
from gateway.capability_isolation import (  # noqa: E402
    CapabilityExecutionBoundary,
    CapabilityExecutionRequest,
    CapabilityExecutionReceipt,
    CapabilityExecutionResponse,
    CapabilityIsolationPolicy,
    CapabilityWorkerTransport,
    HttpCapabilityWorkerTransport,
    LocalCapabilityExecutionWorker,
    RemoteCapabilityExecutionExecutor,
    build_isolated_capability_executor_from_env,
    capability_execution_response_payload,
    sign_capability_payload,
)
from gateway.command_spine import canonical_hash, capability_passport_for  # noqa: E402
from gateway.mcp_capabilities import register_mcp_capabilities  # noqa: E402
from mcoi_runtime.contracts.governed_capability_fabric import (  # noqa: E402
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)
from mcoi_runtime.mcp import (  # noqa: E402
    GovernedMCPExecutor,
    MCPToolCallResult,
    MCPToolDescriptor,
    import_mcp_tool_as_capability,
)
from skills.financial.providers.base import AccountInfo, StubFinancialProvider  # noqa: E402


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


class ApprovingPaymentExecutor:
    def initiate_payment(self, *, tenant_id, amount, currency, destination, actor_id, description=""):
        return PaymentResult(
            success=True,
            tx_id="tx-123",
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
            provider_tx_id="provider-123",
            metadata={
                "ledger_hash": "ledger-proof-123",
                "recipient_hash": "recipient-proof-123",
                "recipient_ref": "dest:pending",
            },
        )

    def refund(self, tx_id, *, reason="", actor_id="", api_key=""):
        return PaymentResult(
            success=True,
            tx_id=tx_id,
            state="refunded",
            amount="50",
            currency="USD",
            provider_tx_id="refund-123",
            metadata={"ledger_hash": "refund-ledger-proof-123"},
        )


class FailingRefundExecutor:
    def refund(self, tx_id, *, reason="", actor_id="", api_key=""):
        return PaymentResult(
            success=False,
            tx_id=tx_id,
            state="refund_failed",
            amount="50",
            currency="USD",
            error="provider rejected refund",
        )


class StubCapabilityWorkerTransport(CapabilityWorkerTransport):
    """Transport stub that returns a valid restricted-worker receipt."""

    def __init__(self) -> None:
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        result = {
            "response": "Payment processed: tx-remote-1",
            "governed": True,
            "skill": "send_payment",
            "receipt_status": "settled",
            "transaction_id": "tx-remote-1",
            "amount": "50",
            "currency": "USD",
            "provider_transaction_id": "provider-remote-1",
            "ledger_hash": "ledger-remote-proof",
            "recipient_hash": "recipient-remote-proof",
            "recipient_ref": "dest:pending",
        }
        output_hash = canonical_hash(result)
        receipt_hash = canonical_hash({
            "request_id": request.request_id,
            "input_hash": request.input_hash,
            "output_hash": output_hash,
        })
        return CapabilityExecutionResponse(
            request_id=request.request_id,
            status="succeeded",
            result=result,
            receipt=CapabilityExecutionReceipt(
                receipt_id=f"capability-receipt-{receipt_hash[:16]}",
                capability_id=request.boundary.capability_id,
                execution_plane=request.boundary.execution_plane,
                isolation_required=request.boundary.isolation_required,
                worker_id="restricted-worker-1",
                input_hash=request.input_hash,
                output_hash=output_hash,
                evidence_refs=(f"restricted_worker:{receipt_hash[:16]}",),
            ),
        )


class PlatformWithFinancialProvider:
    """Platform stub exposing a direct financial provider."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self._financial_provider = provider


class CapabilityRuntime:
    """Nested runtime stub exposing a governed financial provider."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self.financial_provider = provider


class PlatformWithCapabilityRuntime:
    """Platform stub exposing providers through a capability runtime."""

    def __init__(self, provider: StubFinancialProvider) -> None:
        self.capability_runtime = CapabilityRuntime(provider)


class ExactCapabilityRegistry:
    """Registry stub that records exact capability lookup keys."""

    def __init__(self, admitted: set[str]) -> None:
        self.admitted = admitted
        self.lookups: list[tuple[str, str]] = []

    def find_agents_with_capability(self, capability_id: str, tenant_id: str) -> list[str]:
        self.lookups.append((capability_id, tenant_id))
        return ["agent-1"] if capability_id in self.admitted else []


class StubMCPClient:
    """MCP client fixture for dispatcher integration tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call_tool(self, *, server_id: str, tool_name: str, arguments: dict[str, Any]) -> MCPToolCallResult:
        self.calls.append({
            "server_id": server_id,
            "tool_name": tool_name,
            "arguments": dict(arguments),
        })
        return MCPToolCallResult(
            content={"issue_id": "ISSUE-1"},
            metadata={"provider_request_id": "provider-1"},
        )


class StubSandboxRunner:
    """Sandbox runner fixture that records governed command requests."""

    def __init__(self) -> None:
        self.requests: list[Any] = []

    def execute(self, request):
        from gateway.sandbox_runner import SandboxExecutionReceipt, SandboxCommandResult

        self.requests.append(request)
        receipt = SandboxExecutionReceipt(
            receipt_id="sandbox-receipt-test",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            capability_id=request.capability_id,
            sandbox_id="docker-rootless",
            image="mullu-agent-runner:latest",
            command_hash="command-hash",
            docker_args_hash="docker-args-hash",
            stdout_hash="stdout-hash",
            stderr_hash="stderr-hash",
            returncode=0,
            network_disabled=True,
            read_only_rootfs=True,
            workspace_mount="/workspace",
            forbidden_effects_observed=False,
            changed_file_count=0,
            changed_file_refs=(),
            verification_status="passed",
            evidence_refs=("sandbox_execution:test",),
        )
        return SandboxCommandResult(status="succeeded", stdout="ok", stderr="", receipt=receipt)


class StubCodeAdapter:
    """Workspace adapter fixture for computer capability dispatch."""

    def list_files(self, repo_id, extensions=()):
        file_item = type(
            "File",
            (),
            {
                "relative_path": "src/app.py",
                "content_hash": "content-hash",
                "size_bytes": 10,
                "line_count": 1,
            },
        )()
        return type(
            "Workspace",
            (),
            {
                "root_path": "/workspace",
                "files": (file_item,),
                "total_files": 1,
                "total_bytes": 10,
            },
        )()


def _seeded_provider() -> StubFinancialProvider:
    provider = StubFinancialProvider()
    provider.seed_account(
        "tenant-1",
        AccountInfo(
            account_id="acct-1",
            name="Operating",
            account_type="checking",
            currency="USD",
            balance=Decimal("125.50"),
        ),
    )
    return provider


def _certified_mcp_capability() -> CapabilityRegistryEntry:
    candidate = import_mcp_tool_as_capability(
        MCPToolDescriptor(
            server_id="GitHub Enterprise",
            name="Create Issue",
            description="Create a repository issue.",
            input_schema={
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        )
    )
    return CapabilityRegistryEntry(
        capability_id=candidate.capability_id,
        domain=candidate.domain,
        version=candidate.version,
        input_schema_ref=candidate.input_schema_ref,
        output_schema_ref=candidate.output_schema_ref,
        effect_model=candidate.effect_model,
        evidence_model=candidate.evidence_model,
        authority_policy=candidate.authority_policy,
        isolation_profile=candidate.isolation_profile,
        recovery_plan=candidate.recovery_plan,
        cost_model=candidate.cost_model,
        obligation_model=candidate.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=candidate.metadata,
        extensions=candidate.extensions,
    )


def test_dispatcher_uses_direct_platform_financial_provider() -> None:
    dispatcher = build_skill_dispatcher_from_platform(
        PlatformWithFinancialProvider(_seeded_provider()),
    )

    result = dispatcher.dispatch(
        SkillIntent("financial", "balance_check", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["governed"] is True
    assert "Operating" in result["response"]
    assert "125.50" in result["response"]


def test_dispatcher_uses_nested_capability_runtime_provider() -> None:
    dispatcher = build_skill_dispatcher_from_platform(
        PlatformWithCapabilityRuntime(_seeded_provider()),
    )

    result = dispatcher.dispatch(
        SkillIntent("financial", "balance_check", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "balance_check"
    assert "USD" in result["response"]
    assert "Operating" in result["response"]


def test_payment_dispatcher_emits_settled_effect_receipts() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "send_payment", {"amount": "50"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "send_payment"
    assert result["receipt_status"] == "settled"
    assert result["transaction_id"] == "tx-123"
    assert result["amount"] == "50"
    assert result["currency"] == "USD"
    assert result["recipient_hash"] == "recipient-proof-123"
    assert result["ledger_hash"] == "ledger-proof-123"


def test_refund_dispatcher_emits_refund_effect_receipts() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "refund", {"transaction_id": "tx-123"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "refund"
    assert result["receipt_status"] == "refunded"
    assert result["refund_id"] == "refund-123"
    assert result["transaction_id"] == "tx-123"
    assert result["ledger_hash"] == "refund-ledger-proof-123"


def test_refund_dispatcher_requires_transaction_id() -> None:
    dispatcher = SkillDispatcher(payment_executor=ApprovingPaymentExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "refund", {"transaction_id": ""}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "refund"
    assert result["receipt_status"] == "missing_transaction_id"


def test_refund_dispatcher_returns_failed_receipt_without_success_fields() -> None:
    dispatcher = SkillDispatcher(payment_executor=FailingRefundExecutor())

    result = dispatcher.dispatch(
        SkillIntent("financial", "refund", {"transaction_id": "tx-123"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["skill"] == "refund"
    assert result["receipt_status"] == "failed"
    assert result["transaction_id"] == "tx-123"
    assert "refund_id" not in result


def test_dispatcher_admits_exact_capability_id_not_domain() -> None:
    registry = ExactCapabilityRegistry({"financial.balance_check"})
    dispatcher = build_skill_dispatcher_from_platform(
        PlatformWithFinancialProvider(_seeded_provider()),
    )
    dispatcher._capability_registry = registry

    result = dispatcher.dispatch(
        SkillIntent("financial", "balance_check", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert registry.lookups == [("financial.balance_check", "tenant-1")]
    assert result["capability_id"] == "financial.balance_check"


def test_dispatcher_blocks_unadmitted_exact_capability() -> None:
    registry = ExactCapabilityRegistry({"financial.balance_check"})
    dispatcher = SkillDispatcher(
        payment_executor=ApprovingPaymentExecutor(),
        capability_registry=registry,
    )

    result = dispatcher.dispatch(
        SkillIntent("financial", "send_payment", {"amount": "50"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert registry.lookups == [("financial.send_payment", "tenant-1")]
    assert result["routed"] is False
    assert result["capability_id"] == "financial.send_payment"


def test_intent_resolver_supports_explicit_non_financial_capability() -> None:
    resolver = CapabilityIntentResolver()

    intent = resolver.resolve('/run enterprise.task_schedule {"title": "Review report"}')

    assert intent is not None
    assert intent.capability_id == "enterprise.task_schedule"
    assert intent.params["title"] == "Review report"


def test_dispatcher_executes_registered_enterprise_capability() -> None:
    dispatcher = build_skill_dispatcher_from_platform(None)

    result = dispatcher.dispatch(
        SkillIntent("enterprise", "task_schedule", {"title": "Review generated report"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "enterprise.task_schedule"
    assert result["receipt_status"] == "scheduled"
    assert result["task_id"].startswith("task-")


def test_computer_command_run_uses_sandbox_runner() -> None:
    sandbox_runner = StubSandboxRunner()
    dispatcher = SkillDispatcher()
    register_computer_capabilities(dispatcher, sandbox_runner=sandbox_runner)

    result = dispatcher.dispatch(
        SkillIntent("computer", "command.run", {"argv": ["python", "--version"]}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        command_id="cmd-computer-1",
    )

    assert result is not None
    assert result["capability_id"] == "computer.command.run"
    assert result["receipt_status"] == "succeeded"
    assert result["sandbox_receipt_id"] == "sandbox-receipt-test"
    assert result["verification_status"] == "passed"
    assert result["sandbox_execution_receipt"]["network_disabled"] is True
    assert result["sandbox_execution_receipt"]["workspace_mount"] == "/workspace"
    assert sandbox_runner.requests[0].capability_id == "computer.command.run"
    assert sandbox_runner.requests[0].argv == ("python", "--version")


def test_computer_command_run_fails_closed_without_sandbox_runner() -> None:
    dispatcher = SkillDispatcher()
    register_computer_capabilities(dispatcher)

    result = dispatcher.dispatch(
        SkillIntent("computer", "command.run", {"argv": ["python", "--version"]}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "computer.command.run"
    assert result["receipt_status"] == "sandbox_unavailable"


def test_computer_filesystem_observe_uses_workspace_adapter() -> None:
    dispatcher = SkillDispatcher()
    register_computer_capabilities(dispatcher, code_adapter=StubCodeAdapter())

    result = dispatcher.dispatch(
        SkillIntent("computer", "filesystem.observe", {}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "computer.filesystem.observe"
    assert result["receipt_status"] == "observed"
    assert result["file_count"] == 1
    assert result["workspace_root_hash"]
    assert result["files"][0]["relative_path"] == "src/app.py"


def test_dispatcher_executes_registered_governed_mcp_capability() -> None:
    dispatcher = SkillDispatcher()
    client = StubMCPClient()
    executor = GovernedMCPExecutor(client, clock=lambda: "2026-04-29T12:00:00+00:00")
    capability = _certified_mcp_capability()

    registered = register_mcp_capabilities(
        dispatcher,
        capabilities=(capability,),
        executor=executor,
    )
    result = dispatcher.dispatch(
        SkillIntent("mcp", "github_enterprise_create_issue", {"title": "Fix bridge"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        command_id="cmd-1",
        metadata={
            "approval_id": "approval-1",
            "budget_reservation_id": "budget-1",
            "isolation_boundary_id": "isolation-1",
        },
    )

    assert registered == ("mcp.github_enterprise_create_issue",)
    assert result is not None
    assert result["capability_id"] == "mcp.github_enterprise_create_issue"
    assert result["receipt_status"] == "succeeded"
    assert result["mcp_succeeded"] is True
    assert result["mcp_output"] == {"issue_id": "ISSUE-1"}
    assert result["mcp_execution_receipt"]["command_id"] == "cmd-1"
    assert result["mcp_execution_receipt"]["approval_id"] == "approval-1"
    assert result["mcp_execution_receipt"]["budget_reservation_id"] == "budget-1"
    assert result["mcp_execution_receipt"]["isolation_boundary_id"] == "isolation-1"
    assert result["input_hash"]
    assert result["output_hash"]
    assert result["evidence_refs"]
    assert executor.audit_records(status="succeeded")[0].command_id == "cmd-1"
    assert client.calls == [{
        "server_id": "GitHub Enterprise",
        "tool_name": "Create Issue",
        "arguments": {"title": "Fix bridge"},
    }]


def test_dispatcher_rejects_governed_mcp_capability_without_witness_metadata() -> None:
    dispatcher = SkillDispatcher()
    client = StubMCPClient()
    executor = GovernedMCPExecutor(client)
    register_mcp_capabilities(
        dispatcher,
        capabilities=(_certified_mcp_capability(),),
        executor=executor,
    )

    with pytest.raises(ValueError, match="approval_id is required for governed MCP execution"):
        dispatcher.dispatch(
            SkillIntent("mcp", "github_enterprise_create_issue", {"title": "Fix bridge"}),
            tenant_id="tenant-1",
            identity_id="identity-1",
            command_id="cmd-1",
        )

    assert client.calls == []
    assert executor.audit_records() == ()


def test_capability_isolation_marks_payment_as_isolated() -> None:
    policy = CapabilityIsolationPolicy(environment="pilot")
    boundary = policy.boundary_for(capability_passport_for("financial.send_payment"))

    assert boundary.isolation_required is True
    assert boundary.execution_plane == "isolated_worker"
    assert boundary.network_policy == ("payment_provider",)
    assert boundary.filesystem_policy == "read_only"
    assert boundary.evidence_required


def test_local_capability_worker_emits_execution_receipt() -> None:
    worker = LocalCapabilityExecutionWorker(
        SkillDispatcher(payment_executor=ApprovingPaymentExecutor()),
        worker_id="test-worker",
    )
    boundary = CapabilityIsolationPolicy(environment="local_dev").boundary_for(
        capability_passport_for("financial.send_payment"),
    )

    result, receipt = worker.execute(
        intent=SkillIntent("financial", "send_payment", {"amount": "50"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        boundary=boundary,
    )

    assert result is not None
    assert result["receipt_status"] == "settled"
    assert result["capability_execution_receipt"]["receipt_id"] == receipt.receipt_id
    assert receipt.worker_id == "test-worker"
    assert receipt.isolation_required is True
    assert receipt.evidence_refs


def test_remote_capability_executor_validates_worker_receipt() -> None:
    transport = StubCapabilityWorkerTransport()
    executor = RemoteCapabilityExecutionExecutor(transport)
    boundary = CapabilityIsolationPolicy(environment="pilot").boundary_for(
        capability_passport_for("financial.send_payment"),
    )

    result, receipt = executor.execute(
        intent=SkillIntent("financial", "send_payment", {"amount": "50"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        boundary=boundary,
    )

    assert result is not None
    assert result["receipt_status"] == "settled"
    assert result["capability_execution_request_id"].startswith("capability-request-")
    assert result["capability_execution_receipt"]["receipt_id"] == receipt.receipt_id
    assert receipt.worker_id == "restricted-worker-1"
    assert receipt.evidence_refs[0].startswith("restricted_worker:")
    assert len(transport.requests) == 1


def test_isolated_capability_executor_env_requires_complete_transport(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_WORKER_URL", "https://worker.invalid/execute")
    monkeypatch.delenv("MULLU_CAPABILITY_WORKER_SECRET", raising=False)

    with pytest.raises(ValueError, match="^capability worker signing secret is required$"):
        build_isolated_capability_executor_from_env()


def test_http_capability_transport_verifies_response_signature(monkeypatch) -> None:
    secret = "transport-secret"
    boundary = CapabilityExecutionBoundary(
        capability_id="financial.send_payment",
        execution_plane="isolated_worker",
        isolation_required=True,
        network_policy=("payment_provider",),
        filesystem_policy="read_only",
        max_runtime_seconds=30,
        max_memory_mb=256,
        service_account="capability-financial-send_payment",
        evidence_required=("ledger_hash",),
    )
    request = CapabilityExecutionRequest(
        request_id="capability-request-transport",
        tenant_id="tenant-1",
        identity_id="identity-1",
        intent={"skill": "financial", "action": "send_payment", "params": {"amount": "50"}},
        boundary=boundary,
        input_hash="input-hash",
    )
    result = {"response": "ok", "receipt_status": "settled"}
    receipt = CapabilityExecutionReceipt(
        receipt_id="capability-receipt-transport",
        capability_id=boundary.capability_id,
        execution_plane=boundary.execution_plane,
        isolation_required=True,
        worker_id="restricted-worker-1",
        input_hash=request.input_hash,
        output_hash=canonical_hash(result),
        evidence_refs=("restricted_worker:transport",),
    )
    response_payload = capability_execution_response_payload(
        CapabilityExecutionResponse(
            request_id=request.request_id,
            status="succeeded",
            result=result,
            receipt=receipt,
        ),
    )
    response_body = json.dumps(response_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    class StubHttpResponse:
        headers = {"X-Mullu-Capability-Response-Signature": sign_capability_payload(response_body, secret)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    transport = HttpCapabilityWorkerTransport(
        endpoint_url="https://worker.invalid/capability/execute",
        signing_secret=secret,
    )

    response = transport.submit(request)

    assert response.status == "succeeded"
    assert response.receipt.receipt_id == "capability-receipt-transport"
    assert response.receipt.evidence_refs == ("restricted_worker:transport",)


def test_http_capability_transport_rejects_bad_response_signature(monkeypatch) -> None:
    secret = "transport-secret"
    boundary = CapabilityExecutionBoundary(
        capability_id="financial.send_payment",
        execution_plane="isolated_worker",
        isolation_required=True,
        network_policy=("payment_provider",),
        filesystem_policy="read_only",
        max_runtime_seconds=30,
        max_memory_mb=256,
        service_account="capability-financial-send_payment",
        evidence_required=("ledger_hash",),
    )
    request = CapabilityExecutionRequest(
        request_id="capability-request-transport",
        tenant_id="tenant-1",
        identity_id="identity-1",
        intent={"skill": "financial", "action": "send_payment", "params": {"amount": "50"}},
        boundary=boundary,
        input_hash="input-hash",
    )
    response_body = b'{"request_id":"capability-request-transport"}'

    class StubHttpResponse:
        headers = {"X-Mullu-Capability-Response-Signature": "hmac-sha256:bad"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr("urllib.request.urlopen", lambda http_request, timeout: StubHttpResponse())
    transport = HttpCapabilityWorkerTransport(
        endpoint_url="https://worker.invalid/capability/execute",
        signing_secret=secret,
    )

    with pytest.raises(RuntimeError, match="^capability worker response signature invalid$"):
        transport.submit(request)
