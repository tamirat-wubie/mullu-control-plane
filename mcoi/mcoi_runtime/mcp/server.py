"""MCP Tool Server — Model Context Protocol server for Mullu governance.

Purpose: Expose GovernedSession operations as MCP tools that external agents
    (Claude Code, Cursor, other MCP clients) can call. Every tool call flows
    through the full governance pipeline.

Protocol: JSON-RPC 2.0 over stdio (MCP standard transport).
Tools exposed:
  - mullu_llm: Governed LLM completion
  - mullu_query: Governed read-only query
  - mullu_execute: Governed action execution
  - mullu_balance: Financial balance check
  - mullu_transactions: Financial transaction history
  - mullu_pay: Governed payment initiation (requires approval)

Invariants:
  - Every tool call is identity-bound and tenant-scoped.
  - Every tool call flows through RBAC + content safety + budget + audit + proof.
  - No tool bypasses governance — MCP server IS the governance layer.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from gateway.command_spine import CommandEnvelope, CommandLedger, CommandState, canonical_hash


def _bounded_mcp_error(prefix: str, summary: str, exc: Exception) -> str:
    """Return a bounded MCP-facing error without backend detail."""
    return f"{prefix}: {summary} ({type(exc).__name__})"


@dataclass(frozen=True, slots=True)
class MCPTool:
    """An MCP tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MCPToolResult:
    """Result of an MCP tool call."""

    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


_MCP_TOOL_INTENTS: dict[str, str] = {
    "mullu_llm": "llm_completion",
    "mullu_query": "mcp.query",
    "mullu_execute": "mcp.execute",
    "mullu_balance": "financial.balance_check",
    "mullu_transactions": "financial.transaction_history",
    "mullu_pay": "financial.send_payment",
    "mullu_software_change": "software_dev.governed_change",
    "mullu_software_receipts": "software_dev.receipt_query",
}


# SoftwareDevRunnerConfig now lives in core.software_dev_gates (where the
# operator-side factory make_default_software_dev_runner builds it). We
# re-export here so existing `from mcoi_runtime.mcp.server import
# SoftwareDevRunnerConfig` imports keep working.
from mcoi_runtime.core.software_dev_gates import SoftwareDevRunnerConfig  # noqa: E402, F401


