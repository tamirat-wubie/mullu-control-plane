"""MCP Server Tests — Governed tool provider for external agents."""

import json
import pytest
from mcoi_runtime.mcp.server import MulluMCPServer, MCPTool, MCPToolResult
from mcoi_runtime.core.governed_session import Platform
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.proof_bridge import ProofBridge


def _clock():
    return "2026-01-01T00:00:00Z"


def _platform():
    return Platform(
        clock=_clock,
        audit_trail=AuditTrail(clock=_clock),
        proof_bridge=ProofBridge(clock=_clock),
    )


class TestMCPToolListing:
    def test_list_tools(self):
        server = MulluMCPServer(platform=_platform())
        tools = server.list_tools()
        assert len(tools) == 6
        names = [t.name for t in tools]
        assert "mullu_llm" in names
        assert "mullu_query" in names
        assert "mullu_execute" in names
        assert "mullu_balance" in names
        assert "mullu_pay" in names

    def test_tool_has_schema(self):
        server = MulluMCPServer(platform=_platform())
        tools = server.list_tools()
        for tool in tools:
            assert isinstance(tool.input_schema, dict)
            assert "properties" in tool.input_schema


class TestMCPToolCalls:
    def test_query_tool(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("mullu_query", {"resource_type": "health"})
        assert not result.is_error
        data = json.loads(result.content)
        assert data["governed"] is True

    def test_execute_tool(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("mullu_execute", {"action_type": "test_action"})
        assert not result.is_error

    def test_unknown_tool(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("nonexistent", {})
        assert result.is_error
        assert "Unknown tool" in result.content

    def test_llm_without_bridge(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("mullu_llm", {"prompt": "hello"})
        assert result.is_error  # No LLM bridge configured

    def test_balance_tool(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("mullu_balance", {})
        assert not result.is_error
        data = json.loads(result.content)
        assert data["governed"] is True

    def test_pay_tool(self):
        server = MulluMCPServer(platform=_platform())
        result = server.call_tool("mullu_pay", {"amount": "100", "destination": "vendor"})
        assert not result.is_error
        data = json.loads(result.content)
        assert data["status"] == "requires_approval"

    def test_call_count(self):
        server = MulluMCPServer(platform=_platform())
        assert server.call_count == 0
        server.call_tool("mullu_query", {"resource_type": "test"})
        server.call_tool("mullu_query", {"resource_type": "test2"})
        assert server.call_count == 2


class TestMCPJsonRPC:
    def test_initialize(self):
        server = MulluMCPServer(platform=_platform())
        resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp["result"]["serverInfo"]["name"] == "mullu-governed"

    def test_tools_list(self):
        server = MulluMCPServer(platform=_platform())
        resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(resp["result"]["tools"]) == 6

    def test_tools_call(self):
        server = MulluMCPServer(platform=_platform())
        resp = server.handle_jsonrpc({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "mullu_query", "arguments": {"resource_type": "health"}},
        })
        assert "content" in resp["result"]
        assert not resp["result"]["isError"]

    def test_unknown_method(self):
        server = MulluMCPServer(platform=_platform())
        resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 4, "method": "unknown/method"})
        assert "error" in resp
        assert resp["error"]["code"] == -32601
