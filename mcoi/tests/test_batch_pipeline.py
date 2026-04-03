"""Phase 205C — Batch LLM pipeline tests."""

import pytest
from mcoi_runtime.core.batch_pipeline import BatchPipeline, PipelineStep
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget, LLMProvider, LLMResult

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _bridge():
    bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
    bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))
    return bridge


def _pipeline():
    bridge = _bridge()
    return BatchPipeline(
        clock=FIXED_CLOCK,
        llm_complete_fn=lambda prompt, **kw: bridge.complete(prompt, **kw),
    )


class TestBatchPipeline:
    def test_single_step(self):
        pipe = _pipeline()
        result = pipe.execute([
            PipelineStep(step_id="s1", name="Step 1", prompt_template="Hello {input}"),
        ], initial_input="world")
        assert result.succeeded is True
        assert len(result.steps) == 1
        assert result.final_output

    def test_two_steps(self):
        pipe = _pipeline()
        result = pipe.execute([
            PipelineStep(step_id="s1", name="Summarize", prompt_template="Summarize: {input}"),
            PipelineStep(step_id="s2", name="Refine", prompt_template="Refine: {input}"),
        ], initial_input="some text")
        assert result.succeeded is True
        assert len(result.steps) == 2
        assert result.total_cost >= 0

    def test_three_steps(self):
        pipe = _pipeline()
        result = pipe.execute([
            PipelineStep(step_id="s1", name="A", prompt_template="A: {input}"),
            PipelineStep(step_id="s2", name="B", prompt_template="B: {input}"),
            PipelineStep(step_id="s3", name="C", prompt_template="C: {input}"),
        ], initial_input="start")
        assert result.succeeded is True
        assert len(result.steps) == 3

    def test_pipeline_id_increments(self):
        pipe = _pipeline()
        r1 = pipe.execute([PipelineStep(step_id="s1", name="A", prompt_template="X")])
        r2 = pipe.execute([PipelineStep(step_id="s1", name="A", prompt_template="Y")])
        assert r1.pipeline_id != r2.pipeline_id

    def test_step_cost_tracking(self):
        pipe = _pipeline()
        result = pipe.execute([
            PipelineStep(step_id="s1", name="A", prompt_template="test"),
            PipelineStep(step_id="s2", name="B", prompt_template="test"),
        ])
        assert result.total_cost >= 0
        assert result.total_tokens >= 0

    def test_error_in_step(self):
        def failing_fn(prompt, **kw):
            raise RuntimeError("LLM down")

        pipe = BatchPipeline(clock=FIXED_CLOCK, llm_complete_fn=failing_fn)
        result = pipe.execute([
            PipelineStep(step_id="s1", name="Fail", prompt_template="test"),
        ])
        assert result.succeeded is False
        assert result.steps[0].error == "pipeline execution error (RuntimeError)"
        assert result.error == "step s1 failed: pipeline execution error (RuntimeError)"
        assert "LLM down" not in result.error

    def test_fail_fast(self):
        call_count = 0
        def counting_fn(prompt, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("step 2 fails")
            bridge = _bridge()
            return bridge.complete(prompt, **kw)

        pipe = BatchPipeline(clock=FIXED_CLOCK, llm_complete_fn=counting_fn)
        result = pipe.execute([
            PipelineStep(step_id="s1", name="A", prompt_template="a"),
            PipelineStep(step_id="s2", name="B", prompt_template="b"),
            PipelineStep(step_id="s3", name="C", prompt_template="c"),
        ])
        assert result.succeeded is False
        assert len(result.steps) == 2  # s3 never ran
        assert result.steps[1].error == "pipeline execution error (RuntimeError)"
        assert result.error == "step s2 failed: pipeline execution error (RuntimeError)"
        assert "step 2 fails" not in result.error

    def test_returned_failure_error_redacted(self):
        def failed_result(prompt, **kw):
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

        pipe = BatchPipeline(clock=FIXED_CLOCK, llm_complete_fn=failed_result)
        result = pipe.execute([
            PipelineStep(step_id="s1", name="Fail", prompt_template="test"),
        ])
        assert result.succeeded is False
        assert result.steps[0].error == "pipeline step failed"
        assert result.error == "step s1 failed: pipeline step failed"
        assert "provider secret detail" not in result.error

    def test_history(self):
        pipe = _pipeline()
        pipe.execute([PipelineStep(step_id="s1", name="A", prompt_template="x")])
        pipe.execute([PipelineStep(step_id="s1", name="B", prompt_template="y")])
        assert pipe.total_pipelines == 2
        assert len(pipe.history()) == 2

    def test_summary(self):
        pipe = _pipeline()
        pipe.execute([PipelineStep(step_id="s1", name="A", prompt_template="ok")])
        summary = pipe.summary()
        assert summary["total"] == 1
        assert summary["succeeded"] == 1

    def test_empty_pipeline(self):
        pipe = _pipeline()
        result = pipe.execute([])
        assert result.succeeded is True
        assert result.final_output == ""
        assert len(result.steps) == 0

    def test_input_placeholder(self):
        pipe = _pipeline()
        result = pipe.execute([
            PipelineStep(step_id="s1", name="A", prompt_template="Process this: {input}"),
        ], initial_input="raw data")
        assert result.succeeded is True
