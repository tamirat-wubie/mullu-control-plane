"""Tests for the simple governed platform facade.

Purpose: verify non-technical action checks project MVK governance decisions
into ready, needs-review, and blocked outcomes.
Governance scope: usability projection only; MVK remains the authority for
scope, side-effect, proof, and witness decisions.
Dependencies: simple platform facade, simple CLI, pytest capture, and metadata.
Invariants: simple outcomes preserve proof references, do not bypass scope
checks, and report external side effects as review work.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.simple_cli import guarded_main
from mcoi_runtime.core.simple_platform import (
    SimpleActionRequest,
    SimpleOnboardingGuide,
    SimplePlatform,
    SimpleTaskRequest,
    SimpleWorkflowRequest,
)
from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime

ROOT = Path(__file__).resolve().parents[2]


def test_simple_platform_allows_plain_view_inside_allowed_area() -> None:
    check = SimplePlatform().check_action(
        SimpleActionRequest(
            goal="Review docs",
            action="view",
            target="docs/README.md",
            allowed_area="docs/**",
            actor_id="simple-test",
        )
    )

    assert check.outcome == "ready"
    assert check.ok_to_continue is True
    assert check.message == "This action stays inside the allowed area and has the required proof."
    assert check.proof_stamp_ref.startswith("proof-")
    assert check.boundary_witness_ref.startswith("witness-")


def test_simple_platform_blocks_plain_change_outside_allowed_area() -> None:
    check = SimplePlatform().check_action(
        {
            "goal": "Update project docs",
            "action": "change",
            "target": "deploy/config.json",
            "allowed_area": "docs/**",
            "actor_id": "simple-test",
        }
    )

    assert check.outcome == "blocked"
    assert check.ok_to_continue is False
    assert check.raw_decision == "block"
    assert "The target is outside the allowed area." in check.blocked_reasons
    assert check.next_step == "Narrow the request or change the allowed area, then check again."


def test_simple_platform_sends_external_change_to_review() -> None:
    check = SimplePlatform().check_action(
        SimpleActionRequest(
            goal="Notify support",
            action="send",
            target="support@mullusi.com",
            allowed_area="support@mullusi.com",
            actor_id="simple-test",
        )
    )

    assert check.outcome == "needs_review"
    assert check.ok_to_continue is False
    assert check.raw_decision == "escalate"
    assert "External changes require approval." in check.review_reasons
    assert check.blocked_reasons == ()


def test_simple_platform_task_template_infers_safe_scope() -> None:
    check = SimplePlatform().check_task(
        SimpleTaskRequest(
            task="review_docs",
            target="docs/README.md",
            actor_id="simple-task-test",
        )
    )

    assert check.outcome == "ready"
    assert check.ok_to_continue is True
    assert check.proof_stamp_ref.startswith("proof-")
    assert check.blocked_reasons == ()


def test_simple_platform_task_template_blocks_target_outside_template_scope() -> None:
    check = SimplePlatform().check_task(
        {
            "task": "update-docs",
            "target": "deploy/config.json",
            "actor_id": "simple-task-test",
        }
    )

    assert check.outcome == "blocked"
    assert check.ok_to_continue is False
    assert check.blocked_reasons == ("The target is outside the allowed area.",)


def test_simple_platform_task_template_uses_default_target_for_support_notice() -> None:
    check = SimplePlatform().check_task({"task": "notify-support", "actor_id": "simple-task-test"})

    assert check.outcome == "needs_review"
    assert check.ok_to_continue is False
    assert check.review_reasons == ("External changes require approval.",)


def test_simple_platform_workflow_projects_ready_docs_update_plan() -> None:
    plan = SimplePlatform().check_workflow(
        SimpleWorkflowRequest(
            workflow="docs_update",
            target="docs/README.md",
            actor_id="simple-workflow-test",
        )
    )

    assert plan.outcome == "ready"
    assert plan.ok_to_continue is True
    assert plan.ready_count == 3
    assert plan.review_count == 0
    assert plan.blocked_count == 0
    assert [check.outcome for check in plan.checks] == ["ready", "ready", "ready"]


def test_simple_platform_workflow_blocks_docs_update_outside_docs() -> None:
    plan = SimplePlatform().check_workflow(
        {
            "workflow": "docs-update",
            "target": "deploy/config.json",
            "actor_id": "simple-workflow-test",
        }
    )

    assert plan.outcome == "blocked"
    assert plan.ok_to_continue is False
    assert plan.ready_count == 1
    assert plan.blocked_count == 2
    assert "One or more steps cannot continue" in plan.message
    assert plan.checks[0].blocked_reasons == ("The target is outside the allowed area.",)


def test_simple_platform_workflow_projects_support_notice_review() -> None:
    plan = SimplePlatform().check_workflow({"workflow": "support-notice", "actor_id": "simple-workflow-test"})

    assert plan.outcome == "needs_review"
    assert plan.ok_to_continue is False
    assert plan.review_count == 1
    assert plan.blocked_count == 0
    assert plan.checks[0].review_reasons == ("External changes require approval.",)


def test_simple_platform_onboarding_guide_is_plain_and_non_executing() -> None:
    guide = SimplePlatform.onboarding_guide()
    payload = guide.to_dict()

    assert guide.execution_allowed is False
    assert payload["title"] == "Mullu simple mode"
    assert payload["recommended_path"][0]["command"] == "mullu workflows"
    assert payload["recommended_path"][1]["command"] == "mullu workflow docs-update --target docs/README.md"
    assert payload["outcomes"] == ["Ready", "Needs review", "Blocked"]


def test_simple_platform_onboarding_guide_rejects_execution_authority() -> None:
    try:
        SimpleOnboardingGuide(
            title="Unsafe",
            message="Unsafe guide.",
            recommended_path=(),
            outcomes=("Ready",),
            execution_allowed=True,
        )
    except RuntimeCoreInvariantError as exc:
        assert "simple onboarding guide cannot allow execution" in str(exc)
    else:
        raise AssertionError("onboarding guide must reject execution authority")


def test_simple_platform_rejects_loose_action_target() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="target must be text"):
        SimplePlatform().check_action(
            {
                "goal": "Review docs",
                "action": "view",
                "target": 7,
                "allowed_area": "docs/**",
                "actor_id": "simple-test",
            }
        )


def test_simple_platform_rejects_loose_action_actor() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="actor_id must be text"):
        SimplePlatform().check_action(
            {
                "goal": "Review docs",
                "action": "view",
                "target": "docs/README.md",
                "allowed_area": "docs/**",
                "actor_id": 7,
            }
        )


def test_simple_platform_rejects_loose_task_goal() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="goal must be text"):
        SimplePlatform().check_task(
            {
                "task": "review_docs",
                "target": "docs/README.md",
                "goal": 7,
                "actor_id": "simple-task-test",
            }
        )


def test_simple_platform_rejects_loose_workflow_actor() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="actor_id must be text"):
        SimplePlatform().check_workflow(
            {
                "workflow": "docs_update",
                "target": "docs/README.md",
                "actor_id": 7,
            }
        )


def test_simple_cli_outputs_readable_ready_result(capsys) -> None:
    exit_code = guarded_main(
        [
            "check",
            "--goal",
            "Review docs",
            "--action",
            "view",
            "--target",
            "docs/README.md",
            "--allowed-area",
            "docs/**",
            "--actor-id",
            "simple-cli-test",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Outcome: Ready" in output
    assert "Next: Continue with the action." in output
    assert "Proof: proof-" in output


def test_simple_cli_outputs_json_for_review_result(capsys) -> None:
    exit_code = guarded_main(
        [
            "check",
            "--goal",
            "Notify support",
            "--action",
            "send",
            "--target",
            "support@mullusi.com",
            "--allowed-area",
            "support@mullusi.com",
            "--json",
        ]
    )
    envelope = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "needs_review"
    assert envelope["payload"]["outcome"] == "needs_review"
    assert envelope["payload"]["review_reasons"] == ["External changes require approval."]


def test_simple_cli_task_template_outputs_ready_result(capsys) -> None:
    exit_code = guarded_main(
        [
            "task",
            "review-docs",
            "--target",
            "docs/README.md",
            "--actor-id",
            "simple-cli-test",
            "--json",
        ]
    )
    envelope = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["outcome"] == "ready"


def test_simple_cli_lists_task_templates_as_readable_catalog(capsys) -> None:
    exit_code = guarded_main(["tasks"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Common tasks:" in output
    assert "review-docs" in output
    assert "mullu task review-docs --target <target>" in output
    assert "notify-support" in output


def test_simple_cli_lists_task_templates_as_json(capsys) -> None:
    exit_code = guarded_main(["tasks", "--json"])
    envelope = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert envelope["payload"]["tasks"][0]["task"] == "review_docs"
    assert envelope["payload"]["tasks"][2]["default_target"] == "support@mullusi.com"


def test_simple_cli_workflow_outputs_ready_result(capsys) -> None:
    exit_code = guarded_main(
        [
            "workflow",
            "docs-update",
            "--target",
            "docs/README.md",
            "--actor-id",
            "simple-cli-test",
            "--json",
        ]
    )
    envelope = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["workflow"] == "docs_update"
    assert envelope["payload"]["ready_count"] == 3


def test_simple_cli_lists_workflow_templates_as_readable_catalog(capsys) -> None:
    exit_code = guarded_main(["workflows"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Common workflows:" in output
    assert "docs-update" in output
    assert "mullu workflow docs-update --target <target>" in output
    assert "support-notice" in output


def test_simple_cli_start_outputs_onboarding_path(capsys) -> None:
    exit_code = guarded_main(["start"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mullu simple mode" in output
    assert "Recommended path:" in output
    assert "mullu workflows" in output
    assert "mullu workflow docs-update --target docs/README.md" in output


def test_simple_platform_api_projects_ready_check() -> None:
    envelope = SimplePlatformRuntime().check_action(
        {
            "goal": "Review docs",
            "action": "view",
            "target": "docs/README.md",
            "allowed_area": "docs/**",
            "actor_id": "simple-api-test",
        }
    )
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["payload"]["check"]["proof_stamp_ref"].startswith("proof-")
    assert payload["error"] == ""


def test_simple_platform_api_projects_template_backed_task() -> None:
    envelope = SimplePlatformRuntime().check_task(
        {
            "task": "review_docs",
            "target": "docs/README.md",
            "actor_id": "simple-api-test",
        }
    )
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["payload"]["check"]["outcome"] == "ready"


def test_simple_platform_api_projects_template_backed_workflow() -> None:
    envelope = SimplePlatformRuntime().check_workflow(
        {
            "workflow": "docs_update",
            "target": "docs/README.md",
            "actor_id": "simple-api-test",
        }
    )
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["payload"]["workflow"]["outcome"] == "ready"
    assert payload["payload"]["workflow"]["ready_count"] == 3


def test_simple_platform_api_rejects_invalid_workflow() -> None:
    envelope = SimplePlatformRuntime().check_workflow({"workflow": "unknown-workflow", "target": "docs/README.md"})
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is False
    assert payload["status"] == "rejected"
    assert payload["payload"] == {}
    assert "workflow must be one of" in payload["error"]


def test_simple_platform_api_returns_start_guide() -> None:
    payload = SimplePlatformRuntime().start_guide().to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "listed"
    assert payload["payload"]["guide"]["execution_allowed"] is False
    assert payload["payload"]["guide"]["recommended_path"][0]["step"] == "choose"


def test_simple_platform_api_rejects_invalid_request() -> None:
    envelope = SimplePlatformRuntime().check_action({"goal": "", "action": "view"})
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is False
    assert payload["status"] == "rejected"
    assert payload["payload"] == {}
    assert payload["error"]


def test_simple_platform_api_rejects_non_text_request_fields() -> None:
    runtime = SimplePlatformRuntime()

    action_payload = runtime.check_action({"goal": 1001, "action": "view"}).to_dict()
    task_payload = runtime.check_task(
        {"task": "review_docs", "target": "docs/README.md", "actor_id": False}
    ).to_dict()
    workflow_payload = runtime.check_workflow(
        {"workflow": "docs_update", "target": 1001}
    ).to_dict()

    assert action_payload["governed"] is True
    assert action_payload["ok"] is False
    assert "goal must be text" in action_payload["error"]
    assert task_payload["ok"] is False
    assert "actor_id must be text" in task_payload["error"]
    assert workflow_payload["ok"] is False
    assert "target must be text" in workflow_payload["error"]


def test_simple_platform_api_rejects_unknown_request_fields_without_reflection() -> None:
    runtime = SimplePlatformRuntime()

    action_payload = runtime.check_action(
        {
            "goal": "Review docs",
            "action": "view",
            "target": "docs/README.md",
            "allowed_area": "docs/**",
            "scope_override": True,
        }
    ).to_dict()
    task_payload = runtime.check_task(
        {"task": "review_docs", "target": "docs/README.md", "execute_now": True}
    ).to_dict()
    workflow_payload = runtime.check_workflow(
        {"workflow": "docs_update", "target": "docs/README.md", "approval_override": "force"}
    ).to_dict()

    assert action_payload["ok"] is False
    assert action_payload["status"] == "rejected"
    assert action_payload["payload"] == {}
    assert action_payload["error"] == "request contains unsupported fields"
    assert "scope_override" not in action_payload["error"]
    assert task_payload["ok"] is False
    assert task_payload["error"] == "request contains unsupported fields"
    assert "execute_now" not in task_payload["error"]
    assert workflow_payload["ok"] is False
    assert workflow_payload["error"] == "request contains unsupported fields"
    assert "approval_override" not in workflow_payload["error"]


def test_simple_platform_api_lists_action_menu() -> None:
    payload = SimplePlatformRuntime().action_menu().to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "listed"
    assert payload["payload"]["actions"][0]["action"] == "view"
    assert payload["payload"]["tasks"][0]["task"] == "review_docs"
    assert payload["payload"]["tasks"][2]["default_target"] == "support@mullusi.com"
    assert payload["payload"]["outcomes"][2]["label"] == "Blocked"
    assert payload["payload"]["workflows"][0]["workflow"] == "docs_update"


def test_simple_platform_console_entry_point_is_guarded() -> None:
    metadata = tomllib.loads((ROOT / "mcoi" / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["mullu"] == "mcoi_runtime.core.simple_cli:guarded_main"
    assert metadata["project"]["scripts"]["mcoi"] == "mcoi_runtime.app.cli:main"
    assert metadata["project"]["scripts"]["mcoi-swarm"] == "mcoi_runtime.swarm.cli:guarded_main"
    assert metadata["project"]["scripts"]["mcoi-notes"] == "mcoi_runtime.core.note_memory_cli:guarded_main"
