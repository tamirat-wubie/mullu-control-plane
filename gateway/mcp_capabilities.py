"""Purpose: register certified MCP capabilities as gateway handlers.
Governance scope: capability dispatcher integration for governed MCP
execution, witness propagation, and receipt-shaped handler outputs.
Dependencies: gateway capability dispatcher and mcoi_runtime MCP executor.
Invariants:
  - Only certified MCP capability registry entries may be registered.
  - Handler execution requires command, approval, budget, and isolation witnesses.
  - MCP execution receipts are returned as capability evidence.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from gateway.capability_dispatch import (
    CapabilityDispatcher,
    CapabilityExecutionContext,
    CapabilityHandler,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry
from mcoi_runtime.mcp import (
    GovernedMCPExecutionContext,
    GovernedMCPExecutor,
)


class GovernedMCPCapabilityHandler:
    """Capability handler that delegates to a governed MCP executor."""

    def __init__(
        self,
        *,
        capability: CapabilityRegistryEntry,
        executor: GovernedMCPExecutor,
    ) -> None:
        self.capability_id = capability.capability_id
        self._capability = capability
        self._executor = executor

    def execute(
        self,
        context: CapabilityExecutionContext,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        execution_context = GovernedMCPExecutionContext(
            tenant_id=context.tenant_id,
            identity_id=context.identity_id,
            command_id=context.command_id,
            approval_id=_required_witness(context.metadata, "approval_id"),
            budget_reservation_id=_required_witness(context.metadata, "budget_reservation_id"),
            isolation_boundary_id=_required_witness(context.metadata, "isolation_boundary_id"),
            terminal_certificate_required=True,
            metadata=context.metadata,
        )
        result = self._executor.execute(
            capability=self._capability,
            context=execution_context,
            params=params,
        )
        receipt = asdict(result.receipt)
        return {
            "response": "MCP capability executed." if result.succeeded else "MCP capability execution failed.",
            "receipt_status": result.receipt.status,
            "mcp_server_id": result.receipt.server_id,
            "mcp_tool_name": result.receipt.tool_name,
            "tool_call_receipt": result.receipt.receipt_id,
            "mcp_succeeded": result.succeeded,
            "mcp_output": result.output,
            "mcp_error": result.error,
            "mcp_execution_receipt": receipt,
            "mcp_execution_metadata": dict(result.metadata),
            "input_hash": result.receipt.input_hash,
            "output_hash": result.receipt.output_hash,
            "evidence_refs": result.receipt.evidence_refs,
        }


def register_mcp_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    capabilities: Iterable[CapabilityRegistryEntry],
    executor: GovernedMCPExecutor,
) -> tuple[str, ...]:
    """Register certified MCP capabilities with a gateway dispatcher."""
    registered: list[str] = []
    for capability in capabilities:
        handler: CapabilityHandler = GovernedMCPCapabilityHandler(
            capability=capability,
            executor=executor,
        )
        dispatcher.register(handler)
        registered.append(capability.capability_id)
    return tuple(registered)


def _required_witness(metadata: Mapping[str, Any], key: str) -> str:
    value = str(metadata.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required for governed MCP execution")
    return value
