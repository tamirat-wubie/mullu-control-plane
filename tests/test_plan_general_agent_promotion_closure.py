"""Tests for full general-agent promotion closure planning.

Purpose: prove adapter and deployment closure plans aggregate into one
operator-facing production promotion plan.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_general_agent_promotion_closure.
Invariants:
  - Aggregation preserves source blockers.
  - Approval-required source actions remain approval-required.
  - Source plan type is explicit on every action.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_general_agent_promotion_closure import (  # noqa: E402
    main,
    plan_general_agent_promotion_closure,
    write_general_agent_promotion_closure_plan,
)


def test_promotion_closure_plan_combines_adapter_and_deployment_actions(tmp_path: Path) -> None:
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)

    plan = plan_general_agent_promotion_closure(
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
    )
    source_types = {action["source_plan_type"] for action in plan.actions}

    assert plan.source_ready is False
    assert plan.plan_id.startswith("general-agent-promotion-closure-plan-")
    assert plan.plan_id != "general-agent-promotion-closure-plan-03"
    assert plan.readiness_level == "pilot-governed-core"
    assert plan.total_action_count == 3
    assert plan.approval_required_action_count == 2
    assert plan.source_plans == (
        "capability_adapter_closure_plan.json",
        "deployment_publication_closure_plan.json",
    )
    assert str(tmp_path) not in json.dumps(plan.as_dict(), sort_keys=True)
    assert source_types == {"adapter", "deployment"}
    assert "adapter_evidence_not_closed" in plan.blockers
    assert "production_health_not_declared" in plan.blockers


def test_promotion_closure_plan_preserves_deployment_runtime_input_actions(tmp_path: Path) -> None:
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)
    deployment_plan = json.loads(deployment_plan_path.read_text(encoding="utf-8"))
    deployment_plan["blockers"] = [
        "deployment_witness_secret_missing",
        "deployment_dns_not_verified",
    ]
    deployment_plan["actions"] = [
        {
            "action_id": "provision-deployment-witness-secret",
            "blocker": "deployment_witness_secret_missing",
            "action_type": "secret-binding",
            "command": (
                "Provision GitHub Actions secret MULLU_DEPLOYMENT_WITNESS_SECRET; "
                "do not print or serialize the secret value."
            ),
            "evidence_required": [
                "gh_secret_list_presence:MULLU_DEPLOYMENT_WITNESS_SECRET",
                "deployment_witness_preflight",
            ],
            "approval_required": True,
        },
        {
            "action_id": "verify-gateway-dns",
            "blocker": "deployment_dns_not_verified",
            "action_type": "dns-verification",
            "command": "Resolve $MULLU_GATEWAY_HOST and rerun deployment witness preflight.",
            "evidence_required": [
                "dns_resolution_receipt",
                "deployment_witness_preflight",
            ],
            "approval_required": True,
        },
    ]
    deployment_plan_path.write_text(json.dumps(deployment_plan), encoding="utf-8")

    plan = plan_general_agent_promotion_closure(
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
    )
    deployment_actions = {
        action["action_id"]: action
        for action in plan.actions
        if action["source_plan_type"] == "deployment"
    }

    assert plan.total_action_count == 3
    assert plan.approval_required_action_count == 3
    assert deployment_actions["provision-deployment-witness-secret"]["action_type"] == "secret-binding"
    assert deployment_actions["verify-gateway-dns"]["action_type"] == "dns-verification"
    assert "deployment_witness_secret_missing" in plan.blockers
    assert "deployment_dns_not_verified" in plan.blockers


def test_promotion_closure_plan_marks_browser_runner_environment(tmp_path: Path) -> None:
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)
    adapter_plan = json.loads(adapter_plan_path.read_text(encoding="utf-8"))
    adapter_plan["blockers"] = ["browser_live_evidence_missing"]
    adapter_plan["actions"] = [
        {
            "action_id": "browser-playwright-browser-live-evidence-missing",
            "blocker": "browser_live_evidence_missing",
            "action_type": "live-receipt",
            "verification_command": "python scripts/collect_capability_adapter_evidence.py",
            "receipt_validator": "adapter_evidence.browser.playwright.receipt_check.passed",
            "approval_required": False,
        },
    ]
    adapter_plan_path.write_text(json.dumps(adapter_plan), encoding="utf-8")

    plan = plan_general_agent_promotion_closure(
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
        platform_system=lambda: "Windows",
    )
    browser_action = next(
        action for action in plan.actions if action["blocker"] == "browser_live_evidence_missing"
    )
    execution_environment = browser_action["execution_environment"]

    assert execution_environment["required_host_os"] == "Linux"
    assert execution_environment["current_host_os"] == "Windows"
    assert execution_environment["current_environment_ready"] is False
    assert execution_environment["blocker_if_unmet"] == "browser_sandbox_runner_linux_only"
    assert "rootless_docker" in execution_environment["requirements"]


def test_promotion_closure_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)
    output_path = tmp_path / "general_agent_promotion_closure_plan.json"
    plan = plan_general_agent_promotion_closure(
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
    )

    written = write_general_agent_promotion_closure_plan(plan, output_path)
    exit_code = main(
        [
            "--readiness",
            str(readiness_path),
            "--adapter-plan",
            str(adapter_plan_path),
            "--deployment-plan",
            str(deployment_plan_path),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["total_action_count"] == 3
    assert stdout_payload["plan_id"] == payload["plan_id"]
    assert payload["approval_required_action_count"] == 2


def test_promotion_closure_plan_rejects_nonfinite_source_json(tmp_path: Path) -> None:
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)
    readiness_path.write_text(
        '{"ready": false, "readiness_level": "pilot-governed-core", "score": Infinity}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        plan_general_agent_promotion_closure(
            readiness_path=readiness_path,
            adapter_plan_path=adapter_plan_path,
            deployment_plan_path=deployment_plan_path,
        )

    assert "promotion readiness JSON parse failed" in str(excinfo.value)
    assert "Infinity" not in str(excinfo.value)
    assert adapter_plan_path.exists()


def _write_source_plans(tmp_path: Path) -> tuple[Path, Path, Path]:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    adapter_plan_path = tmp_path / "capability_adapter_closure_plan.json"
    deployment_plan_path = tmp_path / "deployment_publication_closure_plan.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "readiness_level": "pilot-governed-core",
                "blockers": [
                    "adapter_evidence_not_closed",
                    "deployment_witness_not_published",
                    "production_health_not_declared",
                ],
            }
        ),
        encoding="utf-8",
    )
    adapter_plan_path.write_text(
        json.dumps(
            {
                "blockers": ["voice_dependency_missing:OPENAI_API_KEY"],
                "actions": [
                    {
                        "action_id": "voice-secret",
                        "blocker": "voice_dependency_missing:OPENAI_API_KEY",
                        "approval_required": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    deployment_plan_path.write_text(
        json.dumps(
            {
                "blockers": [
                    "deployment_witness_not_published",
                    "production_health_not_declared",
                ],
                "actions": [
                    {
                        "action_id": "publish-witness",
                        "blocker": "deployment_witness_not_published",
                        "approval_required": True,
                    },
                    {
                        "action_id": "declare-health",
                        "blocker": "production_health_not_declared",
                        "approval_required": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return readiness_path, adapter_plan_path, deployment_plan_path