class MulluMCPServer:
    """MCP server that wraps GovernedSession as tool provider.

    External agents connect to this server and call governed tools.
    Every tool call opens a GovernedSession, executes the operation,
    closes the session, and returns the result with audit + proof.

    Transport: JSON-RPC 2.0 over stdio (standard MCP transport).
    """

    def __init__(
        self,
        *,
        platform: Any,  # Platform instance
        default_tenant_id: str = "mcp-default",
        default_identity_id: str = "mcp-agent",
        command_ledger: CommandLedger | None = None,
        software_dev_runner: SoftwareDevRunnerConfig | None = None,
    ) -> None:
        self._platform = platform
        self._default_tenant = default_tenant_id
        self._default_identity = default_identity_id
        self._commands = command_ledger or CommandLedger()
        self._software_dev_runner = software_dev_runner
        self._call_count = 0
        self._close_failures = 0

    def list_tools(self) -> list[MCPTool]:
        """Return all available MCP tools.

        mullu_software_change is included only when the server was
        constructed with a SoftwareDevRunnerConfig — operators who
        haven't wired plan/patch/gate machinery don't see the tool.
        """
        tools = self._base_tools()
        if self._software_dev_runner is not None:
            tools.append(self._software_change_tool())
            if self._software_dev_runner.receipt_store is not None:
                tools.append(self._software_receipts_tool())
        return tools

    def _base_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="mullu_llm",
                description="Governed LLM completion. Every call is audited, budget-checked, and content-safety filtered.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt to send to the LLM"},
                        "tenant_id": {"type": "string", "description": "Tenant ID (optional, uses default)"},
                    },
                    "required": ["prompt"],
                },
            ),
            MCPTool(
                name="mullu_query",
                description="Governed read-only query. Returns governed data with audit trail.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "resource_type": {"type": "string", "description": "Resource to query (e.g., 'tenants', 'audit', 'health')"},
                        "tenant_id": {"type": "string"},
                    },
                    "required": ["resource_type"],
                },
            ),
            MCPTool(
                name="mullu_execute",
                description="Governed action execution. RBAC + approval gated.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "description": "Action to execute"},
                        "tenant_id": {"type": "string"},
                    },
                    "required": ["action_type"],
                },
            ),
            MCPTool(
                name="mullu_balance",
                description="Check financial account balance. Governed read-only.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tenant_id": {"type": "string"},
                        "account_id": {"type": "string", "description": "Specific account ID (optional)"},
                    },
                },
            ),
            MCPTool(
                name="mullu_transactions",
                description="Get recent financial transactions. Governed read-only.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tenant_id": {"type": "string"},
                        "account_id": {"type": "string"},
                        "days": {"type": "integer", "default": 30},
                    },
                },
            ),
            MCPTool(
                name="mullu_pay",
                description="Initiate a governed payment. Requires human approval before execution.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "string", "description": "Payment amount (decimal string)"},
                        "currency": {"type": "string", "default": "USD"},
                        "destination": {"type": "string", "description": "Payment destination"},
                        "description": {"type": "string"},
                        "tenant_id": {"type": "string"},
                    },
                    "required": ["amount", "destination"],
                },
            ),
        ]

    def _software_change_tool(self) -> MCPTool:
        return MCPTool(
            name="mullu_software_change",
            description=(
                "Govern an autonomous software change end-to-end: UCJA gate "
                "→ workspace snapshot → plan → patch → quality gates → "
                "rollback (if needed) → typed terminal certificate. "
                "Returns SolverOutcome (solved | solved_with_compensation | "
                "requires_review) plus the certificate disposition, case_id "
                "(if any), and a per-attempt evidence trail."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": (
                            "SoftwareWorkKind value: bug_fix, feature, refactor, "
                            "deploy, review, investigate, test_generation, "
                            "security_fix, docs, migration, dependency_update, "
                            "rollback."
                        ),
                    },
                    "summary": {
                        "type": "string",
                        "description": "Human-readable description of the change.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository identifier.",
                    },
                    "target_branch": {"type": "string", "default": "main"},
                    "affected_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Relative paths the request is bounded to. Plans "
                            "may not target files outside this set."
                        ),
                    },
                    "acceptance_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "blast_radius": {
                        "type": "string",
                        "enum": ["function", "module", "service", "system"],
                        "default": "module",
                    },
                    "reviewer_required": {"type": "boolean", "default": True},
                    "mode": {
                        "type": "string",
                        "enum": [
                            "plan_only", "dry_run", "patch_only",
                            "patch_and_test", "patch_test_review",
                            "commit_candidate",
                        ],
                        "default": "patch_test_review",
                    },
                    "quality_gates": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "unit_tests", "integration_tests", "lint",
                                "typecheck", "security_scan", "build", "review",
                            ],
                        },
                        "default": ["unit_tests", "lint"],
                    },
                    "max_self_debug_iterations": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 3,
                    },
                    "tenant_id": {"type": "string"},
                },
                "required": ["kind", "summary", "repository"],
            },
        )

    def _software_receipts_tool(self) -> MCPTool:
        return MCPTool(
            name="mullu_software_receipts",
            description=(
                "Read governed software-change lifecycle receipts from the "
                "configured receipt store. Supports list, get, and replay "
                "without mutating the workspace."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["list", "get", "replay"],
                        "default": "list",
                    },
                    "request_id": {
                        "type": "string",
                        "description": "Software-change request id for list or replay.",
                    },
                    "receipt_id": {
                        "type": "string",
                        "description": "Receipt id for get.",
                    },
                    "stage": {
                        "type": "string",
                        "description": "Optional SoftwareChangeReceiptStage filter for list.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 50,
                    },
                    "tenant_id": {"type": "string"},
                },
            },
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Execute an MCP tool call through the governance pipeline.

        Identity is bound to the MCP server's configured default — callers
        cannot spoof identity_id via arguments.
        """
        self._call_count += 1
        if not isinstance(arguments, dict):
            arguments = {}
        tenant_id = str(arguments.get("tenant_id") or "")
        if not tenant_id:
            if not self._default_tenant:
                return MCPToolResult(content="tenant_id is required", is_error=True)
            tenant_id = self._default_tenant
        # Identity is ALWAYS server-bound — never from arguments (prevents spoofing)
        identity_id = self._default_identity
        command = self._create_tool_command(
            name=name,
            arguments=arguments,
            tenant_id=tenant_id,
            identity_id=identity_id,
        )

        try:
            session = self._platform.connect(
                identity_id=identity_id,
                tenant_id=tenant_id,
            )
        except PermissionError as exc:
            denied = self._commands.transition(
                command.command_id,
                CommandState.DENIED,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                detail={"cause": "mcp_access_denied"},
            )
            return self._finalize_connection_result(
                denied,
                name=name,
                result=MCPToolResult(
                    content=_bounded_mcp_error("Access denied", "access denied", exc),
                    is_error=True,
                ),
            )
        except Exception as exc:
            review = self._commands.transition(
                command.command_id,
                CommandState.REQUIRES_REVIEW,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                detail={"cause": "mcp_connect_failed"},
            )
            return self._finalize_connection_result(
                review,
                name=name,
                result=MCPToolResult(
                    content=_bounded_mcp_error("Connection failed", "mcp session unavailable", exc),
                    is_error=True,
                ),
            )

        close_failed = False
        result: MCPToolResult
        try:
            self._commands.transition(
                command.command_id,
                CommandState.DISPATCHED,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                detail={"cause": "mcp_tool_dispatched"},
            )
            if name == "mullu_llm":
                result = self._tool_llm(session, arguments)
            elif name == "mullu_query":
                result = self._tool_query(session, arguments)
            elif name == "mullu_execute":
                result = self._tool_execute(session, arguments)
            elif name == "mullu_balance":
                result = self._tool_balance(session, arguments)
            elif name == "mullu_transactions":
                result = self._tool_transactions(session, arguments)
            elif name == "mullu_pay":
                result = self._tool_pay(session, arguments)
            elif name == "mullu_software_change":
                result = self._tool_software_change(session, arguments)
            elif name == "mullu_software_receipts":
                result = self._tool_software_receipts(session, arguments)
            else:
                result = MCPToolResult(content="Unknown tool", is_error=True)
        except Exception as exc:
            result = MCPToolResult(
                content=_bounded_mcp_error("Tool error", "mcp tool execution failed", exc),
                is_error=True,
            )
        finally:
            try:
                session.close()
            except Exception:
                self._close_failures += 1
                close_failed = True

        return self._finalize_tool_result(command, name=name, result=result, close_failed=close_failed)

    def _create_tool_command(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        tenant_id: str,
        identity_id: str,
    ) -> CommandEnvelope:
        known_tool = self._known_tool_name(name)
        argument_hash = canonical_hash({"arguments": arguments})
        argument_keys = sorted(str(key) for key in arguments)
        provided_idempotency_key = str(arguments.get("idempotency_key") or "")
        if provided_idempotency_key:
            idempotency_key = canonical_hash({"provided_idempotency_key": provided_idempotency_key})
        else:
            idempotency_key = canonical_hash({
                "source": "mcp",
                "tenant_id": tenant_id,
                "identity_id": identity_id,
                "tool_name": known_tool,
                "argument_hash": argument_hash,
            })
        intent = _MCP_TOOL_INTENTS.get(name, "mcp.unknown")
        payload = {
            "body_hash": argument_hash,
            "mcp_tool": known_tool,
            "mcp_argument_keys": argument_keys,
        }
        command = self._commands.create_command(
            tenant_id=tenant_id,
            actor_id=identity_id,
            source="mcp",
            conversation_id=f"mcp:{identity_id}",
            idempotency_key=idempotency_key,
            intent=intent,
            payload=payload,
        )
        self._commands.transition(
            command.command_id,
            CommandState.NORMALIZED,
            tool_name=known_tool,
            detail={"cause": "mcp_tool_normalized", "tool": known_tool},
        )
        self._commands.transition(
            command.command_id,
            CommandState.TENANT_BOUND,
            tool_name=known_tool,
            detail={"cause": "mcp_tenant_bound"},
        )
        self._commands.transition(
            command.command_id,
            CommandState.POLICY_EVALUATED,
            risk_tier=self._risk_tier_for_tool(name),
            tool_name=known_tool,
            detail={"cause": "mcp_policy_evaluated"},
        )
        return command

    def _finalize_tool_result(
        self,
        command: CommandEnvelope,
        *,
        name: str,
        result: MCPToolResult,
        close_failed: bool = False,
    ) -> MCPToolResult:
        output = {
            "content_hash": canonical_hash({"content": result.content}),
            "is_error": result.is_error,
        }
        observed = self._commands.transition(
            command.command_id,
            CommandState.OBSERVED,
            risk_tier=self._risk_tier_for_tool(name),
            tool_name=self._known_tool_name(name),
            output=output,
            detail={"cause": "mcp_tool_observed"},
        )
        if result.is_error or close_failed:
            cause = "mcp_session_close_failed" if close_failed else "mcp_tool_error"
            terminal = self._commands.transition(
                observed.command_id,
                CommandState.REQUIRES_REVIEW,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                output=output,
                detail={"cause": cause},
            )
        else:
            verified = self._commands.transition(
                observed.command_id,
                CommandState.VERIFIED,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                detail={"cause": "mcp_result_verified"},
            )
            terminal = self._commands.transition(
                verified.command_id,
                CommandState.COMMITTED,
                risk_tier=self._risk_tier_for_tool(name),
                tool_name=self._known_tool_name(name),
                detail={"cause": "mcp_tool_committed"},
            )
        responded = self._commands.transition(
            terminal.command_id,
            CommandState.RESPONDED,
            risk_tier=self._risk_tier_for_tool(name),
            tool_name=self._known_tool_name(name),
            output=output,
            detail={"cause": "mcp_response_emitted"},
        )
        metadata = dict(result.metadata)
        metadata.update({
            "command_id": responded.command_id,
            "trace_id": responded.trace_id,
            "command_state": responded.state.value,
            "tool_name": self._known_tool_name(name),
            "risk_tier": self._risk_tier_for_tool(name),
            "close_failed": close_failed,
        })
        return MCPToolResult(
            content=result.content,
            is_error=result.is_error,
            metadata=metadata,
        )

    def _finalize_connection_result(
        self,
        command: CommandEnvelope,
        *,
        name: str,
        result: MCPToolResult,
    ) -> MCPToolResult:
        output = {
            "content_hash": canonical_hash({"content": result.content}),
            "is_error": result.is_error,
        }
        responded = self._commands.transition(
            command.command_id,
            CommandState.RESPONDED,
            risk_tier=self._risk_tier_for_tool(name),
            tool_name=self._known_tool_name(name),
            output=output,
            detail={"cause": "mcp_response_emitted"},
        )
        metadata = dict(result.metadata)
        metadata.update({
            "command_id": responded.command_id,
            "trace_id": responded.trace_id,
            "command_state": responded.state.value,
            "tool_name": self._known_tool_name(name),
            "risk_tier": self._risk_tier_for_tool(name),
            "close_failed": False,
        })
        return MCPToolResult(
            content=result.content,
            is_error=result.is_error,
            metadata=metadata,
        )

    def _known_tool_name(self, name: str) -> str:
        """Return a bounded tool label for command witnesses."""
        return name if name in _MCP_TOOL_INTENTS else "unknown"

    def _risk_tier_for_tool(self, name: str) -> str:
        if name in {"mullu_pay", "mullu_execute", "mullu_software_change"}:
            return "high"
        return "low"

    def _tool_llm(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        prompt = args.get("prompt", "")
        if not prompt:
            return MCPToolResult(content="prompt is required", is_error=True)
        try:
            result = session.llm(prompt)
            if result.succeeded:
                return MCPToolResult(content=result.content)
            return MCPToolResult(content="Service error: llm request failed", is_error=True)
        except ValueError as exc:
            return MCPToolResult(
                content=_bounded_mcp_error("Content blocked", "content blocked", exc),
                is_error=True,
            )
        except RuntimeError as exc:
            return MCPToolResult(
                content=_bounded_mcp_error("Service error", "service unavailable", exc),
                is_error=True,
            )

    def _tool_query(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        resource = args.get("resource_type", "")
        result = session.query(resource)
        return MCPToolResult(content=json.dumps(result, default=str))

    def _tool_execute(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        action = args.get("action_type", "")
        result = session.execute(action)
        return MCPToolResult(content=json.dumps(result, default=str))

    def _tool_balance(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(content=json.dumps({
            "type": "balance_check",
            "governed": True,
            "note": "Connect a financial provider to enable balance checks",
        }))

    def _tool_transactions(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(content=json.dumps({
            "type": "transaction_history",
            "governed": True,
            "note": "Connect a financial provider to enable transaction history",
        }))

    def _tool_software_change(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        """Run governed_software_change with the configured runner.

        The runner config is bundled at construction time so the MCP layer
        does not own LLM or workspace state. Failures from the loop itself
        come back as REQUIRES_REVIEW certificates rather than tool errors;
        only schema-level rejections (bad kind/mode/gate enum, missing
        required fields) surface as is_error=True.
        """
        config = self._software_dev_runner
        if config is None:
            return MCPToolResult(
                content="Service error: software_dev_runner not configured",
                is_error=True,
            )

        # Lazy import — keeps mcp/server.py importable in environments that
        # don't pull in the loop module's transitive deps.
        try:
            from mcoi_runtime.core.software_dev_loop import (
                governed_software_change,
            )
            from mcoi_runtime.domain_adapters.software_dev import (
                SoftwareQualityGate,
                SoftwareRequest,
                SoftwareWorkKind,
                SoftwareWorkMode,
            )
        except ImportError as exc:
            return MCPToolResult(
                content=_bounded_mcp_error(
                    "Service error", "software_dev modules unavailable", exc,
                ),
                is_error=True,
            )

        try:
            kind = SoftwareWorkKind(str(args.get("kind", "")))
        except ValueError:
            return MCPToolResult(content="invalid kind", is_error=True)

        summary = str(args.get("summary", "")).strip()
        repository = str(args.get("repository", "")).strip()
        if not summary:
            return MCPToolResult(content="summary is required", is_error=True)
        if not repository:
            return MCPToolResult(content="repository is required", is_error=True)

        mode_value = str(args.get("mode") or SoftwareWorkMode.PATCH_TEST_REVIEW.value)
        try:
            mode = SoftwareWorkMode(mode_value)
        except ValueError:
            return MCPToolResult(content="invalid mode", is_error=True)

        gate_values = args.get("quality_gates") or [
            SoftwareQualityGate.UNIT_TESTS.value,
            SoftwareQualityGate.LINT.value,
        ]
        if not isinstance(gate_values, list):
            return MCPToolResult(content="quality_gates must be a list", is_error=True)
        try:
            quality_gates = tuple(SoftwareQualityGate(v) for v in gate_values)
        except ValueError:
            return MCPToolResult(content="invalid quality_gates entry", is_error=True)

        affected_files = args.get("affected_files") or ()
        acceptance_criteria = args.get("acceptance_criteria") or ()
        if not isinstance(affected_files, (list, tuple)):
            return MCPToolResult(content="affected_files must be a list", is_error=True)
        if not isinstance(acceptance_criteria, (list, tuple)):
            return MCPToolResult(
                content="acceptance_criteria must be a list", is_error=True,
            )

        try:
            request = SoftwareRequest(
                kind=kind,
                summary=summary,
                repository=repository,
                target_branch=str(args.get("target_branch") or "main"),
                affected_files=tuple(str(p) for p in affected_files),
                acceptance_criteria=tuple(str(c) for c in acceptance_criteria),
                blast_radius=str(args.get("blast_radius") or "module"),
                reviewer_required=bool(args.get("reviewer_required", True)),
                mode=mode,
                quality_gates=quality_gates,
                max_self_debug_iterations=int(args.get("max_self_debug_iterations", 3)),
            )
        except (ValueError, TypeError) as exc:
            return MCPToolResult(
                content=_bounded_mcp_error("Invalid request", "request rejected", exc),
                is_error=True,
            )

        try:
            outcome = governed_software_change(
                request,
                adapter=config.adapter,
                plan_generator=config.plan_generator,
                patch_generator=config.patch_generator,
                gate_runners=config.gate_runners,
                clock=config.clock,
                ucja_runner=config.ucja_runner,
            )
        except Exception as exc:
            return MCPToolResult(
                content=_bounded_mcp_error(
                    "Service error", "software change failed", exc,
                ),
                is_error=True,
            )

        receipts = outcome.receipts
        receipt_persistence = {
            "configured": config.receipt_store is not None,
            "persisted": False,
            "count": 0,
            "error": "",
        }
        if config.receipt_store is not None:
            try:
                persisted = config.receipt_store.append_many(receipts)
                receipt_persistence.update({
                    "persisted": True,
                    "count": len(persisted),
                })
            except Exception as exc:
                receipt_persistence.update({
                    "persisted": False,
                    "error": _bounded_mcp_error(
                        "Receipt persistence failed",
                        "software receipt store rejected write",
                        exc,
                    ),
                })

        is_persistence_error = (
            receipt_persistence["configured"]
            and not receipt_persistence["persisted"]
        )
        return MCPToolResult(
            content=json.dumps({
                "outcome": outcome.outcome.value,
                "solved": outcome.solved,
                "certificate": {
                    "certificate_id": outcome.certificate.certificate_id,
                    "disposition": outcome.certificate.disposition.value,
                    "case_id": outcome.certificate.case_id,
                    "compensation_outcome_id": outcome.certificate.compensation_outcome_id,
                    "evidence_refs": list(outcome.certificate.evidence_refs),
                },
                "evidence": {
                    "request_id": outcome.evidence.request_id,
                    "ucja_job_id": outcome.evidence.ucja_job_id,
                    "ucja_accepted": outcome.evidence.ucja_accepted,
                    "ucja_halted_at_layer": outcome.evidence.ucja_halted_at_layer,
                    "plan_id": outcome.evidence.plan_id,
                    "rollback_succeeded": outcome.evidence.rollback_succeeded,
                    "attempts": [
                        {
                            "attempt_index": a.attempt_index,
                            "patch_id": a.patch_id,
                            "status": a.status.value,
                            "rolled_back": a.rolled_back,
                            "gates_passed": sum(1 for g in a.gate_results if g.passed),
                            "gates_failed": sum(1 for g in a.gate_results if not g.passed),
                        }
                        for a in outcome.evidence.attempts
                    ],
                },
                "receipts": [
                    receipt.to_json_dict()
                    for receipt in receipts
                ],
                "receipt_persistence": receipt_persistence,
            }, default=str),
            is_error=is_persistence_error,
        )

    def _tool_software_receipts(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        """Read software-change lifecycle receipts from the configured store."""
        config = self._software_dev_runner
        if config is None or config.receipt_store is None:
            return MCPToolResult(
                content="Service error: software receipt store not configured",
                is_error=True,
            )

        try:
            from mcoi_runtime.contracts.software_dev_loop import (
                SoftwareChangeReceiptStage,
            )
        except ImportError as exc:
            return MCPToolResult(
                content=_bounded_mcp_error(
                    "Service error", "software receipt modules unavailable", exc,
                ),
                is_error=True,
            )

        operation = str(args.get("operation") or "list")
        if operation not in {"list", "get", "replay"}:
            return MCPToolResult(content="invalid operation", is_error=True)

        try:
            if operation == "get":
                receipt_id = str(args.get("receipt_id") or "").strip()
                if not receipt_id:
                    return MCPToolResult(content="receipt_id is required", is_error=True)
                receipt = config.receipt_store.get(receipt_id)
                receipts = tuple() if receipt is None else (receipt,)
                payload = {
                    "operation": operation,
                    "found": receipt is not None,
                    "receipt_id": receipt_id,
                    "receipts": [item.to_json_dict() for item in receipts],
                }
                return MCPToolResult(content=json.dumps(payload, default=str))

            request_id = str(args.get("request_id") or "").strip() or None
            if operation == "replay":
                if request_id is None:
                    return MCPToolResult(content="request_id is required", is_error=True)
                receipts = config.receipt_store.replay_request(request_id)
                payload = {
                    "operation": operation,
                    "request_id": request_id,
                    "count": len(receipts),
                    "terminal_closed": True,
                    "receipts": [item.to_json_dict() for item in receipts],
                }
                return MCPToolResult(content=json.dumps(payload, default=str))

            stage_arg = args.get("stage")
            stage = None
            if stage_arg not in (None, ""):
                stage = SoftwareChangeReceiptStage(str(stage_arg))
            limit_arg = args.get("limit", 50)
            try:
                limit = int(limit_arg)
            except (TypeError, ValueError):
                return MCPToolResult(content="limit must be a positive integer", is_error=True)
            receipts = config.receipt_store.list_receipts(
                request_id=request_id,
                stage=stage,
                limit=limit,
            )
            payload = {
                "operation": operation,
                "request_id": request_id,
                "stage": stage.value if stage is not None else None,
                "count": len(receipts),
                "receipts": [item.to_json_dict() for item in receipts],
            }
            return MCPToolResult(content=json.dumps(payload, default=str))
        except ValueError as exc:
            return MCPToolResult(
                content=_bounded_mcp_error("Invalid request", "receipt query rejected", exc),
                is_error=True,
            )
        except Exception as exc:
            return MCPToolResult(
                content=_bounded_mcp_error(
                    "Service error", "software receipt query failed", exc,
                ),
                is_error=True,
            )

    def _tool_pay(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        amount = args.get("amount", "0")
        destination = args.get("destination", "")
        return MCPToolResult(content=json.dumps({
            "type": "payment_initiation",
            "amount": amount,
            "destination": destination,
            "status": "requires_approval",
            "governed": True,
            "note": "Payment requires human approval before execution",
        }))

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def close_failure_count(self) -> int:
        return self._close_failures

    def summary(self) -> dict[str, Any]:
        """Return bounded MCP server health details."""
        return {
            "call_count": self._call_count,
            "close_failures": self._close_failures,
            "commands": self._commands.summary(),
        }

    def handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC 2.0 request (MCP protocol)."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "mullu-governed", "version": "1.0.0"},
                },
            }

        if method == "tools/list":
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self.list_tools()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self.call_tool(tool_name, arguments)
            payload = {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result.content}],
                    "isError": result.is_error,
                },
            }
            if result.metadata:
                payload["result"]["_meta"] = result.metadata
            return payload

        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": "Method not found"},
        }

    def run_stdio(self) -> None:
        """Run the MCP server over stdio (standard MCP transport)."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_jsonrpc(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                error = {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(error) + "\n")
                sys.stdout.flush()
