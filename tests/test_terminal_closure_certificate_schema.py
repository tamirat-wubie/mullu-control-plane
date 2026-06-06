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
  - Every disposition rejects non-null proof anchors from other closure paths.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_terminal_closure_certificate import (
    DISPOSITION_FORBIDDEN_ANCHORS,
    DISPOSITION_REQUIRED_ANCHORS,
    VALID_DISPOSITIONS,
)
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


def test_terminal_closure_schema_disposition_rules_match_validator_tables() -> None:
    schema = _load_schema(SCHEMA_PATH)
    schema_rules = _schema_disposition_rules(schema)

    assert set(schema_rules) == set(VALID_DISPOSITIONS)
    for disposition in sorted(VALID_DISPOSITIONS):
        assert set(schema_rules[disposition]["required"]) == set(DISPOSITION_REQUIRED_ANCHORS[disposition])
        assert set(schema_rules[disposition]["forbidden"]) == set(DISPOSITION_FORBIDDEN_ANCHORS[disposition])


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


def test_terminal_closure_schema_accepts_compensated_certificate() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="compensated",
        compensation_outcome_id="comp-outcome-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert errors == []
    assert certificate["disposition"] == "compensated"
    assert certificate["compensation_outcome_id"] == "comp-outcome-1"


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


def test_terminal_closure_schema_accepts_accepted_risk_certificate() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="accepted_risk",
        accepted_risk_id="risk-1",
        case_id="case-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert errors == []
    assert certificate["disposition"] == "accepted_risk"
    assert certificate["accepted_risk_id"] == "risk-1"
    assert certificate["case_id"] == "case-1"


def test_terminal_closure_schema_requires_case_for_review() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(disposition="requires_review")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert "case_id" in errors[0]
    assert "missing required fields" in errors[0]


def test_terminal_closure_schema_accepts_review_certificate() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="requires_review",
        case_id="case-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert errors == []
    assert certificate["disposition"] == "requires_review"
    assert certificate["case_id"] == "case-1"


def test_terminal_closure_schema_allows_null_unselected_anchors() -> None:
    schema = _load_schema(SCHEMA_PATH)
    cases = [
        _certificate(
            compensation_outcome_id=None,
            accepted_risk_id=None,
            case_id=None,
            include_null_anchors=True,
        ),
        _certificate(
            disposition="compensated",
            compensation_outcome_id="comp-outcome-1",
            accepted_risk_id=None,
            case_id=None,
            include_null_anchors=True,
        ),
        _certificate(
            disposition="accepted_risk",
            compensation_outcome_id=None,
            accepted_risk_id="risk-1",
            case_id="case-1",
            include_null_anchors=True,
        ),
        _certificate(
            disposition="requires_review",
            compensation_outcome_id=None,
            accepted_risk_id=None,
            case_id="case-1",
            include_null_anchors=True,
        ),
    ]

    errors_by_disposition = {
        certificate["disposition"]: _validate_schema_instance(schema, certificate)
        for certificate in cases
    }

    assert errors_by_disposition == {
        "committed": [],
        "compensated": [],
        "accepted_risk": [],
        "requires_review": [],
    }


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


def test_terminal_closure_schema_rejects_committed_with_case() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(case_id="case-1")

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"
    assert certificate["disposition"] == "committed"


def test_terminal_closure_schema_rejects_compensated_with_accepted_risk() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="compensated",
        compensation_outcome_id="comp-outcome-1",
        accepted_risk_id="risk-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def test_terminal_closure_schema_rejects_compensated_with_case() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="compensated",
        compensation_outcome_id="comp-outcome-1",
        case_id="case-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def test_terminal_closure_schema_rejects_accepted_risk_with_compensation() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="accepted_risk",
        accepted_risk_id="risk-1",
        case_id="case-1",
        compensation_outcome_id="comp-outcome-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def test_terminal_closure_schema_rejects_review_with_compensation() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="requires_review",
        compensation_outcome_id="comp-outcome-1",
        case_id="case-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def test_terminal_closure_schema_rejects_review_with_accepted_risk() -> None:
    schema = _load_schema(SCHEMA_PATH)
    certificate = _certificate(
        disposition="requires_review",
        accepted_risk_id="risk-1",
        case_id="case-1",
    )

    errors = _validate_schema_instance(schema, certificate)

    assert len(errors) == 1
    assert errors[0] == "$: matched forbidden schema"


def _certificate(
    *,
    disposition: str = "committed",
    compensation_outcome_id: str | None = None,
    accepted_risk_id: str | None = None,
    case_id: str | None = None,
    include_null_anchors: bool = False,
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
    if include_null_anchors:
        certificate.update(
            {
                "compensation_outcome_id": compensation_outcome_id,
                "accepted_risk_id": accepted_risk_id,
                "case_id": case_id,
            }
        )
    if compensation_outcome_id is not None:
        certificate["compensation_outcome_id"] = compensation_outcome_id
    if accepted_risk_id is not None:
        certificate["accepted_risk_id"] = accepted_risk_id
    if case_id is not None:
        certificate["case_id"] = case_id
    return deepcopy(certificate)


def _schema_disposition_rules(schema: dict[str, Any]) -> dict[str, dict[str, tuple[str, ...]]]:
    rules: dict[str, dict[str, tuple[str, ...]]] = {}
    for rule in schema["allOf"]:
        disposition = rule["if"]["properties"]["disposition"]["const"]
        then_schema = rule["then"]
        rules[disposition] = {
            "required": tuple(then_schema.get("required", ())),
            "forbidden": _forbidden_non_null_anchor_names(then_schema.get("not", {})),
        }
    return rules


def _forbidden_non_null_anchor_names(forbidden_schema: dict[str, Any]) -> tuple[str, ...]:
    if not forbidden_schema:
        return ()
    branches = forbidden_schema.get("anyOf", (forbidden_schema,))
    anchor_names: list[str] = []
    for branch in branches:
        required = branch["required"]
        assert len(required) == 1
        anchor_name = required[0]
        assert branch["properties"][anchor_name] == {"type": "string", "minLength": 1}
        anchor_names.append(anchor_name)
    return tuple(anchor_names)
