"""Tests for the public terminal closure certificate schema.

Purpose: prove terminal command closure is governed by a public schema with
disposition-specific proof requirements.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/terminal_closure_certificate.schema.json and
scripts.validate_schemas.
Invariants:
  - Every certificate carries evidence refs.
  - Compensated closure requires compensation outcome evidence.
  - Accepted-risk and review closures require case anchoring.
  - Committed closure cannot carry compensation or accepted-risk proof.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "terminal_closure_certificate.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "terminal_closure_certificate.json"


def test_terminal_closure_schema_accepts_committed_certificate() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate()

    errors = _validate_schema_instance(schema, certificate)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:terminal-closure-certificate:1"
    assert schema["title"] == "Terminal Closure Certificate"


def test_terminal_closure_schema_accepts_public_example() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _load_schema(EXAMPLE_PATH)

    errors = _validate_schema_instance(schema, certificate)

    assert errors == []
    assert certificate["certificate_id"] == "terminal-closure-example-1"
    assert certificate["metadata"]["terminal_proof"] is True


def test_terminal_closure_schema_rejects_missing_evidence_refs() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate()
    certificate["evidence_refs"] = []

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert "$.evidence_refs" in errors[0]
    assert "at least 1 item" in errors[0]


def test_terminal_closure_schema_requires_compensation_outcome_for_compensated() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(disposition="compensated")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert "compensation_outcome_id" in errors[0]
    assert "missing required fields" in errors[0]


def test_terminal_closure_schema_requires_case_for_accepted_risk() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="accepted_risk",
        accepted_risk_id="risk-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert "case_id" in errors[0]
    assert "missing required fields" in errors[0]


def test_terminal_closure_schema_requires_case_for_review() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(disposition="requires_review")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert "case_id" in errors[0]
    assert "missing required fields" in errors[0]


def test_terminal_closure_schema_rejects_committed_with_compensation() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(compensation_outcome_id="comp-outcome-1")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def test_terminal_closure_schema_rejects_committed_with_accepted_risk() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(accepted_risk_id="risk-1")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"
    assert certificate["disposition"] == "committed"


def _certificate(
    *,
    disposition: str = "committed",
    compensation_outcome_id: str | None = None,
    accepted_risk_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    certificate = {
        "certificate_id": "terminal-closure-1",
        "command_id": "command-1",
        "execution_id": "execution-1",
        "disposition": disposition,
        "verification_result_id": "verification-1",
        "effect_reconciliation_id": "reconciliation-1",
        "evidence_refs": ["evidence:verification-1"],
        "closed_at": "2026-05-02T12:00:00Z",
        "response_closure_ref": None,
        "memory_entry_id": None,
        "graph_refs": ["command:command-1"],
        "metadata": {"source": "schema-test"},
    }
    if compensation_outcome_id is not None:
        certificate["compensation_outcome_id"] = compensation_outcome_id
    if accepted_risk_id is not None:
        certificate["accepted_risk_id"] = accepted_risk_id
    if case_id is not None:
        certificate["case_id"] = case_id
    return deepcopy(certificate)
