"""Purpose: verify Personal Assistant planning projection validation.
Governance scope: schedule planning preview, receipt integrity, no-effect
boundaries, and private payload denial.
Dependencies: scripts.validate_personal_assistant_planning_projection.
Invariants: planning projections cannot write calendar events, write tasks,
message people, mutate systems, move money, deploy, write memory, serialize
secrets, or activate Nested Mind.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_personal_assistant_planning_projection import (
    build_runtime_planning_projection_evidence,
    validate_personal_assistant_planning_projection,
)


def test_personal_assistant_planning_projection_fixture_validates() -> None:
    result = validate_personal_assistant_planning_projection()

    assert result.valid is True
    assert result.runtime_validated is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.assurance_outcome == "AwaitingEvidence"
    assert result.errors == ()


def test_runtime_planning_projection_blocks_effect_boundaries_and_assigns_capacity() -> None:
    envelope = build_runtime_planning_projection_evidence()
    effect_boundary = envelope["effect_boundary"]
    ready_projection = envelope["projections"][1]
    plan = ready_projection["plan"]
    receipt = ready_projection["receipt"]

    assert effect_boundary["planning_projection_records_allowed"] is True
    assert effect_boundary["calendar_write_allowed"] is False
    assert effect_boundary["task_write_allowed"] is False
    assert effect_boundary["connector_mutation_allowed"] is False
    assert effect_boundary["deployment_allowed"] is False
    assert effect_boundary["nested_mind_live_activation_allowed"] is False
    assert plan["assignment_plan"] == [
        {"item_ref": "memo", "title": "Write launch memo", "window_ref": "morning", "estimated_minutes": "60", "status": "assigned", "reason": "assigned"},
        {"item_ref": "receipts", "title": "Review receipts", "window_ref": "morning", "estimated_minutes": "45", "status": "assigned", "reason": "assigned"},
        {"item_ref": "followups", "title": "Triage followups", "window_ref": "afternoon", "estimated_minutes": "30", "status": "assigned", "reason": "assigned"},
    ]
    assert plan["capacity_summary"] == [
        {"window_ref": "morning", "label": "Morning focus", "capacity_minutes": "120", "assigned_minutes": "105", "remaining_minutes": "15", "status": "within_capacity"},
        {"window_ref": "afternoon", "label": "Afternoon review", "capacity_minutes": "90", "assigned_minutes": "30", "remaining_minutes": "60", "status": "within_capacity"},
    ]
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "task_not_written" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_planning_projection_validator_rejects_calendar_or_task_authority(tmp_path) -> None:
    envelope = build_runtime_planning_projection_evidence()
    envelope["effect_boundary"]["calendar_write_allowed"] = True
    envelope["projections"][1]["plan"]["task_write_allowed"] = True
    projection_path = tmp_path / "planning_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_planning_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("calendar_write_allowed must be false" in error for error in result.errors)
    assert any("task_write_allowed must be false" in error for error in result.errors)


def test_planning_projection_validator_rejects_receipt_drift(tmp_path) -> None:
    envelope = build_runtime_planning_projection_evidence()
    envelope["projections"][1]["receipt"]["actions_not_taken"].remove("calendar_event_not_created")
    envelope["projections"][1]["receipt"]["metadata"]["calendar_write_allowed"] = True
    projection_path = tmp_path / "planning_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_planning_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("actions_not_taken must include calendar_event_not_created" in error for error in result.errors)
    assert any("metadata.calendar_write_allowed must be false" in error for error in result.errors)


def test_planning_projection_validator_rejects_raw_private_and_secret(tmp_path) -> None:
    envelope = build_runtime_planning_projection_evidence()
    envelope["projections"][1]["plan"]["work_items"][0]["raw_body"] = "private calendar export"
    envelope["projections"][1]["plan"]["assumptions"].append("Bearer secret-token-value")
    projection_path = tmp_path / "planning_projection.json"
    projection_path.write_text(__import__("json").dumps(envelope), encoding="utf-8")

    result = validate_personal_assistant_planning_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("raw private field is forbidden" in error for error in result.errors)
    assert any("secret-like value must not be serialized" in error for error in result.errors)


def test_planning_projection_validator_requires_ready_and_blocked_items(tmp_path) -> None:
    envelope = build_runtime_planning_projection_evidence()
    ready_only = deepcopy(envelope)
    ready_only["projections"] = [ready_only["projections"][1]]
    ready_only["projection_count"] = 1
    ready_only["projection_ids"] = [ready_only["projections"][0]["projection_id"]]
    ready_only["receipt_ids"] = [ready_only["projections"][0]["receipt"]["receipt_id"]]
    projection_path = tmp_path / "planning_projection.json"
    projection_path.write_text(__import__("json").dumps(ready_only), encoding="utf-8")

    result = validate_personal_assistant_planning_projection(projection_path=projection_path, validate_runtime=False)

    assert result.valid is False
    assert any("blocked planning projection" in error for error in result.errors)


def test_planning_projection_runtime_rejects_secret_like_value() -> None:
    from mcoi_runtime.personal_assistant import interpret_user_request, plan_schedule_optimization

    intent = interpret_user_request(
        "Optimize schedule with operator supplied windows.",
        request_id="pa_request_planning_secret_001",
        submitted_at="2026-06-16T04:00:00+00:00",
    )

    with pytest.raises(Exception, match="secret-like"):
        plan_schedule_optimization(
            intent,
            generated_at="2026-06-16T04:05:00+00:00",
            objective="Plan day.",
            time_windows=(
                {
                    "window_ref": "secret-ghp_abcdef123456",
                    "label": "Morning",
                    "start": "2026-06-16T09:00:00-04:00",
                    "end": "2026-06-16T10:00:00-04:00",
                    "capacity_minutes": 60,
                    "source_ref": "operator_supplied",
                    "notes": "",
                },
            ),
        )
