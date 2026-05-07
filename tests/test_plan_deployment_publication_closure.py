"""Tests for deployment publication closure planning.

Purpose: prove deployment promotion blockers become explicit publication actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_deployment_publication_closure.
Invariants:
  - Planning does not mutate deployment status.
  - Publication and health actions require approval.
  - Unknown deployment blockers remain manual-review items.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_deployment_publication_closure import (  # noqa: E402
    main,
    plan_deployment_publication_closure,
    write_deployment_publication_closure_plan,
)


def test_deployment_closure_plan_maps_publication_blockers(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    deployment_status_path = tmp_path / "DEPLOYMENT_STATUS.md"
    readiness_path.write_text(json.dumps(_blocked_readiness()), encoding="utf-8")
    deployment_status_path.write_text("**Deployment witness state:** `not-published`\n", encoding="utf-8")

    plan = plan_deployment_publication_closure(readiness_path, deployment_status_path)
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.source_ready is False
    assert plan.plan_id.startswith("deployment-publication-closure-plan-")
    assert plan.plan_id != "deployment-publication-closure-plan-02"
    assert plan.action_count == 2
    assert plan.blockers == ("deployment_witness_not_published", "production_health_not_declared")
    assert actions_by_blocker["deployment_witness_not_published"].approval_required is True
    assert actions_by_blocker["deployment_witness_not_published"].risk_level == "high"
    assert "publish_gateway_publication.py" in actions_by_blocker["deployment_witness_not_published"].command
    assert "deployment_witness.json" in actions_by_blocker["production_health_not_declared"].evidence_required
    assert "DEPLOYMENT_STATUS.md" in actions_by_blocker["production_health_not_declared"].command


def test_deployment_closure_plan_preserves_unknown_deployment_blocker(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    readiness_path.write_text(
        json.dumps({"ready": False, "blockers": ["deployment_dns_not_verified"]}),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(readiness_path)
    action = plan.actions[0]

    assert plan.action_count == 1
    assert action.blocker == "deployment_dns_not_verified"
    assert action.action_type == "manual-review"
    assert action.approval_required is True


def test_deployment_closure_plan_maps_responsibility_debt_blockers(tmp_path: Path) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "blockers": [
                    "deployment_runtime_responsibility_debt_present",
                    "deployment_authority_responsibility_debt_present",
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_deployment_publication_closure(readiness_path)
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.action_count == 2
    assert actions_by_blocker[
        "deployment_runtime_responsibility_debt_present"
    ].action_type == "responsibility-debt-closure"
    assert actions_by_blocker[
        "deployment_authority_responsibility_debt_present"
    ].approval_required is True
    assert "/authority/responsibility" in actions_by_blocker[
        "deployment_authority_responsibility_debt_present"
    ].command


def test_deployment_closure_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    readiness_path = tmp_path / "general_agent_promotion_readiness.json"
    output_path = tmp_path / "deployment_publication_closure_plan.json"
    readiness_path.write_text(json.dumps(_blocked_readiness()), encoding="utf-8")
    plan = plan_deployment_publication_closure(readiness_path)

    written = write_deployment_publication_closure_plan(plan, output_path)
    exit_code = main(["--readiness", str(readiness_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["action_count"] == 2
    assert stdout_payload["plan_id"] == payload["plan_id"]
    assert "production_health_not_declared" in payload["blockers"]


def _blocked_readiness() -> dict[str, object]:
    return {
        "ready": False,
        "blockers": [
            "adapter_evidence_not_closed",
            "deployment_witness_not_published",
            "production_health_not_declared",
        ],
    }
