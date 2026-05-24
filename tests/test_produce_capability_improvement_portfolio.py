"""Tests for capability improvement portfolio witness production.

Purpose: prove governed capability records can produce a schema-valid,
activation-blocked improvement portfolio and feed promotion closure planning.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_capability_improvement_portfolio and promotion
closure planner/validator scripts.
Invariants:
  - Produced portfolios are schema-valid before they are written.
  - Portfolio actions remain approval-required and activation-blocked.
  - Promotion closure validation consumes the produced witness explicitly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_general_agent_promotion_closure import (  # noqa: E402
    plan_general_agent_promotion_closure,
    write_general_agent_promotion_closure_plan,
)
from scripts.produce_capability_improvement_portfolio import (  # noqa: E402
    DEFAULT_GENERATED_AT,
    main as produce_portfolio_main,
    produce_capability_improvement_portfolio,
)
from scripts.validate_general_agent_promotion_closure_plan import (  # noqa: E402
    validate_general_agent_promotion_closure_plan,
)


def test_produce_capability_improvement_portfolio_writes_schema_valid_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "capability_improvement_portfolio.json"

    result = produce_capability_improvement_portfolio(
        output_path=output_path,
        generated_at=DEFAULT_GENERATED_AT,
        domain="browser",
        candidate_limit=3,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.plan_count == 3
    assert payload["portfolio_id"] == result.portfolio_id
    assert payload["activation_blocked"] is True
    assert payload["operator_review_required"] is True
    assert payload["metadata"]["selected_candidate_count"] == 3
    assert "production_certification_missing" in payload["systemic_weakness_codes"]
    assert all(capability_id.startswith("browser.") for capability_id in payload["prioritized_capability_ids"])


def test_produced_portfolio_feeds_promotion_closure_plan(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "capability_improvement_portfolio.json"
    portfolio_result = produce_capability_improvement_portfolio(
        output_path=portfolio_path,
        generated_at=DEFAULT_GENERATED_AT,
        domain="browser",
        candidate_limit=2,
    )
    readiness_path, adapter_plan_path, deployment_plan_path = _write_source_plans(tmp_path)
    promotion_plan_path = tmp_path / "general_agent_promotion_closure_plan.json"

    plan = plan_general_agent_promotion_closure(
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
        portfolio_plan_path=portfolio_path,
    )
    write_general_agent_promotion_closure_plan(plan, promotion_plan_path)
    validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=promotion_plan_path,
        readiness_path=readiness_path,
        adapter_plan_path=adapter_plan_path,
        deployment_plan_path=deployment_plan_path,
        portfolio_plan_path=portfolio_path,
    )
    portfolio_actions = [action for action in plan.actions if action["source_plan_type"] == "portfolio"]

    assert portfolio_result.passed is True
    assert plan.total_action_count == 5
    assert plan.approval_required_action_count == 4
    assert len(portfolio_actions) == 2
    assert all(action["approval_required"] is True for action in portfolio_actions)
    assert all(action["receipt_validator"].startswith("capability_improvement_portfolio:") for action in portfolio_actions)
    assert validation.ok is True
    assert validation.expected_action_count == plan.total_action_count
    assert validation.observed_action_count == plan.total_action_count


def test_produce_capability_improvement_portfolio_cli_outputs_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "capability_improvement_portfolio.json"

    exit_code = produce_portfolio_main(
        [
            "--output",
            str(output_path),
            "--domain",
            "browser",
            "--candidate-limit",
            "2",
            "--json",
            "--strict",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["status"] == "passed"
    assert payload["plan_count"] == 2
    assert len(payload["prioritized_capability_ids"]) == 2


def _write_source_plans(tmp_path: Path) -> tuple[Path, Path, Path]:
    readiness_path = tmp_path / "readiness.json"
    adapter_plan_path = tmp_path / "adapter_closure_plan.json"
    deployment_plan_path = tmp_path / "deployment_publication_closure_plan.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready": False,
                "readiness_level": "pilot-governed-core",
                "blockers": ["promotion_requires_closure"],
            }
        ),
        encoding="utf-8",
    )
    adapter_plan_path.write_text(
        json.dumps(
            {
                "plan_id": "capability-adapter-closure-plan-test",
                "blockers": ["voice_adapter_live_receipt_missing"],
                "actions": [
                    {
                        "action_id": "voice-secret",
                        "blocker": "voice_adapter_live_receipt_missing",
                        "verification_command": "python scripts/collect_capability_adapter_evidence.py",
                        "receipt_validator": "adapter_evidence.voice.openai.dependency.OPENAI_API_KEY",
                        "approval_required": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    deployment_plan_path.write_text(
        json.dumps(
            {
                "plan_id": "deployment-publication-closure-plan-test",
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
