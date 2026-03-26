"""Phase 212B — Tool-augmented agent tests."""

import pytest
from mcoi_runtime.core.tool_agent import ToolAugmentedAgent
from mcoi_runtime.core.tool_use import ToolDefinition, ToolParameter, ToolRegistry

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _setup():
    reg = ToolRegistry(clock=FIXED_CLOCK)
    reg.register(
        ToolDefinition(tool_id="calc", name="Calc", description="Math", parameters=(
            ToolParameter(name="expression", param_type="string"),
        )),
        handler=lambda args: {"result": str(eval(args.get("expression", "0")))},
    )
    reg.register(
        ToolDefinition(tool_id="echo", name="Echo", description="Echo input", parameters=(
            ToolParameter(name="text", param_type="string"),
        )),
        handler=lambda args: {"echo": args.get("text", "")},
    )
    return reg


class TestToolAugmentedAgent:
    def test_execute_no_tool_calls(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)
        result = agent.execute_with_tools("Just answer this question")
        assert result.content
        assert result.total_tool_calls == 0

    def test_execute_with_tools_available(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)
        result = agent.execute_with_tools("What is 2+2?")
        assert result.content
        assert result.all_succeeded is True

    def test_tool_call_parsing(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        parsed = agent._parse_tool_call("TOOL_CALL: calc(expression=2+2)")
        assert parsed is not None
        assert parsed[0] == "calc"
        assert parsed[1]["expression"] == "2+2"

    def test_tool_call_parsing_with_quotes(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        parsed = agent._parse_tool_call("TOOL_CALL: echo(text='hello world')")
        assert parsed is not None
        assert parsed[1]["text"] == "hello world"

    def test_invalid_tool_call_returns_none(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        assert agent._parse_tool_call("not a tool call") is None

    def test_filtered_tools(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)
        result = agent.execute_with_tools("test", tool_ids=["calc"])
        # Only calc should be mentioned in prompt
        assert result.content

    def test_max_tool_calls(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, max_tool_calls=2)
        # Agent won't exceed max even if LLM requests more
        result = agent.execute_with_tools("test")
        assert result.total_tool_calls <= 2

    def test_summary(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)
        agent.execute_with_tools("test")
        s = agent.summary()
        assert s["executions"] == 1
        assert s["available_tools"] == 2
