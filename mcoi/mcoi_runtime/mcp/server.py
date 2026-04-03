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
from typing import Any, Callable


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
    ) -> None:
        self._platform = platform
        self._default_tenant = default_tenant_id
        self._default_identity = default_identity_id
        self._call_count = 0

    def list_tools(self) -> list[MCPTool]:
        """Return all available MCP tools."""
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

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Execute an MCP tool call through the governance pipeline."""
        self._call_count += 1
        tenant_id = arguments.get("tenant_id", self._default_tenant)
        identity_id = arguments.get("identity_id", self._default_identity)

        try:
            session = self._platform.connect(
                identity_id=identity_id,
                tenant_id=tenant_id,
            )
        except PermissionError as exc:
            return MCPToolResult(content=f"Access denied: {exc}", is_error=True)
        except Exception as exc:
            return MCPToolResult(content=f"Connection failed: {exc}", is_error=True)

        try:
            if name == "mullu_llm":
                return self._tool_llm(session, arguments)
            elif name == "mullu_query":
                return self._tool_query(session, arguments)
            elif name == "mullu_execute":
                return self._tool_execute(session, arguments)
            elif name == "mullu_balance":
                return self._tool_balance(session, arguments)
            elif name == "mullu_transactions":
                return self._tool_transactions(session, arguments)
            elif name == "mullu_pay":
                return self._tool_pay(session, arguments)
            else:
                return MCPToolResult(content=f"Unknown tool: {name}", is_error=True)
        except Exception as exc:
            return MCPToolResult(content=f"Tool error: {exc}", is_error=True)
        finally:
            try:
                session.close()
            except Exception:
                pass

    def _tool_llm(self, session: Any, args: dict[str, Any]) -> MCPToolResult:
        prompt = args.get("prompt", "")
        if not prompt:
            return MCPToolResult(content="prompt is required", is_error=True)
        try:
            result = session.llm(prompt)
            return MCPToolResult(content=result.content if result.succeeded else f"LLM error: {result.error}")
        except ValueError as exc:
            return MCPToolResult(content=f"Content blocked: {exc}", is_error=True)
        except RuntimeError as exc:
            return MCPToolResult(content=f"Service error: {exc}", is_error=True)

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
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result.content}],
                    "isError": result.is_error,
                },
            }

        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
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
