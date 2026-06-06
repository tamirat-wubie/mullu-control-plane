"""Tests for terminal closure certificate artifact validation.

Purpose: prove the public terminal closure certificate example and CLI validator
produce deterministic, disposition-aware proof results.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_terminal_closure_certificate and
examples/terminal_closure_certificate.json.
Invariants:
  - The canonical example validates against the terminal closure schema.
  - Every disposition requires its own non-null proof anchors.
  - Every disposition rejects non-null proof anchors from other closure paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.validate_terminal_closure_certificate import (
    DEFAULT_CERTIFICATE,
    DEFAULT_SCHEMA,
    DISPOSITION_FORBIDDEN_ANCHORS,
    DISPOSITION_REQUIRED_ANCHORS,
    VALID_DISPOSITIONS,
    main,
    validate_terminal_closure_certificate,
)


def test_terminal_closure_certificate_example_validates() -> None:
    result = validate_terminal_closure_certificate()

    assert result.valid is True
    assert result.disposition == "committed"
    assert result.certificate_path == "examples/terminal_closure_certificate.json"
    assert result.schema_path == "schemas/terminal_closure_certificate.schema.json"
    assert result.evidence_ref_count == 2
    assert result.errors == ()


def test_terminal_closure_disposition_tables_are_complete_and_disjoint() -> None:
    assert set(DISPOSITION_REQUIRED_ANCHORS) == set(VALID_DISPOSITIONS)
    assert set(DISPOSITION_FORBIDDEN_ANCHORS) == set(VALID_DISPOSITIONS)
    for disposition in sorted(VALID_DISPOSITIONS):
        assert set(DISPOSITION_REQUIRED_ANCHORS[disposition]).isdisjoint(
            DISPOSITION_FORBIDDEN_ANCHORS[disposition]
        )


def test_terminal_closure_certificate_rejects_committed_compensation(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        compensation_outcome_id="compensation-outcome-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "committed"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("committed closure must not include compensation_outcome_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_committed_case(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "committed"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("committed closure must not include case_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_compensated_accepted_risk_anchor(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="compensated",
        compensation_outcome_id="compensation-outcome-1",
        accepted_risk_id="accepted-risk-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "compensated"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("compensated closure must not include accepted_risk_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_compensated_case_anchor(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="compensated",
        compensation_outcome_id="compensation-outcome-1",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "compensated"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("compensated closure must not include case_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_accepted_risk_without_case(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="accepted_risk",
        accepted_risk_id="accepted-risk-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "accepted_risk"
    assert any("case_id" in error for error in result.errors)
    assert any("accepted_risk closure requires case_id" in error for error in result.errors)


def test_terminal_closure_certificate_accepts_compensated_path(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="compensated",
        compensation_outcome_id="compensation-outcome-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is True
    assert result.disposition == "compensated"
    assert result.evidence_ref_count == 2
    assert result.errors == ()


def test_terminal_closure_certificate_accepts_accepted_risk_path(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="accepted_risk",
        accepted_risk_id="accepted-risk-1",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is True
    assert result.disposition == "accepted_risk"
    assert result.evidence_ref_count == 2
    assert result.errors == ()


def test_terminal_closure_certificate_accepts_review_path(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="requires_review",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is True
    assert result.disposition == "requires_review"
    assert result.evidence_ref_count == 2
    assert result.errors == ()


def test_terminal_closure_certificate_allows_null_unselected_anchors(
    tmp_path: Path,
) -> None:
    certificate_paths = [
        _write_certificate(
            tmp_path / "committed",
            null_anchor_fields=("compensation_outcome_id", "accepted_risk_id", "case_id"),
        ),
        _write_certificate(
            tmp_path / "compensated",
            disposition="compensated",
            compensation_outcome_id="compensation-outcome-1",
            null_anchor_fields=("accepted_risk_id", "case_id"),
        ),
        _write_certificate(
            tmp_path / "accepted-risk",
            disposition="accepted_risk",
            accepted_risk_id="accepted-risk-1",
            case_id="case-1",
            null_anchor_fields=("compensation_outcome_id",),
        ),
        _write_certificate(
            tmp_path / "review",
            disposition="requires_review",
            case_id="case-1",
            null_anchor_fields=("compensation_outcome_id", "accepted_risk_id"),
        ),
    ]

    results = [
        validate_terminal_closure_certificate(certificate_path=certificate_path)
        for certificate_path in certificate_paths
    ]

    assert [result.valid for result in results] == [True, True, True, True]
    assert [result.disposition for result in results] == [
        "committed",
        "compensated",
        "accepted_risk",
        "requires_review",
    ]
    assert [result.errors for result in results] == [(), (), (), ()]


def test_terminal_closure_certificate_rejects_accepted_risk_compensation_anchor(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="accepted_risk",
        accepted_risk_id="accepted-risk-1",
        compensation_outcome_id="compensation-outcome-1",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "accepted_risk"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("accepted_risk closure must not include compensation_outcome_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_review_compensation_anchor(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="requires_review",
        compensation_outcome_id="compensation-outcome-1",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "requires_review"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("requires_review closure must not include compensation_outcome_id" in error for error in result.errors)


def test_terminal_closure_certificate_rejects_review_accepted_risk_anchor(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="requires_review",
        accepted_risk_id="accepted-risk-1",
        case_id="case-1",
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)

    assert result.valid is False
    assert result.disposition == "requires_review"
    assert any("matched forbidden schema" in error for error in result.errors)
    assert any("requires_review closure must not include accepted_risk_id" in error for error in result.errors)


def test_terminal_closure_certificate_cli_returns_success(capsys: Any) -> None:
    exit_code = main(["--certificate", str(DEFAULT_CERTIFICATE), "--schema", str(DEFAULT_SCHEMA)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "terminal closure certificate ok" in output
    assert "disposition=committed" in output
    assert "error:" not in output


def test_terminal_closure_certificate_reports_evidence_refs_by_count_only(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        evidence_refs=["proof://sensitive-token-1", "s3://private-proof-bucket/object"],
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)
    payload = result.as_dict()
    serialized_payload = json.dumps(payload, sort_keys=True)

    assert result.valid is True
    assert result.certificate_path == "terminal_closure_certificate.json"
    assert payload["evidence_ref_count"] == 2
    assert "evidence_refs" not in payload
    assert str(tmp_path) not in serialized_payload
    assert "sensitive-token-1" not in serialized_payload
    assert "private-proof-bucket" not in serialized_payload


def test_terminal_closure_certificate_errors_do_not_include_evidence_ref_values(
    tmp_path: Path,
) -> None:
    certificate_path = _write_certificate(
        tmp_path,
        disposition="accepted_risk",
        accepted_risk_id="accepted-risk-secret",
        evidence_refs=["proof://sensitive-terminal-witness"],
    )

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert result.evidence_ref_count == 1
    assert any("accepted_risk closure requires case_id" in error for error in result.errors)
    assert "sensitive-terminal-witness" not in serialized_errors
    assert "accepted-risk-secret" not in serialized_errors


def test_terminal_closure_certificate_missing_file_error_is_bounded(
    tmp_path: Path,
) -> None:
    certificate_path = tmp_path / "secret-path-token.json"

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert result.certificate_path == "secret-path-token.json"
    assert result.errors == ("terminal closure certificate could not be read",)
    assert result.evidence_ref_count == 0
    assert str(tmp_path) not in json.dumps(result.as_dict(), sort_keys=True)
    assert "secret-path-token" not in serialized_errors


def test_terminal_closure_certificate_json_parse_error_is_bounded(
    tmp_path: Path,
) -> None:
    certificate_path = tmp_path / "secret-json-path.json"
    certificate_path.write_text('{"certificate_id": "secret-json-value"', encoding="utf-8")

    result = validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert result.certificate_path == "secret-json-path.json"
    assert result.errors == ("terminal closure certificate must be JSON",)
    assert result.evidence_ref_count == 0
    assert str(tmp_path) not in json.dumps(result.as_dict(), sort_keys=True)
    assert "secret-json-path" not in serialized_errors
    assert "secret-json-value" not in serialized_errors


def _write_certificate(
    tmp_path: Path,
    *,
    disposition: str = "committed",
    compensation_outcome_id: str | None = None,
    accepted_risk_id: str | None = None,
    case_id: str | None = None,
    evidence_refs: list[str] | None = None,
    null_anchor_fields: tuple[str, ...] = (),
) -> Path:
    certificate = json.loads(DEFAULT_CERTIFICATE.read_text(encoding="utf-8"))
    certificate["disposition"] = disposition
    for field_name in null_anchor_fields:
        certificate[field_name] = None
    if compensation_outcome_id is not None:
        certificate["compensation_outcome_id"] = compensation_outcome_id
    if accepted_risk_id is not None:
        certificate["accepted_risk_id"] = accepted_risk_id
    if case_id is not None:
        certificate["case_id"] = case_id
    if evidence_refs is not None:
        certificate["evidence_refs"] = evidence_refs
    tmp_path.mkdir(parents=True, exist_ok=True)
    certificate_path = tmp_path / "terminal_closure_certificate.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    return certificate_path
