"""Purpose: execute certified imported MCP capabilities through governance.
Governance scope: MCP capability certification, approval witness, budget
reservation, isolation boundary, and execution receipt evidence.
Dependencies: governed capability fabric contracts and command spine hashing.
Invariants:
  - Only certified MCP-backed capabilities can execute.
  - Execution requires command, approval, budget, and isolation witnesses.
  - External MCP output is wrapped in a deterministic receipt.
  - Failed MCP tool calls still produce bounded evidence receipts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol

from gateway.command_spine import canonical_hash
from mcoi_runtime.contracts._base import thaw_value_json
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)


@dataclass(frozen=True, slots=True)
class GovernedMCPExecutionContext:
    """Governance witnesses required before calling an MCP tool."""

    tenant_id: str
    identity_id: str
    command_id: str
    approval_id: str
    budget_reservation_id: str
    isolation_boundary_id: str
    terminal_certificate_required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "tenant_id",
            "identity_id",
            "command_id",
            "approval_id",
            "budget_reservation_id",
            "isolation_boundary_id",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if not isinstance(self.terminal_certificate_required, bool):
            raise ValueError("terminal_certificate_required must be a boolean")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object")


@dataclass(frozen=True, slots=True)
class MCPToolCallResult:
    """Bounded result returned by an MCP client adapter."""

    content: Any
    is_error: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.is_error, bool):
            raise ValueError("is_error must be a boolean")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object")


@dataclass(frozen=True, slots=True)
class GovernedMCPExecutionReceipt:
    """Receipt proving one governed MCP tool invocation."""

    receipt_id: str
    capability_id: str
    server_id: str
    tool_name: str
    command_id: str
    approval_id: str
    budget_reservation_id: str
    isolation_boundary_id: str
    input_hash: str
    output_hash: str
    status: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernedMCPExecutionResult:
    """Execution result plus evidence receipt for MCP capability calls."""

    succeeded: bool
    output: Any
    receipt: GovernedMCPExecutionReceipt
    error: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class MCPToolClient(Protocol):
    """Client adapter used to invoke an external MCP server."""

    def call_tool(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> MCPToolCallResult:
        """Call one MCP tool and return bounded output."""
        ...


class GovernedMCPExecutor:
    """Execute certified MCP capabilities behind governance witnesses."""

    def __init__(self, client: MCPToolClient, *, worker_id: str = "governed-mcp-executor") -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self._client = client
        self._worker_id = worker_id

    def execute(
        self,
        *,
        capability: CapabilityRegistryEntry,
        context: GovernedMCPExecutionContext,
        params: Mapping[str, Any],
    ) -> GovernedMCPExecutionResult:
        """Execute one certified imported MCP capability."""
        if not isinstance(params, Mapping):
            raise ValueError("params must be an object")
        mcp_descriptor = _mcp_descriptor_for_execution(capability)
        server_id = str(mcp_descriptor["server_id"])
        tool_name = str(mcp_descriptor["tool_name"])
        arguments = dict(thaw_value_json(params))
        input_hash = canonical_hash({
            "capability_id": capability.capability_id,
            "server_id": server_id,
            "tool_name": tool_name,
            "tenant_id": context.tenant_id,
            "identity_id": context.identity_id,
            "command_id": context.command_id,
            "arguments": arguments,
        })
        try:
            call_result = self._client.call_tool(
                server_id=server_id,
                tool_name=tool_name,
                arguments=arguments,
            )
            content = call_result.content
            is_error = call_result.is_error
            call_metadata = call_result.metadata
        except Exception:
            content = {"error": "mcp_tool_call_exception"}
            is_error = True
            call_metadata = {}
        output_payload = {
            "content": thaw_value_json(content),
            "is_error": is_error,
            "metadata": thaw_value_json(call_metadata),
        }
        output_hash = canonical_hash(output_payload)
        status = "failed" if is_error else "succeeded"
        receipt = _receipt(
            capability=capability,
            context=context,
            server_id=server_id,
            tool_name=tool_name,
            input_hash=input_hash,
            output_hash=output_hash,
            status=status,
            worker_id=self._worker_id,
        )
        return GovernedMCPExecutionResult(
            succeeded=not is_error,
            output=content,
            receipt=receipt,
            error="mcp_tool_call_failed" if is_error else "",
            metadata={
                "mcp_call_metadata": dict(thaw_value_json(call_metadata)),
                "mcp_execution_receipt": asdict(receipt),
                "terminal_certificate_required": context.terminal_certificate_required,
            },
        )


def _mcp_descriptor_for_execution(entry: CapabilityRegistryEntry) -> Mapping[str, Any]:
    if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
        raise ValueError("MCP capability execution requires certified capability")
    if entry.domain != "mcp":
        raise ValueError("MCP capability execution requires mcp domain")
    if entry.evidence_model.terminal_certificate_required is not True:
        raise ValueError("MCP capability execution requires terminal certificate evidence")
    mcp_extension = entry.extensions.get("mcp") if isinstance(entry.extensions, Mapping) else None
    if not isinstance(mcp_extension, Mapping):
        raise ValueError("MCP capability extension is required")
    server_id = str(mcp_extension.get("server_id", "")).strip()
    tool_name = str(mcp_extension.get("tool_name", "")).strip()
    if not server_id or not tool_name:
        raise ValueError("MCP capability extension must include server_id and tool_name")
    return mcp_extension


def _receipt(
    *,
    capability: CapabilityRegistryEntry,
    context: GovernedMCPExecutionContext,
    server_id: str,
    tool_name: str,
    input_hash: str,
    output_hash: str,
    status: str,
    worker_id: str,
) -> GovernedMCPExecutionReceipt:
    payload = {
        "capability_id": capability.capability_id,
        "server_id": server_id,
        "tool_name": tool_name,
        "command_id": context.command_id,
        "approval_id": context.approval_id,
        "budget_reservation_id": context.budget_reservation_id,
        "isolation_boundary_id": context.isolation_boundary_id,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "status": status,
        "worker_id": worker_id,
    }
    receipt_hash = canonical_hash(payload)
    return GovernedMCPExecutionReceipt(
        receipt_id=f"mcp-execution-receipt-{receipt_hash[:16]}",
        capability_id=capability.capability_id,
        server_id=server_id,
        tool_name=tool_name,
        command_id=context.command_id,
        approval_id=context.approval_id,
        budget_reservation_id=context.budget_reservation_id,
        isolation_boundary_id=context.isolation_boundary_id,
        input_hash=input_hash,
        output_hash=output_hash,
        status=status,
        evidence_refs=(f"mcp_tool_call:{receipt_hash[:16]}",),
    )
