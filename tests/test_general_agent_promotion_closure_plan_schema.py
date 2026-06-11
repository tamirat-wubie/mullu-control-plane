"""Tests for aggregate promotion closure plan schema validation.

Purpose: prove the operator-facing closure plan is governed by a public schema
and semantic count checks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_general_agent_promotion_closure_plan_schema and
schemas/general_agent_promotion_closure_plan.schema.json.
Invariants:
  - Valid aggregate plans pass schema and count validation.
  - Missing action source tags fail closed.
  - Count drift fails closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_general_agent_promotion_closure_plan_schema import (  # noqa: E402
    main,
    validate_general_agent_promotion_closure_plan_schema,
    write_general_agent_promotion_closure_plan_schema_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "general_agent_promotion_closure_plan.schema.json"


def test_promotion_closure_plan_schema_accepts_valid_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.plan_path == "general_agent_promotion_closure_plan.json"
    assert validation.schema_path == "schemas/general_agent_promotion_closure_plan.schema.json"
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1
    assert validation.source_plan_types == ("adapter", "deployment")
    assert tmp_path.name not in json.dumps(validation.as_dict(), sort_keys=True)


def test_promotion_closure_plan_schema_accepts_portfolio_source_actions(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    payload["source_plans"].append(".change_assurance/capability_improvement_portfolio.json")  # type: ignore[index, union-attr]
    payload["actions"].append(  # type: ignore[index, union-attr]
        {
            "action_id": "capability-improvement-browser-open-0123456789abcdef",
            "action_type": "capability-improvement",
            "blocker": "capability_improvement_required:browser.open",
            "command": "Review activation-blocked improvement plan.",
            "verification_command": "python -m pytest tests/test_gateway/test_autonomous_capability_upgrade.py -q",
            "receipt_validator": "capability_improvement_portfolio:portfolio-hash:plan-id",
            "evidence_required": ["capability_health:browser.open"],
            "risk_level": "critical",
            "approval_required": True,
            "source_plan_type": "portfolio",
        }
    )
    payload["total_action_count"] = 3
    payload["approval_required_action_count"] = 2
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 3
    assert validation.approval_required_action_count == 2
    assert validation.source_plan_types == ("adapter", "deployment", "portfolio")


def test_promotion_closure_plan_schema_accepts_portfolio_only_after_source_ready(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _portfolio_only_ready_plan()
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 1
    assert validation.approval_required_action_count == 1
    assert validation.source_plan_types == ("portfolio",)


def test_promotion_closure_plan_schema_accepts_execution_environment(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    payload["actions"][0]["execution_environment"] = {  # type: ignore[index]
        "required_host_os": "Linux",
        "current_host_os": "Windows",
        "current_environment_ready": False,
        "blocker_if_unmet": "browser_sandbox_runner_linux_only",
        "requirements": ["linux_host", "rootless_docker"],
    }
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1


def test_promotion_closure_plan_schema_rejects_missing_source_tag(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    del payload["actions"][0]["source_plan_type"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.action_count == 2
    assert any("source_plan_type" in error for error in validation.errors)
    assert any("adapter blockers" in error for error in validation.errors)


def test_promotion_closure_plan_schema_bounds_malformed_json_detail(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    plan_path.write_text('{"secret": "secret-promotion-plan-token",', encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "promotion closure plan JSON parse failed" in validation.errors
    assert all("secret-promotion-plan-token" not in error for error in validation.errors)


def test_promotion_closure_plan_schema_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    plan_path.write_text('{"plan_id": "general-agent-promotion-closure-plan-x", "score": Infinity}', encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "promotion closure plan JSON parse failed" in validation.errors
    assert "Infinity" not in serialized_errors


def test_promotion_closure_plan_schema_rejects_count_drift(tmp_path: Path) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    payload["total_action_count"] = 99
    payload["approval_required_action_count"] = 99
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1
    assert "total_action_count does not match actions length" in validation.errors
    assert "approval_required_action_count does not match actions" in validation.errors


def test_promotion_closure_plan_schema_rejects_adapter_without_proof_contract(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    del payload["actions"][0]["verification_command"]
    del payload["actions"][0]["receipt_validator"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "adapter action 0 missing verification_command" in validation.errors
    assert "adapter action 0 missing receipt_validator" in validation.errors


def test_promotion_closure_plan_schema_rejects_portfolio_without_approval(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    payload = _valid_plan()
    payload["actions"].append(  # type: ignore[index, union-attr]
        {
            "action_id": "capability-improvement-browser-open-0123456789abcdef",
            "action_type": "capability-improvement",
            "blocker": "capability_improvement_required:browser.open",
            "command": "Review activation-blocked improvement plan.",
            "verification_command": "python -m pytest tests/test_gateway/test_autonomous_capability_upgrade.py -q",
            "receipt_validator": "capability_improvement_portfolio:portfolio-hash:plan-id",
            "risk_level": "critical",
            "approval_required": False,
            "source_plan_type": "portfolio",
        }
    )
    payload["total_action_count"] = 3
    payload["approval_required_action_count"] = 1
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "portfolio action 2 must require approval" in validation.errors


def test_promotion_closure_plan_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    plan_path = tmp_path / "general_agent_promotion_closure_plan.json"
    output_path = tmp_path / "schema_validation.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")
    validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_general_agent_promotion_closure_plan_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--plan",
            str(plan_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["source_plan_types"] == ["adapter", "deployment"]
    assert payload["action_count"] == 2


def _valid_plan() -> dict[str, object]:
    return {
        "plan_id": "general-agent-promotion-closure-plan-0123456789abcdef",
        "readiness_level": "pilot-governed-core",
        "source_ready": False,
        "total_action_count": 2,
        "approval_required_action_count": 1,
        "source_plans": [
            ".change_assurance/capability_adapter_closure_plan.json",
            ".change_assurance/deployment_publication_closure_plan.json",
        ],
        "blockers": [
            "adapter_evidence_not_closed",
            "deployment_witness_not_published",
        ],
        "actions": [
            {
                "action_id": "voice-secret",
                "action_type": "credential",
                "adapter_id": "voice.openai",
                "blocker": "voice_dependency_missing:OPENAI_API_KEY",
                "command": "Bind governed voice secret.",
                "verification_command": "python scripts/collect_capability_adapter_evidence.py",
                "receipt_validator": "adapter_evidence.voice.openai.dependency.OPENAI_API_KEY",
                "evidence_required": ["secret_presence_attestation"],
                "risk_level": "high",
                "approval_required": True,
                "source_plan_type": "adapter",
            },
            {
                "action_id": "publish-witness",
                "action_type": "publish-witness",
                "blocker": "deployment_witness_not_published",
                "command": "Publish deployment witness after approval.",
                "evidence_required": ["deployment_witness.json"],
                "risk_level": "high",
                "approval_required": False,
                "source_plan_type": "deployment",
            },
        ],
    }


def _portfolio_only_ready_plan() -> dict[str, object]:
    return {
        "plan_id": "general-agent-promotion-closure-plan-fedcba9876543210",
        "readiness_level": "production-general-agent",
        "source_ready": True,
        "total_action_count": 1,
        "approval_required_action_count": 1,
        "source_plans": [
            ".change_assurance/capability_adapter_closure_plan.json",
            ".change_assurance/deployment_publication_closure_plan.json",
            ".change_assurance/capability_improvement_portfolio.json",
        ],
        "blockers": [],
        "actions": [
            {
                "action_id": "capability-improvement-financial-refund-0123456789abcdef",
                "action_type": "capability-improvement",
                "blocker": "capability_improvement_required:financial.refund",
                "command": "Review activation-blocked improvement plan.",
                "verification_command": "python -m pytest tests/test_gateway/test_autonomous_capability_upgrade.py -q",
                "receipt_validator": "capability_improvement_portfolio:portfolio-hash:plan-id",
                "evidence_required": ["capability_health:financial.refund"],
                "risk_level": "critical",
                "approval_required": True,
                "source_plan_type": "portfolio",
            }
        ],
    }
