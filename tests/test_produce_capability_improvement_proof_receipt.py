"""Tests for capability improvement proof receipt production.

Purpose: prove activation-blocked capability improvement plans can emit a
schema-valid proof receipt without activating the capability.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_capability_improvement_proof_receipt and
scripts.produce_capability_improvement_portfolio.
Invariants:
  - Proof receipts are not execution grants.
  - Proof receipts preserve source portfolio and plan identity.
  - Missing capability plans fail closed without writing output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.produce_capability_improvement_portfolio import (  # noqa: E402
    DEFAULT_GENERATED_AT,
    produce_capability_improvement_portfolio,
)
from scripts.produce_capability_improvement_proof_receipt import (  # noqa: E402
    DEFAULT_CAPABILITY_ID,
    main,
    produce_capability_improvement_proof_receipt,
    validate_capability_improvement_proof_receipt,
)


def test_produce_capability_improvement_proof_receipt_writes_schema_valid_artifact(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "capability_improvement_portfolio.json"
    output_path = tmp_path / "capability_improvement_proof_receipt.json"
    portfolio_result = produce_capability_improvement_portfolio(
        output_path=portfolio_path,
        generated_at=DEFAULT_GENERATED_AT,
        profile="agentic-control-core",
        candidate_limit=None,
    )

    run = produce_capability_improvement_proof_receipt(
        portfolio_path=portfolio_path,
        output_path=output_path,
        generated_at=DEFAULT_GENERATED_AT,
        capability_id=DEFAULT_CAPABILITY_ID,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert portfolio_result.passed is True
    assert run.passed is True
    assert run.capability_id == DEFAULT_CAPABILITY_ID
    assert run.receipt_id == payload["receipt_id"]
    assert run.evidence_key_count == len(payload["evidence_keys"])
    assert run.resolved_blocker_count == len(payload["resolved_blockers"])
    assert payload["status"] == "passed"
    assert payload["verification_status"] == "passed"
    assert payload["metadata"]["proof_is_not_execution"] is True
    assert payload["metadata"]["capability_activation_performed"] is False
    assert payload["metadata"]["registry_mutated"] is False
    assert payload["metadata"]["secret_values_serialized"] is False
    assert "capability_registry:agentic_control.governance_gate.evaluate" in payload["evidence_keys"]
    assert "change_command_not_certified" in payload["evidence_keys"]
    assert "terminal_closure_missing" in payload["evidence_keys"]
    assert validate_capability_improvement_proof_receipt(payload) == ()
    assert str(tmp_path) not in json.dumps(payload, sort_keys=True)


def test_capability_improvement_proof_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    portfolio_path = tmp_path / "capability_improvement_portfolio.json"
    output_path = tmp_path / "capability_improvement_proof_receipt.json"
    produce_capability_improvement_portfolio(
        output_path=portfolio_path,
        generated_at=DEFAULT_GENERATED_AT,
        profile="agentic-control-core",
        candidate_limit=None,
    )

    exit_code = main(
        [
            "--portfolio",
            str(portfolio_path),
            "--output",
            str(output_path),
            "--capability-id",
            DEFAULT_CAPABILITY_ID,
            "--json",
            "--strict",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["status"] == "passed"
    assert payload["capability_id"] == DEFAULT_CAPABILITY_ID
    assert payload["evidence_key_count"] >= 10
    assert payload["resolved_blocker_count"] == 6
    assert payload["validation_errors"] == []
    assert payload["blockers"] == []


def test_capability_improvement_proof_receipt_missing_plan_fails_closed(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "capability_improvement_portfolio.json"
    output_path = tmp_path / "missing_capability_proof_receipt.json"
    produce_capability_improvement_portfolio(
        output_path=portfolio_path,
        generated_at=DEFAULT_GENERATED_AT,
        profile="agentic-control-core",
        candidate_limit=None,
    )

    run = produce_capability_improvement_proof_receipt(
        portfolio_path=portfolio_path,
        output_path=output_path,
        generated_at=DEFAULT_GENERATED_AT,
        capability_id="agentic_control.missing",
    )

    assert run.passed is False
    assert run.status == "blocked"
    assert run.blockers == ("capability_plan_missing",)
    assert run.validation_errors == ()
    assert run.receipt_id == ""
    assert run.evidence_key_count == 0
    assert not output_path.exists()
