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
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1
    assert validation.source_plan_types == ("adapter", "deployment")


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
    assert any("adapter and deployment source actions" in error for error in validation.errors)


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
