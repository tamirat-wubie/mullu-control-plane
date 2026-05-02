"""Tests for aggregate promotion closure plan validation.

Purpose: prove the combined promotion closure plan cannot drift from source plans.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_general_agent_promotion_closure_plan.
Invariants:
  - Source action identity is preserved.
  - Approval counts are recomputed.
  - Strict CLI exits non-zero on drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_general_agent_promotion_closure_plan import (  # noqa: E402
    main,
    validate_general_agent_promotion_closure_plan,
    write_general_agent_promotion_closure_plan_validation,
)


def test_validate_promotion_closure_plan_accepts_matching_sources(tmp_path: Path) -> None:
    paths = _write_matching_artifacts(tmp_path)

    validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=paths["promotion"],
        readiness_path=paths["readiness"],
        adapter_plan_path=paths["adapter"],
        deployment_plan_path=paths["deployment"],
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.expected_action_count == 3
    assert validation.observed_action_count == 3
    assert validation.expected_approval_required_count == 2
    assert validation.observed_approval_required_count == 2


def test_validate_promotion_closure_plan_rejects_missing_source_action(tmp_path: Path) -> None:
    paths = _write_matching_artifacts(tmp_path)
    promotion = json.loads(paths["promotion"].read_text(encoding="utf-8"))
    promotion["actions"] = promotion["actions"][:-1]
    promotion["total_action_count"] = 2
    paths["promotion"].write_text(json.dumps(promotion), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=paths["promotion"],
        readiness_path=paths["readiness"],
        adapter_plan_path=paths["adapter"],
        deployment_plan_path=paths["deployment"],
    )

    assert validation.ok is False
    assert validation.expected_action_count == 3
    assert validation.observed_action_count == 2
    assert any("missing source actions" in error for error in validation.errors)


def test_validate_promotion_closure_plan_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    paths = _write_matching_artifacts(tmp_path)
    validation_output = tmp_path / "validation.json"
    validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=paths["promotion"],
        readiness_path=paths["readiness"],
        adapter_plan_path=paths["adapter"],
        deployment_plan_path=paths["deployment"],
    )

    written = write_general_agent_promotion_closure_plan_validation(validation, validation_output)
    exit_code = main(
        [
            "--plan",
            str(paths["promotion"]),
            "--readiness",
            str(paths["readiness"]),
            "--adapter-plan",
            str(paths["adapter"]),
            "--deployment-plan",
            str(paths["deployment"]),
            "--output",
            str(validation_output),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(validation_output.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == validation_output
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["ok"] is True


def _write_matching_artifacts(tmp_path: Path) -> dict[str, Path]:
    readiness = tmp_path / "general_agent_promotion_readiness.json"
    adapter = tmp_path / "capability_adapter_closure_plan.json"
    deployment = tmp_path / "deployment_publication_closure_plan.json"
    promotion = tmp_path / "general_agent_promotion_closure_plan.json"
    readiness.write_text(
        json.dumps(
            {
                "ready": False,
                "readiness_level": "pilot-governed-core",
                "blockers": ["adapter_evidence_not_closed"],
            }
        ),
        encoding="utf-8",
    )
    adapter.write_text(
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
    deployment.write_text(
        json.dumps(
            {
                "blockers": ["deployment_witness_not_published"],
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
    promotion.write_text(
        json.dumps(
            {
                "readiness_level": "pilot-governed-core",
                "source_ready": False,
                "total_action_count": 3,
                "approval_required_action_count": 2,
                "actions": [
                    {
                        "source_plan_type": "adapter",
                        "action_id": "voice-secret",
                        "blocker": "voice_dependency_missing:OPENAI_API_KEY",
                        "approval_required": True,
                    },
                    {
                        "source_plan_type": "deployment",
                        "action_id": "publish-witness",
                        "blocker": "deployment_witness_not_published",
                        "approval_required": True,
                    },
                    {
                        "source_plan_type": "deployment",
                        "action_id": "declare-health",
                        "blocker": "production_health_not_declared",
                        "approval_required": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return {
        "readiness": readiness,
        "adapter": adapter,
        "deployment": deployment,
        "promotion": promotion,
    }
