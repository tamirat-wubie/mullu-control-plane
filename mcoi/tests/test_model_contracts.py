"""Purpose: verify model contracts align to shared schemas.
Governance scope: model contract tests only.
Dependencies: model contracts module.
Invariants: model outputs are bounded external inferences; validation gates downstream use.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)


_CLOCK = "2026-03-19T00:00:00+00:00"


def test_model_invocation_validates() -> None:
    inv = ModelInvocation(
        invocation_id="inv-1",
        model_id="model-gpt4",
        prompt_hash="hash-abc",
        invoked_at=_CLOCK,
        input_tokens=100,
        cost_estimate=0.005,
    )
    assert inv.invocation_id == "inv-1"
    assert inv.input_tokens == 100


def test_model_invocation_minimal() -> None:
    inv = ModelInvocation(
        invocation_id="inv-1",
        model_id="m-1",
        prompt_hash="h-1",
        invoked_at=_CLOCK,
    )
    assert inv.input_tokens is None
    assert inv.cost_estimate is None


def test_model_invocation_rejects_negative_tokens() -> None:
    with pytest.raises(ValueError, match="input_tokens"):
        ModelInvocation(
            invocation_id="inv-1",
            model_id="m-1",
            prompt_hash="h-1",
            invoked_at=_CLOCK,
            input_tokens=-1,
        )


def test_model_invocation_rejects_negative_cost() -> None:
    with pytest.raises(ValueError, match="cost_estimate"):
        ModelInvocation(
            invocation_id="inv-1",
            model_id="m-1",
            prompt_hash="h-1",
            invoked_at=_CLOCK,
            cost_estimate=-0.01,
        )


def test_model_response_validates() -> None:
    resp = ModelResponse(
        response_id="resp-1",
        invocation_id="inv-1",
        status=ModelStatus.SUCCEEDED,
        output_digest="digest-xyz",
        completed_at=_CLOCK,
        validation_status=ValidationStatus.PASSED,
        output_tokens=50,
        actual_cost=0.003,
    )
    assert resp.status is ModelStatus.SUCCEEDED
    assert resp.validation_status is ValidationStatus.PASSED


def test_model_response_rejects_negative_output_tokens() -> None:
    with pytest.raises(ValueError, match="output_tokens"):
        ModelResponse(
            response_id="resp-1",
            invocation_id="inv-1",
            status=ModelStatus.SUCCEEDED,
            output_digest="d-1",
            completed_at=_CLOCK,
            validation_status=ValidationStatus.PASSED,
            output_tokens=-1,
        )


def test_model_response_serializes() -> None:
    resp = ModelResponse(
        response_id="resp-1",
        invocation_id="inv-1",
        status=ModelStatus.FAILED,
        output_digest="d-1",
        completed_at=_CLOCK,
        validation_status=ValidationStatus.FAILED,
    )
    d = resp.to_dict()
    assert d["status"] == "failed"
    assert d["validation_status"] == "failed"


def test_model_status_values() -> None:
    assert len(ModelStatus) == 3


def test_validation_status_values() -> None:
    assert len(ValidationStatus) == 3
    assert ValidationStatus.PENDING == "pending"
