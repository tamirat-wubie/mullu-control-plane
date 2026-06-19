"""Tests for Agentic Service Harness live producer effect receipt preflight.

Purpose: prove the effect receipt requirement is explicit while the actual
effect receipt remains missing and authority-denying.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_effect_receipt_preflight.
Invariants:
  - The default preflight validates.
  - Effect receipt satisfaction, live authority, mutation routes, and
    credential-like values fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_effect_receipt_preflight import (  # noqa: E402
    DEFAULT_FIXTURE,
    PREFLIGHT_ID,
    REQUIRED_MISSING_EVIDENCE,
    main,
    validate_live_producer_effect_receipt_preflight,
)


def _default_preflight() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_effect_receipt_preflight_accepts_default_fixture() -> None:
    validation = validate_live_producer_effect_receipt_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.preflight_id == PREFLIGHT_ID
    assert validation.target_witness_kind == "effect_receipt"
    assert validation.effect_receipt_status == "AwaitingEvidence"
    assert validation.missing_evidence_count == len(REQUIRED_MISSING_EVIDENCE)
    assert validation.remaining_witness_count == 4
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1


def test_live_producer_effect_receipt_preflight_rejects_effect_satisfaction(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["effect_receipt_status"] = "SolvedVerified"
    preflight["effect_receipt_collected"] = True
    preflight["required_effect_receipt"]["status"] = "SolvedVerified"
    preflight["remaining_witnesses"][0]["status"] = "Satisfied"
    preflight_path = tmp_path / "effect-receipt-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_effect_receipt_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "effect_receipt_status" in serialized_errors
    assert "effect_receipt_collected" in serialized_errors
    assert "required effect receipt status must be AwaitingEvidence" in serialized_errors
    assert "effect_receipt status must be AwaitingEvidence" in serialized_errors


def test_live_producer_effect_receipt_preflight_rejects_live_authority(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["authority_granted"] = True
    preflight["authority_denials"]["live_execution_authorized"] = True
    preflight["effect_boundary"]["runtime_state_written"] = True
    preflight_path = tmp_path / "effect-receipt-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_effect_receipt_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert "effect_boundary.runtime_state_written" in serialized_errors


def test_live_producer_effect_receipt_preflight_rejects_missing_evidence_gap(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["missing_evidence"] = preflight["missing_evidence"][:-1]
    preflight_path = tmp_path / "effect-receipt-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_effect_receipt_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence" in serialized_errors
    assert "missing evidence ids must match required order" in serialized_errors


def test_live_producer_effect_receipt_preflight_rejects_mutation_route_ref(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["required_effect_receipt"]["receipt_ref"] = "POST /api/v1/harness/live-producer/effects"
    preflight_path = tmp_path / "effect-receipt-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_effect_receipt_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "required_effect_receipt.receipt_ref" in serialized_errors


def test_live_producer_effect_receipt_preflight_rejects_secret_like_value(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["next_action"] = "Collect sk-forbiddencredential"
    preflight_path = tmp_path / "effect-receipt-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_effect_receipt_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors


def test_live_producer_effect_receipt_preflight_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["preflight_id"] == PREFLIGHT_ID
    assert payload["effect_receipt_status"] == "AwaitingEvidence"
