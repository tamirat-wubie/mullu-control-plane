"""Tests for the general-agent promotion closure chain runner.

Purpose: prove the default promotion artifact chain can be produced and
validated from explicit source evidence without test-only fixture shortcuts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.run_general_agent_promotion_closure_chain.
Invariants:
  - Readiness blockers do not hide schema or drift failures.
  - Portfolio source actions are included only when requested.
  - Strict mode fails validation errors, while require-ready gates promotion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.run_general_agent_promotion_closure_chain import (  # noqa: E402
    main,
    run_general_agent_promotion_closure_chain,
)


def test_promotion_closure_chain_writes_valid_portfolio_backed_artifacts(tmp_path: Path) -> None:
    adapter_evidence_path = _write_adapter_evidence(tmp_path)
    output_dir = tmp_path / "chain"

    run = run_general_agent_promotion_closure_chain(
        output_dir=output_dir,
        adapter_evidence_path=adapter_evidence_path,
        portfolio_domain="browser",
        portfolio_candidate_limit=2,
    )
    promotion_plan = _load_json(output_dir / "general_agent_promotion_closure_plan.json")
    schema_validation = _load_json(output_dir / "general_agent_promotion_closure_plan_schema_validation.json")
    drift_validation = _load_json(output_dir / "general_agent_promotion_closure_plan_validation.json")
    live_evidence_queue = _load_json(output_dir / "general_agent_promotion_live_evidence_queue.json")
    terminal_gate = _load_json(output_dir / "general_agent_promotion_terminal_certificate_gate.json")
    terminal_candidates = _load_json(output_dir / "general_agent_promotion_terminal_certificate_candidates.json")
    terminal_evidence = _load_json(output_dir / "general_agent_promotion_terminal_evidence_reconciliation.json")
    terminal_minting_gate = _load_json(output_dir / "general_agent_promotion_terminal_minting_gate.json")
    portfolio = _load_json(output_dir / "capability_improvement_portfolio.json")
    source_plan_types = {action["source_plan_type"] for action in promotion_plan["actions"]}

    assert run.passed is True
    assert run.status == "passed_blocked"
    assert run.artifact_valid is True
    assert run.promotion_ready is False
    assert run.readiness_level == "pilot-governed-core"
    assert run.portfolio_plan_count == 2
    assert run.total_action_count == promotion_plan["total_action_count"]
    assert run.approval_required_action_count == promotion_plan["approval_required_action_count"]
    assert run.live_evidence_queue_ready is False
    assert run.live_evidence_runnable_action_count == live_evidence_queue["runnable_action_count"]
    assert run.live_evidence_blocked_action_count == live_evidence_queue["blocked_action_count"]
    assert run.terminal_certificate_gate_ready is False
    assert run.terminal_certificate_admitted_action_count == terminal_gate["admitted_action_count"]
    assert run.terminal_certificate_blocked_action_count == terminal_gate["blocked_action_count"]
    assert run.terminal_certificate_candidate_count == terminal_candidates["candidate_count"]
    assert run.terminal_certificate_minting_ready is False
    assert run.terminal_evidence_reconciled_candidate_count == terminal_evidence["reconciled_candidate_count"]
    assert run.terminal_evidence_blocked_candidate_count == terminal_evidence["blocked_candidate_count"]
    assert run.terminal_minting_gate_admitted_candidate_count == terminal_minting_gate["admitted_candidate_count"]
    assert run.terminal_minting_gate_blocked_candidate_count == terminal_minting_gate["blocked_candidate_count"]
    assert run.validation_errors == ()
    assert "portfolio" in source_plan_types
    assert "adapter" in source_plan_types
    assert schema_validation["ok"] is True
    assert drift_validation["ok"] is True
    assert live_evidence_queue["metadata"]["queue_is_not_execution"] is True
    assert terminal_gate["metadata"]["gate_is_not_execution"] is True
    assert terminal_candidates["metadata"]["candidate_plan_is_not_execution"] is True
    assert terminal_candidates["metadata"]["terminal_certificates_minted"] is False
    assert terminal_evidence["metadata"]["reconciliation_is_not_execution"] is True
    assert terminal_evidence["metadata"]["terminal_certificates_minted"] is False
    assert terminal_minting_gate["metadata"]["minting_gate_is_not_execution"] is True
    assert terminal_minting_gate["metadata"]["terminal_certificates_minted"] is False
    assert terminal_minting_gate["authority_ref_present"] is False
    assert portfolio["metadata"]["selected_candidate_count"] == 2
    assert run.output_dir == "chain"
    assert str(tmp_path) not in json.dumps(run.as_dict(), sort_keys=True)
    assert tmp_path.name not in json.dumps(run.as_dict(), sort_keys=True)
    assert all((output_dir / path).exists() for path in run.artifacts.values())
    generated_payloads = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.glob("*.json"))
    assert str(tmp_path) not in generated_payloads
    assert tmp_path.name not in generated_payloads


def test_promotion_closure_chain_can_skip_portfolio(tmp_path: Path) -> None:
    adapter_evidence_path = _write_adapter_evidence(tmp_path)
    output_dir = tmp_path / "chain"

    run = run_general_agent_promotion_closure_chain(
        output_dir=output_dir,
        adapter_evidence_path=adapter_evidence_path,
        include_portfolio=False,
    )
    promotion_plan = _load_json(output_dir / "general_agent_promotion_closure_plan.json")
    source_plan_types = {action["source_plan_type"] for action in promotion_plan["actions"]}

    assert run.passed is True
    assert run.include_portfolio is False
    assert run.portfolio_plan_count == 0
    assert "portfolio" not in run.artifacts
    assert "terminal_certificate_gate" in run.artifacts
    assert "terminal_certificate_candidates" in run.artifacts
    assert "terminal_evidence_reconciliation" in run.artifacts
    assert "terminal_minting_gate" in run.artifacts
    assert "portfolio" not in source_plan_types
    assert source_plan_types == {"adapter", "deployment"}


def test_promotion_closure_chain_cli_strict_and_require_ready(tmp_path: Path, capsys) -> None:
    adapter_evidence_path = _write_adapter_evidence(tmp_path)
    output_dir = tmp_path / "chain"

    strict_exit_code = main(
        [
            "--output-dir",
            str(output_dir),
            "--adapter-evidence",
            str(adapter_evidence_path),
            "--portfolio-domain",
            "browser",
            "--portfolio-candidate-limit",
            "2",
            "--json",
            "--strict",
        ]
    )
    strict_payload = json.loads(capsys.readouterr().out)
    require_ready_exit_code = main(
        [
            "--output-dir",
            str(output_dir),
            "--adapter-evidence",
            str(adapter_evidence_path),
            "--portfolio-domain",
            "browser",
            "--portfolio-candidate-limit",
            "2",
            "--json",
            "--strict",
            "--require-ready",
        ]
    )
    require_ready_payload = json.loads(capsys.readouterr().out)

    assert strict_exit_code == 0
    assert strict_payload["artifact_valid"] is True
    assert strict_payload["promotion_ready"] is False
    assert strict_payload["status"] == "passed_blocked"
    assert strict_payload["terminal_certificate_gate_ready"] is False
    assert strict_payload["terminal_certificate_minting_ready"] is False
    assert strict_payload["terminal_evidence_blocked_candidate_count"] >= 0
    assert strict_payload["terminal_minting_gate_blocked_candidate_count"] >= 0
    assert require_ready_exit_code == 2
    assert require_ready_payload["artifact_valid"] is True
    assert require_ready_payload["promotion_ready"] is False


def _write_adapter_evidence(tmp_path: Path) -> Path:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "ready": False,
                "adapters": [
                    {
                        "adapter_id": "browser.playwright",
                        "blockers": ["browser_live_evidence_missing"],
                    },
                    {
                        "adapter_id": "document.production_parsers",
                        "blockers": [],
                    },
                    {
                        "adapter_id": "voice.openai",
                        "blockers": [
                            "voice_dependency_missing:OPENAI_API_KEY",
                            "voice_live_evidence_missing",
                        ],
                    },
                    {
                        "adapter_id": "communication.email_calendar_worker",
                        "blockers": [
                            "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                            "email_calendar_live_evidence_missing",
                        ],
                    },
                ],
                "blockers": [
                    "browser_live_evidence_missing",
                    "voice_dependency_missing:OPENAI_API_KEY",
                    "voice_live_evidence_missing",
                    "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                    "email_calendar_live_evidence_missing",
                ],
            }
        ),
        encoding="utf-8",
    )
    return evidence_path


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
