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

from mcoi_runtime.core.simple_cli import guarded_main
from mcoi_runtime.core.simple_platform import SimpleActionRequest, SimplePlatform
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


def test_simple_platform_api_rejects_invalid_request() -> None:
    envelope = SimplePlatformRuntime().check_action({"goal": "", "action": "view"})
    payload = envelope.to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is False
    assert payload["status"] == "rejected"
    assert payload["payload"] == {}
    assert payload["error"]


def test_simple_platform_api_lists_action_menu() -> None:
    payload = SimplePlatformRuntime().action_menu().to_dict()

    assert payload["governed"] is True
    assert payload["ok"] is True
    assert payload["status"] == "listed"
    assert payload["payload"]["actions"][0]["action"] == "view"
    assert payload["payload"]["outcomes"][2]["label"] == "Blocked"


def test_simple_platform_console_entry_point_is_guarded() -> None:
    metadata = tomllib.loads((ROOT / "mcoi" / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["mullu"] == "mcoi_runtime.core.simple_cli:guarded_main"
    assert metadata["project"]["scripts"]["mcoi-mvk"] == "mcoi_runtime.core.mvk_cli:guarded_main"
    assert metadata["project"]["scripts"]["mcoi-notes"] == "mcoi_runtime.core.note_memory_cli:guarded_main"
