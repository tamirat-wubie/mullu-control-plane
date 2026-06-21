"""Tests for Agentic Service Harness Receipt/EvidenceBundle read models.

Purpose: prove Receipt and EvidenceBundle projections remain read-only,
reference-consistent, append-disabled, redacted, and non-terminal.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_receipt_evidence_read_models.
Invariants:
  - Valid foundation examples pass schema and semantic validation.
  - Receipt/evidence drift, append enablement, missing append evidence,
    mutation routes, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_receipt_evidence_read_models import (  # noqa: E402
    DEFAULT_EXAMPLES,
    main,
    validate_agentic_service_harness_receipt_evidence_read_models,
    write_receipt_evidence_read_models_validation,
)


def test_receipt_evidence_read_models_accept_default_example() -> None:
    validation = validate_agentic_service_harness_receipt_evidence_read_models()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.schema_path == "schemas/agentic_service_harness_receipt_evidence_read_models.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    )
    payload = _default_payload()
    assert payload["scope"]["append_enabled"] is False
    assert payload["receipt_read_models"][0]["run_id"] == payload["evidence_bundle_read_models"][0]["run_id"]
    assert payload["append_preflight"]["blocked_reason_refs"]


def test_receipt_evidence_read_models_reject_reference_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["receipt_read_models"][0]["evidence_bundle_id"] = "missing-bundle"
    payload["evidence_bundle_read_models"][0]["receipt_ids"] = ["missing-receipt"]
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_receipt_evidence_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "references missing evidence bundle" in serialized_errors
    assert "references missing receipt" in serialized_errors
    assert validation.example_count == 1


def test_receipt_evidence_read_models_reject_append_enablement(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["append_enabled"] = True
    payload["append_preflight"]["append_enabled"] = True
    payload["authority_denials"]["receipt_store_append"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_receipt_evidence_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scope.append_enabled" in serialized_errors
    assert "append_preflight.append_enabled" in serialized_errors
    assert "authority_denials.receipt_store_append" in serialized_errors


def test_receipt_evidence_read_models_reject_missing_append_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["append_preflight"]["required_before_append_refs"] = []
    payload["append_preflight"]["blocked_reason_refs"] = []
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_receipt_evidence_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing required_before_append_refs" in serialized_errors
    assert "missing blocked_reason_refs" in serialized_errors
    assert "evidence://uao-receipt-append-admission" in serialized_errors


def test_receipt_evidence_read_models_reject_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/receipts"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_receipt_evidence_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_receipt_evidence_read_models_reject_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["scope"]["access_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_receipt_evidence_read_models(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_receipt_evidence_read_models_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "receipt-evidence-read-models-validation.json"
    validation = validate_agentic_service_harness_receipt_evidence_read_models()

    written = write_receipt_evidence_read_models_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["example_count"] == 1


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_receipt_evidence_read_models.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
