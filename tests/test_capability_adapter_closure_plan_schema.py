"""Tests for capability adapter closure plan schema validation.

Purpose: prove adapter source closure plans have a public schema and semantic
proof-contract gate before aggregate promotion planning.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_capability_adapter_closure_plan_schema and
schemas/capability_adapter_closure_plan.schema.json.
Invariants:
  - Valid adapter closure plans pass schema and semantic validation.
  - Action count drift fails closed.
  - Missing proof contracts fail closed.
  - Blockers without actions fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_capability_adapter_closure_plan_schema import (  # noqa: E402
    main,
    validate_capability_adapter_closure_plan_schema,
    write_capability_adapter_closure_plan_schema_validation,
)

SCHEMA_PATH = _ROOT / "schemas" / "capability_adapter_closure_plan.schema.json"


def test_adapter_closure_plan_schema_accepts_valid_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "capability_adapter_closure_plan.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")

    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.action_count == 2
    assert validation.approval_required_action_count == 1
    assert validation.blocker_count == 2


def test_adapter_closure_plan_schema_rejects_count_drift(tmp_path: Path) -> None:
    plan_path = tmp_path / "capability_adapter_closure_plan.json"
    payload = _valid_plan()
    payload["action_count"] = 99
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.action_count == 2
    assert "action_count does not match actions length" in validation.errors


def test_adapter_closure_plan_schema_rejects_missing_proof_contract(tmp_path: Path) -> None:
    plan_path = tmp_path / "capability_adapter_closure_plan.json"
    payload = _valid_plan()
    del payload["actions"][0]["verification_command"]
    del payload["actions"][0]["receipt_validator"]
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "adapter action 0 missing verification_command" in validation.errors
    assert "adapter action 0 missing receipt_validator" in validation.errors


def test_adapter_closure_plan_schema_rejects_uncovered_blocker(tmp_path: Path) -> None:
    plan_path = tmp_path / "capability_adapter_closure_plan.json"
    payload = _valid_plan()
    payload["blockers"].append("voice_live_evidence_missing")
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("voice_live_evidence_missing" in error for error in validation.errors)
    assert any("missing closure actions" in error for error in validation.errors)


def test_adapter_closure_plan_schema_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    plan_path = tmp_path / "capability_adapter_closure_plan.json"
    output_path = tmp_path / "schema_validation.json"
    plan_path.write_text(json.dumps(_valid_plan()), encoding="utf-8")
    validation = validate_capability_adapter_closure_plan_schema(
        plan_path=plan_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_capability_adapter_closure_plan_schema_validation(
        validation,
        output_path,
    )
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
    assert stdout_payload["action_count"] == 2


def _valid_plan() -> dict[str, object]:
    return {
        "plan_id": "capability-adapter-closure-plan-0123456789abcdef",
        "source_evidence_path": ".change_assurance/capability_adapter_evidence.json",
        "source_ready": False,
        "action_count": 2,
        "blockers": [
            "browser_live_evidence_missing",
            "voice_dependency_missing:OPENAI_API_KEY",
        ],
        "actions": [
            {
                "action_id": "browser-playwright-browser-live-evidence-missing",
                "adapter_id": "browser.playwright",
                "blocker": "browser_live_evidence_missing",
                "action_type": "live-receipt",
                "command": "python scripts/produce_capability_adapter_live_receipts.py --target browser --strict",
                "verification_command": "python scripts/collect_capability_adapter_evidence.py --output .change_assurance/capability_adapter_evidence.json",
                "receipt_validator": "adapter_evidence.browser.playwright.receipt_check.passed",
                "evidence_required": ["browser_live_receipt.json"],
                "risk_level": "medium",
                "approval_required": False,
            },
            {
                "action_id": "voice-openai-voice-dependency-missing-OPENAI-API-KEY",
                "adapter_id": "voice.openai",
                "blocker": "voice_dependency_missing:OPENAI_API_KEY",
                "action_type": "credential",
                "command": "Set OPENAI_API_KEY only in the governed voice-worker secret store.",
                "verification_command": "python scripts/collect_capability_adapter_evidence.py --output .change_assurance/capability_adapter_evidence.json",
                "receipt_validator": "adapter_evidence.voice.openai.dependency.OPENAI_API_KEY",
                "evidence_required": ["secret_presence_attestation"],
                "risk_level": "high",
                "approval_required": True,
            },
        ],
    }
