"""Tests for Agentic Service Harness live producer external adapter evidence preflight.

Purpose: prove the external adapter evidence requirement is explicit while
adapter integration, credentials, network egress, and live authority remain denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.
Invariants:
  - The default preflight validates.
  - Adapter evidence satisfaction, adapter authority, mutation routes, and
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
from scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight import (  # noqa: E402
    DEFAULT_FIXTURE,
    PREFLIGHT_ID,
    REQUIRED_MISSING_EVIDENCE,
    main,
    validate_live_producer_external_adapter_evidence_preflight,
)


def _default_preflight() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_external_adapter_evidence_preflight_accepts_default_fixture() -> None:
    validation = validate_live_producer_external_adapter_evidence_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.preflight_id == PREFLIGHT_ID
    assert validation.target_witness_kind == "external_adapter_evidence"
    assert validation.external_adapter_evidence_status == "AwaitingEvidence"
    assert validation.missing_evidence_count == len(REQUIRED_MISSING_EVIDENCE)
    assert validation.remaining_witness_count == 4
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1


def test_live_producer_external_adapter_evidence_preflight_rejects_adapter_satisfaction(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["external_adapter_evidence_status"] = "SolvedVerified"
    preflight["external_adapter_integrated"] = True
    preflight["required_external_adapter_evidence"]["status"] = "SolvedVerified"
    preflight["remaining_witnesses"][1]["status"] = "Satisfied"
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_adapter_evidence_status" in serialized_errors
    assert "external_adapter_integrated" in serialized_errors
    assert "required external adapter evidence status must be AwaitingEvidence" in serialized_errors
    assert "external_adapter_evidence status must be AwaitingEvidence" in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_rejects_adapter_credentials(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["adapter_credentials_present"] = True
    preflight["adapter_credentials_serialized"] = True
    preflight["required_external_adapter_evidence"]["adapter_credentials_present"] = True
    preflight["required_external_adapter_evidence"]["adapter_credentials_serialized"] = True
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "adapter_credentials_present" in serialized_errors
    assert "adapter_credentials_serialized" in serialized_errors
    assert "required external adapter evidence adapter_credentials_present must be false" in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_rejects_live_authority(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["authority_granted"] = True
    preflight["authority_denials"]["live_execution_authorized"] = True
    preflight["effect_boundary"]["runtime_state_written"] = True
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert "effect_boundary.runtime_state_written" in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_rejects_missing_evidence_gap(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["missing_evidence"] = preflight["missing_evidence"][:-1]
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence" in serialized_errors
    assert "missing evidence ids must match required order" in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_rejects_mutation_route_ref(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["required_external_adapter_evidence"]["evidence_ref"] = "POST /api/v1/harness/live-producer/adapters"
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "required_external_adapter_evidence.evidence_ref" in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_rejects_credential_like_value(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["next_action"] = "Collect ghp_forbiddencredential"
    preflight_path = tmp_path / "external-adapter-evidence-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation = validate_live_producer_external_adapter_evidence_preflight(fixture_path=preflight_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors


def test_live_producer_external_adapter_evidence_preflight_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["preflight_id"] == PREFLIGHT_ID
    assert payload["external_adapter_evidence_status"] == "AwaitingEvidence"
