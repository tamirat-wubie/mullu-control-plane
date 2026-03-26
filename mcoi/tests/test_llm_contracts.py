"""Phase 199A — LLM contract tests.

Tests: LLMMessage, LLMInvocationParams, LLMResult, LLMBudget, LLMProvider, LLMRole.
"""

import pytest
from mcoi_runtime.contracts.llm import (
    LLMBudget,
    LLMInvocationParams,
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
)


# ═══ LLMMessage ═══

class TestLLMMessage:
    def test_valid_message(self):
        msg = LLMMessage(role=LLMRole.USER, content="hello")
        assert msg.role == LLMRole.USER
        assert msg.content == "hello"

    def test_system_role(self):
        msg = LLMMessage(role=LLMRole.SYSTEM, content="you are helpful")
        assert msg.role == LLMRole.SYSTEM

    def test_assistant_role(self):
        msg = LLMMessage(role=LLMRole.ASSISTANT, content="I can help")
        assert msg.role == LLMRole.ASSISTANT

    def test_empty_content_allowed(self):
        msg = LLMMessage(role=LLMRole.USER, content="")
        assert msg.content == ""

    def test_invalid_role_rejected(self):
        with pytest.raises(ValueError, match="role must be"):
            LLMMessage(role="invalid", content="test")

    def test_non_string_content_rejected(self):
        with pytest.raises(ValueError, match="content must be"):
            LLMMessage(role=LLMRole.USER, content=123)

    def test_frozen(self):
        msg = LLMMessage(role=LLMRole.USER, content="test")
        with pytest.raises(AttributeError):
            msg.content = "changed"


# ═══ LLMInvocationParams ═══

class TestLLMInvocationParams:
    def _msg(self, role="user", content="test"):
        return LLMMessage(role=LLMRole(role), content=content)

    def test_valid_params(self):
        params = LLMInvocationParams(
            model_name="claude-sonnet-4-20250514",
            messages=(self._msg(),),
        )
        assert params.model_name == "claude-sonnet-4-20250514"
        assert len(params.messages) == 1
        assert params.max_tokens == 1024
        assert params.temperature == 0.0

    def test_custom_params(self):
        params = LLMInvocationParams(
            model_name="gpt-4o",
            messages=(self._msg("system", "sys"), self._msg("user", "hi")),
            max_tokens=2048,
            temperature=0.7,
            tenant_id="t1",
            budget_id="b1",
        )
        assert params.max_tokens == 2048
        assert params.temperature == 0.7
        assert params.tenant_id == "t1"
        assert params.budget_id == "b1"
        assert len(params.messages) == 2

    def test_empty_model_name_rejected(self):
        with pytest.raises(ValueError):
            LLMInvocationParams(model_name="", messages=(self._msg(),))

    def test_empty_messages_rejected(self):
        with pytest.raises(ValueError, match="non-empty tuple"):
            LLMInvocationParams(model_name="test", messages=())

    def test_invalid_message_type_rejected(self):
        with pytest.raises(ValueError, match="each message"):
            LLMInvocationParams(model_name="test", messages=("not a message",))

    def test_zero_max_tokens_rejected(self):
        with pytest.raises(ValueError, match="max_tokens"):
            LLMInvocationParams(model_name="test", messages=(self._msg(),), max_tokens=0)

    def test_negative_temperature_rejected(self):
        with pytest.raises(ValueError, match="temperature"):
            LLMInvocationParams(model_name="test", messages=(self._msg(),), temperature=-0.1)

    def test_frozen(self):
        params = LLMInvocationParams(model_name="test", messages=(self._msg(),))
        with pytest.raises(AttributeError):
            params.model_name = "changed"

    def test_metadata_frozen(self):
        params = LLMInvocationParams(
            model_name="test",
            messages=(self._msg(),),
            metadata={"key": "val"},
        )
        with pytest.raises(TypeError):
            params.metadata["new"] = "val"


# ═══ LLMResult ═══

