"""MCP Server Tests — Governed tool provider for external agents."""

import json
from types import SimpleNamespace

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


class _SessionStub:
    def __init__(self, *, llm_fn=None, query_fn=None, execute_fn=None) -> None:
        self._llm_fn = llm_fn or (lambda prompt: SimpleNamespace(succeeded=True, content="ok"))
        self._query_fn = query_fn or (lambda resource: {"governed": True, "resource_type": resource})
        self._execute_fn = execute_fn or (lambda action: {"governed": True, "action_type": action})
        self.closed = False

    def llm(self, prompt: str):
        return self._llm_fn(prompt)

    def query(self, resource: str):
        return self._query_fn(resource)

    def execute(self, action: str):
        return self._execute_fn(action)

    def close(self) -> None:
        self.closed = True


class _PlatformStub:
    def __init__(self, *, session=None, connect_exc: Exception | None = None) -> None:
        self._session = session or _SessionStub()
        self._connect_exc = connect_exc

    def connect(self, **kwargs):
        if self._connect_exc is not None:
            raise self._connect_exc
        return self._session


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
        assert result.content == "Unknown tool"
        assert "nonexistent" not in result.content

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

    def test_connection_failure_is_sanitized(self):
        server = MulluMCPServer(platform=_PlatformStub(connect_exc=RuntimeError("secret backend detail")))
        result = server.call_tool("mullu_query", {"resource_type": "health"})
        assert result.is_error is True
        assert result.content == "Connection failed: mcp session unavailable (RuntimeError)"
        assert "secret backend detail" not in result.content

    def test_access_denial_is_sanitized(self):
        server = MulluMCPServer(platform=_PlatformStub(connect_exc=PermissionError("tenant secret mismatch")))
        result = server.call_tool("mullu_query", {"resource_type": "health"})
        assert result.is_error is True
        assert result.content == "Access denied: access denied (PermissionError)"
        assert "tenant secret mismatch" not in result.content

    def test_tool_failure_is_sanitized_and_session_still_closes(self):
        session = _SessionStub(query_fn=lambda resource: (_ for _ in ()).throw(RuntimeError("secret query failure")))
        server = MulluMCPServer(platform=_PlatformStub(session=session))
        result = server.call_tool("mullu_query", {"resource_type": "health"})
        assert result.is_error is True
        assert result.content == "Tool error: mcp tool execution failed (RuntimeError)"
        assert session.closed is True
        assert "secret query failure" not in result.content

    def test_llm_value_error_is_sanitized(self):
        session = _SessionStub(llm_fn=lambda prompt: (_ for _ in ()).throw(ValueError("secret content block detail")))
        server = MulluMCPServer(platform=_PlatformStub(session=session))
        result = server.call_tool("mullu_llm", {"prompt": "hello"})
        assert result.is_error is True
        assert result.content == "Content blocked: content blocked (ValueError)"
        assert "secret content block detail" not in result.content

    def test_llm_runtime_error_is_sanitized(self):
        session = _SessionStub(llm_fn=lambda prompt: (_ for _ in ()).throw(RuntimeError("secret upstream failure")))
        server = MulluMCPServer(platform=_PlatformStub(session=session))
        result = server.call_tool("mullu_llm", {"prompt": "hello"})
        assert result.is_error is True
        assert result.content == "Service error: service unavailable (RuntimeError)"
        assert "secret upstream failure" not in result.content

    def test_llm_failed_result_is_marked_error(self):
        session = _SessionStub(llm_fn=lambda prompt: SimpleNamespace(succeeded=False, content="", error="secret llm detail"))
        server = MulluMCPServer(platform=_PlatformStub(session=session))
        result = server.call_tool("mullu_llm", {"prompt": "hello"})
        assert result.is_error is True
        assert result.content == "Service error: llm request failed"
        assert "secret llm detail" not in result.content


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
        assert resp["error"]["message"] == "Method not found"
        assert "unknown/method" not in resp["error"]["message"]
