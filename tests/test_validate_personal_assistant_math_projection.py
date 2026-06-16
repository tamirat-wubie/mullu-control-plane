"""Purpose: verify Personal Assistant math projection validation.
Governance scope: planning-only math reasoning, receipt integrity, no-effect
boundaries, and private payload denial.
Dependencies: scripts.validate_personal_assistant_math_projection.
Invariants: math projections cannot move money, write systems, mutate
connectors, publish externally, deploy, write memory, serialize secrets, or
activate Nested Mind.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_personal_assistant_math_projection import (
    build_runtime_math_projection_evidence,
    validate_personal_assistant_math_projection,
)


def test_personal_assistant_math_projection_fixture_validates() -> None:
    result = validate_personal_assistant_math_projection()

    assert result.valid is True
    assert result.runtime_validated is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.assurance_outcome == "AwaitingEvidence"
    assert result.errors == ()


def test_runtime_math_projection_blocks_effect_boundaries() -> None:
    envelope = build_runtime_math_projection_evidence()
    effect_boundary = envelope["effect_boundary"]
    ready_projection = envelope["projections"][1]
    plan = ready_projection["plan"]
    receipt = ready_projection["receipt"]

    assert effect_boundary["math_projection_records_allowed"] is True
    assert effect_boundary["money_movement_allowed"] is False
    assert effect_boundary["system_of_record_write_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert effect_boundary["deployment_allowed"] is False
    assert effect_boundary["nested_mind_live_activation_allowed"] is False
    assert plan["scenario_totals"] == [
        {"scenario_ref": "baseline", "unit": "usd_per_month", "total": "150"},
        {"scenario_ref": "proposed", "unit": "usd_per_month", "total": "120"},
    ]
    assert "payment_not_moved" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_math_projection_validator_rejects_money_or_write_authority(tmp_path) -> None:
    envelope = build_runtime_math_projection_evidence()
    envelope["effect_boundary"]["money_movement_allowed"] = True
    envelope["projections"][1]["plan"]["system_of_record_write_allowed"] = True
    projection_path = tmp_path / "math_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_math_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("money_movement_allowed must be false" in error for error in result.errors)
    assert any("system_of_record_write_allowed must be false" in error for error in result.errors)


def test_math_projection_validator_rejects_receipt_drift(tmp_path) -> None:
    envelope = build_runtime_math_projection_evidence()
    envelope["projections"][1]["receipt"]["actions_not_taken"].remove("payment_not_moved")
    envelope["projections"][1]["receipt"]["metadata"]["money_movement_allowed"] = True
    projection_path = tmp_path / "math_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_math_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("actions_not_taken must include payment_not_moved" in error for error in result.errors)
    assert any("metadata.money_movement_allowed must be false" in error for error in result.errors)


def test_math_projection_validator_rejects_raw_private_and_secret(tmp_path) -> None:
    envelope = build_runtime_math_projection_evidence()
    envelope["projections"][1]["plan"]["known_values"][0]["raw_body"] = "private worksheet"
    envelope["projections"][1]["plan"]["assumptions"].append("Bearer secret-token-value")
    projection_path = tmp_path / "math_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_math_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("raw private field is forbidden" in error for error in result.errors)
    assert any("secret-like value must not be serialized" in error for error in result.errors)


def test_math_projection_validator_requires_ready_and_blocked_items(tmp_path) -> None:
    envelope = build_runtime_math_projection_evidence()
    ready_only = deepcopy(envelope)
    ready_only["projections"] = [ready_only["projections"][1]]
    ready_only["projection_count"] = 1
    ready_only["projection_ids"] = [ready_only["projections"][0]["projection_id"]]
    ready_only["receipt_ids"] = [ready_only["projections"][0]["receipt"]["receipt_id"]]
    projection_path = tmp_path / "math_projection.json"
    projection_path.write_text(__import__("json").dumps(ready_only), encoding="utf-8")

    result = validate_personal_assistant_math_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("blocked math projection" in error for error in result.errors)


def test_math_projection_runtime_rejects_secret_like_value() -> None:
    from mcoi_runtime.personal_assistant import interpret_user_request, plan_math_reasoning

    intent = interpret_user_request(
        "Compare two monthly cost scenarios.",
        request_id="pa_request_math_secret_001",
        submitted_at="2026-06-15T20:00:00+00:00",
    )

    with pytest.raises(Exception, match="secret-like"):
        plan_math_reasoning(
            intent,
            generated_at="2026-06-15T20:05:00+00:00",
            problem_statement="Compare costs.",
            known_values=(
                {
                    "label": "secret ghp_abcdef123456",
                    "scenario_ref": "baseline",
                    "value": "1",
                    "unit": "usd",
                    "source_ref": "operator_supplied",
                    "notes": "",
                },
            ),
        )
