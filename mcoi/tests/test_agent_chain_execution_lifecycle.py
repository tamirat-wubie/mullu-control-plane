"""Purpose: bind agent chain execution lifecycle witnesses to exact anchors.
Governance scope: sequential chain execution, bounded failure behavior, history
    read models, and governed HTTP chain endpoint responses.
Dependencies: agent_chain core engine and FastAPI test client fixture.
Invariants:
  - Chain steps execute in declared order.
  - Prior step output is the only propagated chain state.
  - Failure details are bounded before exposure.
  - Chain endpoint and history read models remain governed and bounded.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.agent_chain import AgentChainEngine, ChainStep

FIXED_CLOCK_VALUE = "2026-05-16T12:00:00Z"


@dataclass(frozen=True, slots=True)
class _LLMResponse:
    content: str
    cost: float = 0.01
    succeeded: bool = True
    error: str = ""


def _fixed_clock() -> str:
    return FIXED_CLOCK_VALUE


def _engine(prompts: list[str] | None = None) -> AgentChainEngine:
    prompt_log = prompts if prompts is not None else []

    def llm_fn(prompt: str) -> _LLMResponse:
        prompt_log.append(prompt)
        return _LLMResponse(content=f"output[{prompt}]")

    return AgentChainEngine(clock=_fixed_clock, llm_fn=llm_fn)


def test_chain_execute_single_step() -> None:
    prompts: list[str] = []
    result = _engine(prompts).execute(
        [ChainStep(step_id="s1", name="Summarize", prompt_template="Summarize {{input}}")],
        initial_input="invoice",
    )

    assert result.chain_id == "chain-1"
    assert result.succeeded is True
    assert len(result.steps) == 1
    assert result.steps[0].step_id == "s1"
    assert result.final_output == "output[Summarize invoice]"
    assert prompts == ["Summarize invoice"]


def test_chain_execute_two_steps() -> None:
    result = _engine().execute(
        [
            ChainStep(step_id="s1", name="Summarize", prompt_template="Summarize {{input}}"),
            ChainStep(step_id="s2", name="Refine", prompt_template="Refine {{prev}}"),
        ],
        initial_input="case packet",
    )

    assert result.succeeded is True
    assert len(result.steps) == 2
    assert [step.step_id for step in result.steps] == ["s1", "s2"]
    assert result.total_cost == 0.02
    assert result.final_output.startswith("output[Refine output[Summarize case packet]")


def test_chain_prev_template_propagates_output() -> None:
    prompts: list[str] = []
    result = _engine(prompts).execute(
        [
            ChainStep(step_id="s1", name="Extract", prompt_template="Extract {{input}}"),
            ChainStep(step_id="s2", name="Use Prior", prompt_template="Use {{prev}}"),
        ],
        initial_input="source",
    )

    assert result.succeeded is True
    assert prompts[0] == "Extract source"
    assert prompts[1] == "Use output[Extract source]"
    assert "{{prev}}" not in prompts[1]
    assert "{{input}}" not in prompts[1]


def test_chain_halt_on_failure_bounded() -> None:
    calls: list[str] = []

    def failing_llm(prompt: str) -> _LLMResponse:
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("raw chain provider secret")
        return _LLMResponse(content=f"ok-{len(calls)}")

    result = AgentChainEngine(clock=_fixed_clock, llm_fn=failing_llm).execute(
        [
            ChainStep(step_id="s1", name="First", prompt_template="first"),
            ChainStep(step_id="s2", name="Second", prompt_template="second", on_failure="halt"),
            ChainStep(step_id="s3", name="Third", prompt_template="third"),
        ]
    )

    assert result.succeeded is False
    assert len(result.steps) == 2
    assert calls == ["first", "second"]
    assert result.steps[1].error == "chain execution error (RuntimeError)"
    assert result.error == "chain execution failed"
    assert "raw chain provider secret" not in str(result)


def test_chain_skip_on_failure_continues() -> None:
    calls: list[str] = []

    def failing_llm(prompt: str) -> _LLMResponse:
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("raw skipped chain secret")
        return _LLMResponse(content=f"ok-{len(calls)}")

    result = AgentChainEngine(clock=_fixed_clock, llm_fn=failing_llm).execute(
        [
            ChainStep(step_id="s1", name="First", prompt_template="first"),
            ChainStep(step_id="s2", name="Second", prompt_template="second", on_failure="skip"),
            ChainStep(step_id="s3", name="Third", prompt_template="third {{prev}}"),
        ]
    )

    assert result.succeeded is True
    assert len(result.steps) == 3
    assert result.steps[1].succeeded is False
    assert result.steps[1].error == "chain execution error (RuntimeError)"
    assert calls == ["first", "second", "third ok-1"]
    assert "raw skipped chain secret" not in str(result)


def test_chain_returned_failure_redacted() -> None:
    def failed_result(_prompt: str) -> _LLMResponse:
        return _LLMResponse(content="", succeeded=False, error="provider secret detail")

    result = AgentChainEngine(clock=_fixed_clock, llm_fn=failed_result).execute(
        [ChainStep(step_id="s1", name="Failing", prompt_template="fail", on_failure="halt")]
    )

    assert result.succeeded is False
    assert len(result.steps) == 1
    assert result.steps[0].succeeded is False
    assert result.steps[0].error == "chain step failed"
    assert result.error == "chain execution failed"
    assert "provider secret detail" not in str(result)


def test_chain_history_bounded() -> None:
    engine = _engine()
    first = engine.execute([ChainStep(step_id="s1", name="First", prompt_template="first")])
    second = engine.execute([ChainStep(step_id="s2", name="Second", prompt_template="second")])

    history = engine.history(limit=1)
    summary = engine.summary()
    assert engine.total_chains == 2
    assert history == [second]
    assert first.chain_id == "chain-1"
    assert summary["total"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0


def test_chain_endpoint_governed(test_client) -> None:
    response = test_client.post(
        "/api/v1/chain/execute",
        json={
            "steps": [
                {"step_id": "s1", "name": "Summarize", "prompt_template": "Summarize {{input}}"},
                {"step_id": "s2", "name": "Refine", "prompt_template": "Refine {{prev}}"},
            ],
            "initial_input": "bounded endpoint input",
            "tenant_id": "tenant-chain-anchor",
        },
    )
    body = response.json()
    history_response = test_client.get("/api/v1/chain/history", params={"limit": 1})
    history_body = history_response.json()

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["succeeded"] is True
    assert len(body["steps"]) == 2
    assert set(body["steps"][0]) == {"id", "name", "succeeded", "cost"}
    assert body["chain_id"].startswith("chain-")
    assert history_response.status_code == 200
    assert len(history_body["chains"]) <= 1
    assert history_body["summary"]["total"] >= len(history_body["chains"])
