"""Tests for InceptaDive external-effect adapter readiness.

Purpose: prove the future external-effect adapter remains evidence-bound and
non-authorizing until hard governance receipts exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_inceptadive_external_effect_adapter_readiness.
Invariants:
  - The default readiness packet validates.
  - Live authority, credentials, mutation routes, and evidence gaps fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_inceptadive_external_effect_adapter_readiness import (  # noqa: E402
    AUTHORITY_DENIAL_FLAGS,
    DEFAULT_FIXTURE,
    READINESS_ID,
    REQUIRED_ACTION_FAMILIES,
    REQUIRED_MISSING_EVIDENCE,
    main,
    validate_inceptadive_external_effect_adapter_readiness,
)


def _default_readiness() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_inceptadive_external_effect_adapter_readiness_accepts_default_fixture() -> None:
    validation = validate_inceptadive_external_effect_adapter_readiness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.readiness_id == READINESS_ID
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.missing_evidence_count == len(REQUIRED_MISSING_EVIDENCE)
    assert validation.action_family_count == len(REQUIRED_ACTION_FAMILIES)
    assert validation.authority_denial_count == len(AUTHORITY_DENIAL_FLAGS)


def test_inceptadive_external_effect_adapter_readiness_rejects_live_authority(tmp_path: Path) -> None:
    readiness = _default_readiness()
    readiness["external_effect_execution_authorized"] = True
    readiness["connector_dispatch_authority"] = True
    readiness["authority_denials"]["provider_mutation_authority"] = True
    readiness["effect_boundary"]["provider_calls_allowed"] = True
    readiness_path = tmp_path / "inceptadive-readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    validation = validate_inceptadive_external_effect_adapter_readiness(fixture_path=readiness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effect_execution_authorized" in serialized_errors
    assert "connector_dispatch_authority" in serialized_errors
    assert "authority_denials.provider_mutation_authority" in serialized_errors
    assert "effect_boundary.provider_calls_allowed" in serialized_errors


def test_inceptadive_external_effect_adapter_readiness_rejects_credentials(tmp_path: Path) -> None:
    readiness = _default_readiness()
    readiness["adapter_credentials_present"] = True
    readiness["adapter_credentials_serialized"] = True
    readiness["next_action"] = "Collect sk-forbiddencredential"
    readiness_path = tmp_path / "inceptadive-readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    validation = validate_inceptadive_external_effect_adapter_readiness(fixture_path=readiness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "adapter_credentials_present" in serialized_errors
    assert "adapter_credentials_serialized" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors


def test_inceptadive_external_effect_adapter_readiness_rejects_missing_evidence_gap(tmp_path: Path) -> None:
    readiness = _default_readiness()
    readiness["missing_evidence"] = readiness["missing_evidence"][:-1]
    readiness["required_evidence"]["authority_granted"] = True
    readiness_path = tmp_path / "inceptadive-readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    validation = validate_inceptadive_external_effect_adapter_readiness(fixture_path=readiness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence" in serialized_errors
    assert "missing evidence ids must match required order" in serialized_errors
    assert "required_evidence.authority_granted must be false" in serialized_errors


def test_inceptadive_external_effect_adapter_readiness_rejects_mutation_route_ref(tmp_path: Path) -> None:
    readiness = _default_readiness()
    readiness["required_evidence"]["dry_run_probe_receipt_ref"] = "POST /api/v1/shadow/external-effect/execute"
    readiness_path = tmp_path / "inceptadive-readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    validation = validate_inceptadive_external_effect_adapter_readiness(fixture_path=readiness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "required_evidence.dry_run_probe_receipt_ref" in serialized_errors
    assert "external-effect/execute" not in serialized_errors


def test_inceptadive_external_effect_adapter_readiness_rejects_live_claim_text(tmp_path: Path) -> None:
    readiness = _default_readiness()
    readiness["next_action"] = "Do not claim adapter_implemented=true until governed receipts exist."
    readiness_path = tmp_path / "inceptadive-readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    validation = validate_inceptadive_external_effect_adapter_readiness(fixture_path=readiness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live adapter claim" in serialized_errors
    assert "next_action" in serialized_errors
    assert "adapter_implemented=true" not in serialized_errors


def test_inceptadive_external_effect_adapter_readiness_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["readiness_id"] == READINESS_ID
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["missing_evidence_count"] == len(REQUIRED_MISSING_EVIDENCE)