class TestLLMResult:
    def test_valid_result(self):
        result = LLMResult(
            content="hello world",
            input_tokens=10,
            output_tokens=5,
            cost=0.001,
            model_name="claude-sonnet-4-20250514",
            provider=LLMProvider.ANTHROPIC,
        )
        assert result.content == "hello world"
        assert result.total_tokens == 15
        assert result.succeeded is True
        assert result.cost == 0.001

    def test_failed_result(self):
        result = LLMResult(
            content="",
            input_tokens=0,
            output_tokens=0,
            cost=0.0,
            model_name="test",
            provider=LLMProvider.STUB,
            finished=False,
            error="timeout",
        )
        assert result.succeeded is False
        assert result.error == "timeout"

    def test_error_with_finished_true(self):
        result = LLMResult(
            content="",
            input_tokens=0,
            output_tokens=0,
            cost=0.0,
            model_name="test",
            provider=LLMProvider.STUB,
            finished=True,
            error="something went wrong",
        )
        assert result.succeeded is False

    def test_negative_tokens_rejected(self):
        with pytest.raises(ValueError, match="input_tokens"):
            LLMResult(content="", input_tokens=-1, output_tokens=0, cost=0.0, model_name="t", provider=LLMProvider.STUB)

    def test_negative_output_tokens_rejected(self):
        with pytest.raises(ValueError, match="output_tokens"):
            LLMResult(content="", input_tokens=0, output_tokens=-1, cost=0.0, model_name="t", provider=LLMProvider.STUB)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError):
            LLMResult(content="", input_tokens=0, output_tokens=0, cost=-0.01, model_name="t", provider=LLMProvider.STUB)

    def test_empty_model_name_rejected(self):
        with pytest.raises(ValueError):
            LLMResult(content="", input_tokens=0, output_tokens=0, cost=0.0, model_name="", provider=LLMProvider.STUB)

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValueError, match="provider must be"):
            LLMResult(content="", input_tokens=0, output_tokens=0, cost=0.0, model_name="t", provider="invalid")

    def test_frozen(self):
        result = LLMResult(content="x", input_tokens=0, output_tokens=0, cost=0.0, model_name="t", provider=LLMProvider.STUB)
        with pytest.raises(AttributeError):
            result.content = "changed"

    def test_all_providers(self):
        for p in LLMProvider:
            result = LLMResult(content="", input_tokens=0, output_tokens=0, cost=0.0, model_name="m", provider=p)
            assert result.provider == p


# ═══ LLMBudget ═══

class TestLLMBudget:
    def test_valid_budget(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0)
        assert budget.remaining == 10.0
        assert budget.exhausted is False
        assert budget.calls_made == 0

    def test_partially_spent(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, spent=3.5)
        assert budget.remaining == 6.5
        assert budget.exhausted is False

    def test_exhausted_by_cost(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, spent=10.0)
        assert budget.remaining == 0.0
        assert budget.exhausted is True

    def test_exhausted_by_calls(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=100.0, max_calls=5, calls_made=5)
        assert budget.exhausted is True

    def test_remaining_never_negative(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=5.0, spent=10.0)
        assert budget.remaining == 0.0

    def test_empty_budget_id_rejected(self):
        with pytest.raises(ValueError):
            LLMBudget(budget_id="", tenant_id="t1", max_cost=10.0)

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            LLMBudget(budget_id="b1", tenant_id="", max_cost=10.0)

    def test_negative_max_cost_rejected(self):
        with pytest.raises(ValueError):
            LLMBudget(budget_id="b1", tenant_id="t1", max_cost=-1.0)

    def test_zero_max_tokens_per_call_rejected(self):
        with pytest.raises(ValueError, match="max_tokens_per_call"):
            LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, max_tokens_per_call=0)

    def test_zero_max_calls_rejected(self):
        with pytest.raises(ValueError, match="max_calls"):
            LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, max_calls=0)

    def test_negative_calls_made_rejected(self):
        with pytest.raises(ValueError, match="calls_made"):
            LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, calls_made=-1)

    def test_frozen(self):
        budget = LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0)
        with pytest.raises(AttributeError):
            budget.spent = 5.0


# ═══ Enums ═══

class TestLLMEnums:
    def test_provider_values(self):
        assert LLMProvider.ANTHROPIC == "anthropic"
        assert LLMProvider.OPENAI == "openai"
        assert LLMProvider.STUB == "stub"

    def test_role_values(self):
        assert LLMRole.SYSTEM == "system"
        assert LLMRole.USER == "user"
        assert LLMRole.ASSISTANT == "assistant"

    def test_provider_from_string(self):
        assert LLMProvider("anthropic") == LLMProvider.ANTHROPIC

    def test_role_from_string(self):
        assert LLMRole("user") == LLMRole.USER
