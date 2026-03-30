"""Phase 211C — Tool-use contract tests."""

import pytest
from mcoi_runtime.core.safe_arithmetic import evaluate_expression
from mcoi_runtime.core.tool_use import (
    ToolDefinition, ToolParameter, ToolRegistry, ToolResult,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _registry():
    reg = ToolRegistry(clock=FIXED_CLOCK)
    reg.register(
        ToolDefinition(
            tool_id="calculator", name="Calculator",
            description="Performs arithmetic",
            parameters=(
                ToolParameter(name="expression", param_type="string", description="Math expression"),
            ),
        ),
        handler=lambda args: {"result": evaluate_expression(args["expression"])},
    )
    reg.register(
        ToolDefinition(
            tool_id="greeting", name="Greeter",
            description="Generates greetings",
            parameters=(
                ToolParameter(name="name", param_type="string", required=True),
                ToolParameter(name="style", param_type="string", required=False, default="formal"),
            ),
        ),
        handler=lambda args: {"greeting": f"Hello, {args['name']}!"},
    )
    return reg


class TestToolRegistry:
    def test_register(self):
        reg = _registry()
        assert reg.tool_count == 2

    def test_duplicate_register(self):
        reg = _registry()
        with pytest.raises(ValueError, match="already registered"):
            reg.register(
                ToolDefinition(tool_id="calculator", name="C2", description="x", parameters=()),
                handler=lambda args: {},
            )

    def test_invoke_success(self):
        reg = _registry()
        result = reg.invoke("calculator", {"expression": "2+3"})
        assert result.succeeded is True
        assert result.output["result"] == 5
        assert result.result_hash

    def test_invoke_missing_param(self):
        reg = _registry()
        result = reg.invoke("calculator", {})  # Missing "expression"
        assert result.succeeded is False
        assert "missing required" in result.error

    def test_invoke_unknown_tool(self):
        reg = _registry()
        result = reg.invoke("nonexistent", {})
        assert result.succeeded is False
        assert "unknown tool" in result.error

    def test_invoke_disallowed_tool(self):
        reg = _registry()
        result = reg.invoke("calculator", {"expression": "2+3"}, allowed_tool_ids={"greeting"})
        assert result.succeeded is False
        assert "tool not allowed" in result.error

    def test_invoke_disabled_tool(self):
        reg = ToolRegistry(clock=FIXED_CLOCK)
        reg.register(
            ToolDefinition(tool_id="disabled", name="D", description="x", parameters=(), enabled=False),
            handler=lambda args: {},
        )
        result = reg.invoke("disabled", {})
        assert result.succeeded is False
        assert "disabled" in result.error

    def test_invoke_handler_error(self):
        reg = ToolRegistry(clock=FIXED_CLOCK)
        reg.register(
            ToolDefinition(tool_id="broken", name="B", description="x", parameters=()),
            handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = reg.invoke("broken", {})
        assert result.succeeded is False
        assert "boom" in result.error

    def test_invoke_unsafe_expression_rejected(self):
        reg = _registry()
        result = reg.invoke("calculator", {"expression": "__import__('os').system('whoami')"})
        assert result.succeeded is False
        assert "unsupported expression node" in result.error

    def test_optional_params(self):
        reg = _registry()
        result = reg.invoke("greeting", {"name": "Alice"})
        assert result.succeeded is True
        assert "Alice" in result.output["greeting"]

    def test_to_llm_tools(self):
        reg = _registry()
        tools = reg.to_llm_tools()
        assert len(tools) == 2
        calc = next(t for t in tools if t["name"] == "calculator")
        assert "expression" in calc["input_schema"]["properties"]
        assert "expression" in calc["input_schema"]["required"]

    def test_invocation_history(self):
        reg = _registry()
        reg.invoke("calculator", {"expression": "1+1"})
        reg.invoke("calculator", {"expression": "2+2"})
        history = reg.invocation_history()
        assert len(history) == 2

    def test_list_tools(self):
        reg = _registry()
        tools = reg.list_tools()
        assert len(tools) == 2

    def test_summary(self):
        reg = _registry()
        reg.invoke("calculator", {"expression": "1+1"})
        s = reg.summary()
        assert s["tools"] == 2
        assert s["invocations"] == 1
        assert s["succeeded"] == 1
