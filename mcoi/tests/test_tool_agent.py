"""Phase 212B — Tool-augmented agent tests."""

import pytest
from mcoi_runtime.contracts.execution import ExecutionMode
from mcoi_runtime.core.safe_arithmetic import evaluate_expression
from mcoi_runtime.core.tool_agent import (
    MissingToolAgentBackendError,
    MissingToolAgentReplayEvidenceError,
    ToolAugmentedAgent,
)
from mcoi_runtime.core.tool_use import ToolDefinition, ToolParameter, ToolRegistry

def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


def _setup():
    reg = ToolRegistry(clock=FIXED_CLOCK)
    reg.register(
        ToolDefinition(tool_id="calc", name="Calc", description="Math", parameters=(
            ToolParameter(name="expression", param_type="string"),
        )),
        handler=lambda args: {"result": str(evaluate_expression(args.get("expression", "0")))},
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
        agent = ToolAugmentedAgent(tool_registry=reg, execution_mode=ExecutionMode.DRY_RUN)
        result = agent.execute_with_tools("Just answer this question")
        assert result.content
        assert result.content.startswith("[dry_run:")
        assert result.total_tool_calls == 0

    def test_missing_llm_requires_explicit_dry_run(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)

        with pytest.raises(MissingToolAgentBackendError, match="execution_mode=real"):
            agent.execute_with_tools("Just answer this question")

        assert agent.history_count == 0

    def test_execute_with_tools_available(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, execution_mode=ExecutionMode.DRY_RUN)
        result = agent.execute_with_tools("What is 2+2?")
        assert result.content
        assert result.all_succeeded is True

    def test_real_mode_without_llm_backend_fails_closed(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg)
        with pytest.raises(MissingToolAgentBackendError, match="execution_mode=real"):
            agent.execute_with_tools("Do not fabricate")
        assert agent.history_count == 0
        assert agent.summary()["executions"] == 0

    def test_replay_mode_without_evidence_fails_closed(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, execution_mode=ExecutionMode.REPLAY)
        with pytest.raises(MissingToolAgentReplayEvidenceError, match="execution_mode=replay"):
            agent.execute_with_tools("Replay only from evidence")
        assert agent.history_count == 0
        assert agent.summary()["execution_mode"] == "replay"

    def test_test_mode_without_llm_backend_is_explicit_synthetic_execution(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, execution_mode=ExecutionMode.TEST)
        result = agent.execute_with_tools("Use testing fixture")
        assert result.content.startswith("[test:")
        assert result.total_tool_calls == 0
        assert agent.summary()["execution_mode"] == "test"

    def test_tool_call_parsing(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        parsed = agent._parse_tool_call("TOOL_CALL: calc(expression=2+2)")
        assert parsed is not None
        assert parsed[0] == "calc"
        assert parsed[1]["expression"] == "2+2"

    def test_tool_call_parsing_with_quotes(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        parsed = agent._parse_tool_call("TOOL_CALL: echo(text='hello, world')")
        assert parsed is not None
        assert parsed[1]["text"] == "hello, world"

    def test_invalid_tool_call_returns_none(self):
        agent = ToolAugmentedAgent(tool_registry=_setup())
        assert agent._parse_tool_call("not a tool call") is None

    def test_filtered_tools(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, dry_run=True)
        result = agent.execute_with_tools("test", tool_ids=["calc"])
        # Only calc should be mentioned in prompt
        assert result.content

    def test_filtered_tools_are_enforced(self):
        reg = _setup()
        agent = ToolAugmentedAgent(
            tool_registry=reg,
            llm_fn=lambda _: "TOOL_CALL: echo(text='blocked')",
        )
        result = agent.execute_with_tools("test", tool_ids=["calc"])
        assert result.total_tool_calls == 1
        assert result.all_succeeded is False
        assert result.tool_calls[0].tool_id == "echo"
        assert "tool not allowed" in result.tool_calls[0].result.error

    def test_max_tool_calls(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, max_tool_calls=2, dry_run=True)
        # Agent won't exceed max even if LLM requests more
        result = agent.execute_with_tools("test")
        assert result.total_tool_calls <= 2

    def test_summary(self):
        reg = _setup()
        agent = ToolAugmentedAgent(tool_registry=reg, dry_run=True)
        agent.execute_with_tools("test")
        s = agent.summary()
        assert s["executions"] == 1
        assert s["available_tools"] == 2
        assert s["execution_mode"] == "dry_run"
