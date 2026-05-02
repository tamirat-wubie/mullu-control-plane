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
    assert source_types == {"adapter", "deployment"}
    assert "adapter_evidence_not_closed" in plan.blockers
    assert "production_health_not_declared" in plan.blockers


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
