"""Tests for InceptaDive live producer readiness binding.

Purpose: prove the binding keeps InceptaDive external-effect readiness aligned
with the live-producer evidence packet chain without authorizing execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_inceptadive_live_producer_readiness_binding.
Invariants:
  - Default binding validates.
  - Source drift, authority grants, mutation routes, and credential values fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_inceptadive_live_producer_readiness_binding import (  # noqa: E402
    BINDING_ID,
    DEFAULT_FIXTURE,
    REQUIRED_BLOCKED_EVIDENCE,
    REQUIRED_SOURCE_IDS,
    main,
    validate_inceptadive_live_producer_readiness_binding,
)


def _default_binding() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_inceptadive_live_producer_readiness_binding_accepts_default_fixture() -> None:
    validation, fixture = validate_inceptadive_live_producer_readiness_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.binding_id == BINDING_ID
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert validation.source_binding_count == len(REQUIRED_SOURCE_IDS)
    assert validation.blocked_evidence_count == len(REQUIRED_BLOCKED_EVIDENCE)


def test_inceptadive_live_producer_readiness_binding_rejects_source_drift(tmp_path: Path) -> None:
    binding = _default_binding()
    binding["source_bindings"][1]["status"] = "SolvedVerified"
    binding["source_statuses"]["live_producer_evidence_intake"] = "SolvedVerified"
    binding_path = tmp_path / "readiness-binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(fixture_path=binding_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_producer_evidence_intake" in serialized_errors
    assert "source_statuses.live_producer_evidence_intake" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors


def test_inceptadive_live_producer_readiness_binding_rejects_authority_grant(tmp_path: Path) -> None:
    binding = _default_binding()
    binding["authority_granted"] = True
    binding["authority_denials"]["external_effect_execution_authorized"] = True
    binding["effect_boundary"]["provider_calls_allowed"] = True
    binding_path = tmp_path / "readiness-binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(fixture_path=binding_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "authority_denials.external_effect_execution_authorized" in serialized_errors
    assert "effect_boundary.provider_calls_allowed" in serialized_errors


def test_inceptadive_live_producer_readiness_binding_rejects_missing_blocked_evidence(tmp_path: Path) -> None:
    binding = _default_binding()
    binding["blocked_evidence"] = binding["blocked_evidence"][:-1]
    binding_path = tmp_path / "readiness-binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(fixture_path=binding_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_evidence" in serialized_errors
    assert "blocked evidence order mismatch" in serialized_errors
    assert "signed_dispatch_receipt_ref" in serialized_errors


def test_inceptadive_live_producer_readiness_binding_rejects_mutation_route_and_secret(tmp_path: Path) -> None:
    binding = _default_binding()
    binding["next_action"] = "Never send POST /api/v1/live-producer/execute with sk-forbiddencredential"
    binding_path = tmp_path / "readiness-binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(fixture_path=binding_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string denied" in serialized_errors
    assert "credential-like value denied" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors


def test_inceptadive_live_producer_readiness_binding_rejects_live_claim_text(tmp_path: Path) -> None:
    binding = _default_binding()
    binding["next_action"] = "Do not claim live_producer_implemented=true before receipts exist."
    binding_path = tmp_path / "readiness-binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(fixture_path=binding_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution claim denied" in serialized_errors
    assert "next_action" in serialized_errors
    assert "live_producer_implemented=true" not in serialized_errors


def test_inceptadive_live_producer_readiness_binding_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["binding_id"] == BINDING_ID
    assert payload["binding_status"] == "blocked_awaiting_live_producer_and_inceptadive_readiness_evidence"
    assert payload["source_binding_count"] == len(REQUIRED_SOURCE_IDS)
