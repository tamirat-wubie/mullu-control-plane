"""Purpose: governed tool gateway with causal ledger receipts.
Governance scope: tool invocation admission, permission-decision binding,
hash-only payload evidence, and append-only causal trace emission.
Dependencies: governed tool registry and causal runtime ledger.
Invariants:
  - Cause references are validated before tool execution.
  - Every allowed, denied, or failed invocation produces a receipt.
  - Receipts bind input hash, output hash, ledger event id, and permission reason.
  - Raw tool arguments and outputs are not written to the causal ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .causal_runtime_ledger import CausalLedgerEvent, CausalRuntimeLedger, hash_runtime_payload
from .governed_tool_use import GovernedToolRegistry, ToolDefinition, ToolInvocationResult
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


@dataclass(frozen=True, slots=True)
class ToolGatewayRequest:
    """Tenant-bound request for one governed tool invocation."""

    tenant_id: str
    actor_id: str
    session_id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    budget_ref: str = "default"
    correlation_id: str = ""
    cause_event_ids: tuple[str, ...] = ()
    approval_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("tenant_id", "actor_id", "session_id", "tool_name", "budget_ref"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, str(getattr(self, field_name))),
            )
        if not isinstance(self.arguments, Mapping):
            raise RuntimeCoreInvariantError("arguments must be an object")
        if not isinstance(self.metadata, Mapping):
            raise RuntimeCoreInvariantError("metadata must be an object")
        correlation_id = self.correlation_id or self.session_id
        object.__setattr__(self, "correlation_id", ensure_non_empty_text("correlation_id", correlation_id))
        object.__setattr__(self, "arguments", dict(self.arguments))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ToolGatewayReceipt:
    """Receipt for a governed tool gateway invocation."""

    receipt_id: str
    ledger_event_id: str
    ledger_event_hash: str
    tenant_id: str
    actor_id: str
    session_id: str
    tool_name: str
    status: str
    input_hash: str
    output_hash: str
    permission_id: str = ""
    reason_codes: tuple[str, ...] = ()
    occurred_at: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "ledger_event_id",
            "ledger_event_hash",
            "tenant_id",
            "actor_id",
            "session_id",
            "tool_name",
            "status",
            "input_hash",
            "output_hash",
            "occurred_at",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, str(getattr(self, field_name))),
            )


@dataclass(frozen=True, slots=True)
class ToolGatewayResult:
    """Tool gateway result with registry decision and causal receipt."""

    allowed: bool
    status: str
    registry_result: ToolInvocationResult
    receipt: ToolGatewayReceipt
    ledger_event: CausalLedgerEvent


class GovernedToolGateway:
    """Execute tools through governance and record causal ledger receipts."""

    def __init__(
        self,
        *,
        registry: GovernedToolRegistry | None = None,
        ledger: CausalRuntimeLedger,
    ) -> None:
        self._registry = registry or GovernedToolRegistry(clock=lambda: "")
        self._ledger = ledger

    @property
    def ledger(self) -> CausalRuntimeLedger:
        """Return the bound causal runtime ledger."""
        return self._ledger

    @property
    def registry(self) -> GovernedToolRegistry:
        """Return the bound governed tool registry."""
        return self._registry

    def register(
        self,
        tool: ToolDefinition,
        *,
        executor: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        """Register a tool with the underlying governed registry."""
        self._registry.register(tool, executor=executor)

    def invoke(
        self,
        request: ToolGatewayRequest,
        *,
        executor: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> ToolGatewayResult:
        """Invoke a tool and append one causal ledger event for the result."""
        self._ledger.validate_causes(request.cause_event_ids)
        input_hash = hash_runtime_payload(
            {
                "tool_name": request.tool_name,
                "tenant_id": request.tenant_id,
                "actor_id": request.actor_id,
                "arguments": dict(request.arguments),
            }
        )
        registry_result = self._registry.invoke(
            request.tool_name,
            dict(request.arguments),
            executor=executor,
            session_id=request.session_id,
            tenant_id=request.tenant_id,
            budget_ref=request.budget_ref,
            audit_present=True,
        )
        status = _status_for_registry_result(registry_result)
        output_hash = hash_runtime_payload(_receipt_output_payload(registry_result, status))
        permission_id = ""
        reason_codes: tuple[str, ...] = ()
        if registry_result.permission_decision is not None:
            permission_id = registry_result.permission_decision.permission_id
            reason_codes = tuple(str(reason) for reason in registry_result.permission_decision.reason_codes)
        event = self._ledger.append(
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            surface="tool_gateway",
            action="tool.invoke",
            outcome=status,
            correlation_id=request.correlation_id,
            cause_event_ids=request.cause_event_ids,
            input_hash=input_hash,
            output_hash=output_hash,
            constraint_refs=_constraint_refs(
                request=request,
                registry_result=registry_result,
                reason_codes=reason_codes,
            ),
            proof_refs=_proof_refs(request=request, registry_result=registry_result),
            metadata={
                "tool_name": request.tool_name,
                "session_id": request.session_id,
                "budget_ref": request.budget_ref,
                "approval_id": request.approval_id,
                "permission_id": permission_id,
                "reason_codes": reason_codes,
                "gateway_metadata": dict(request.metadata),
            },
        )
        receipt_payload = {
            "ledger_event_id": event.event_id,
            "ledger_event_hash": event.event_hash,
            "tenant_id": request.tenant_id,
            "actor_id": request.actor_id,
            "session_id": request.session_id,
            "tool_name": request.tool_name,
            "status": status,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "permission_id": permission_id,
            "reason_codes": reason_codes,
            "occurred_at": event.occurred_at,
        }
        receipt_hash = hash_runtime_payload(receipt_payload)
        receipt = ToolGatewayReceipt(
            receipt_id=f"tool-gateway-receipt-{receipt_hash[:16]}",
            **receipt_payload,
        )
        return ToolGatewayResult(
            allowed=registry_result.allowed,
            status=status,
            registry_result=registry_result,
            receipt=receipt,
            ledger_event=event,
        )


def _status_for_registry_result(result: ToolInvocationResult) -> str:
    if not result.allowed:
        return "denied"
    if result.error:
        return "failed"
    return "succeeded"


def _receipt_output_payload(result: ToolInvocationResult, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "allowed": result.allowed,
        "result": result.result if result.allowed and not result.error else None,
        "error": result.error,
    }


def _constraint_refs(
    *,
    request: ToolGatewayRequest,
    registry_result: ToolInvocationResult,
    reason_codes: tuple[str, ...],
) -> tuple[str, ...]:
    refs = [f"tool:{request.tool_name}", f"budget:{request.budget_ref}"]
    if registry_result.permission_decision is not None:
        refs.append(f"permission:{registry_result.permission_decision.permission_id}")
    refs.extend(f"reason:{reason}" for reason in reason_codes)
    if not registry_result.allowed and registry_result.permission_decision is None:
        refs.append(f"denial:{registry_result.error}")
    return tuple(refs)


def _proof_refs(
    *,
    request: ToolGatewayRequest,
    registry_result: ToolInvocationResult,
) -> tuple[str, ...]:
    refs = [f"causal-tool-call:{request.session_id}:{request.tool_name}"]
    if request.approval_id:
        refs.append(f"approval:{request.approval_id}")
    if registry_result.audit_id:
        refs.append(f"audit:{registry_result.audit_id}")
    return tuple(refs)


def tool_gateway_receipt_json(receipt: ToolGatewayReceipt) -> dict[str, Any]:
    """Return a JSON-ready receipt for operator evidence bundles."""
    payload = asdict(receipt)
    payload["reason_codes"] = list(receipt.reason_codes)
    return payload
