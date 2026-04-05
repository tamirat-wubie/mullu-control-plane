"""Phase 215A — Agent chain tests."""

import pytest
from mcoi_runtime.core.agent_chain import AgentChainEngine, ChainStep
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget, LLMProvider, LLMResult

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _engine():
    bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
    bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))
    return AgentChainEngine(clock=FIXED_CLOCK, llm_fn=lambda p: bridge.complete(p, budget_id="default"))


class TestAgentChain:
    def test_single_step(self):
        eng = _engine()
        result = eng.execute([ChainStep(step_id="s1", name="A", prompt_template="Hello {{input}}")], initial_input="world")
        assert result.succeeded is True
        assert len(result.steps) == 1

    def test_two_steps(self):
        eng = _engine()
        result = eng.execute([
            ChainStep(step_id="s1", name="Summarize", prompt_template="Summarize: {{input}}"),
            ChainStep(step_id="s2", name="Refine", prompt_template="Refine: {{prev}}"),
        ], initial_input="text")
        assert result.succeeded is True
        assert len(result.steps) == 2

    def test_prev_template(self):
        eng = _engine()
        result = eng.execute([
            ChainStep(step_id="s1", name="A", prompt_template="Generate: {{input}}"),
            ChainStep(step_id="s2", name="B", prompt_template="Process: {{prev}}"),
        ], initial_input="data")
        assert result.succeeded is True
        assert result.final_output  # Should have content from step 2

    def test_halt_on_failure(self):
        call_count = {"n": 0}
        def failing_fn(prompt):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("step 2 fails")
            bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
            bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))
            return bridge.complete(prompt, budget_id="default")

        eng = AgentChainEngine(clock=FIXED_CLOCK, llm_fn=failing_fn)
        result = eng.execute([
            ChainStep(step_id="s1", name="A", prompt_template="a"),
            ChainStep(step_id="s2", name="B", prompt_template="b", on_failure="halt"),
            ChainStep(step_id="s3", name="C", prompt_template="c"),
        ])
        assert result.succeeded is False
        assert len(result.steps) == 2  # s3 never ran
        assert result.steps[1].error == "chain execution error (RuntimeError)"
        assert result.error == "chain execution failed"
        assert "step 2 fails" not in result.error
        assert "s2" not in result.error

    def test_skip_on_failure(self):
        call_count = {"n": 0}
        def failing_fn(prompt):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("step 2 fails")
            bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
            bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))
            return bridge.complete(prompt, budget_id="default")

        eng = AgentChainEngine(clock=FIXED_CLOCK, llm_fn=failing_fn)
        result = eng.execute([
            ChainStep(step_id="s1", name="A", prompt_template="a"),
            ChainStep(step_id="s2", name="B", prompt_template="b", on_failure="skip"),
            ChainStep(step_id="s3", name="C", prompt_template="c"),
        ])
        assert result.succeeded is True
        assert len(result.steps) == 3
        assert result.steps[1].succeeded is False
        assert result.steps[1].error == "chain execution error (RuntimeError)"
        assert "step 2 fails" not in result.steps[1].error

    def test_returned_failure_error_redacted(self):
        def failed_result(prompt):
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name="stub-model",
                provider=LLMProvider.STUB,
                finished=False,
                error="provider secret detail",
            )

        eng = AgentChainEngine(clock=FIXED_CLOCK, llm_fn=failed_result)
        result = eng.execute([
            ChainStep(step_id="s1", name="A", prompt_template="a", on_failure="halt"),
        ])
        assert result.succeeded is False
        assert result.steps[0].error == "chain step failed"
        assert result.error == "chain execution failed"
        assert "provider secret detail" not in result.error
        assert "s1" not in result.error

    def test_history(self):
        eng = _engine()
        eng.execute([ChainStep(step_id="s1", name="A", prompt_template="x")])
        eng.execute([ChainStep(step_id="s1", name="B", prompt_template="y")])
        assert eng.total_chains == 2

    def test_summary(self):
        eng = _engine()
        eng.execute([ChainStep(step_id="s1", name="A", prompt_template="x")])
        s = eng.summary()
        assert s["total"] == 1
        assert s["succeeded"] == 1

    def test_empty_chain(self):
        eng = _engine()
        result = eng.execute([])
        assert result.succeeded is True
        assert len(result.steps) == 0
