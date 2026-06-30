"""Tests for the evidence-ledger foundation source validator.

Purpose: prove the repository-local evidence source remains schema-bound,
read-only, non-live, authority-scoped, and free of secret-like payload drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_evidence_ledger_foundation_source.
Invariants:
  - Foundation markers cannot be weakened.
  - Evidence records must cite declared source authorities and allowed domains.
  - Required evidence kinds must be covered before the read model is admitted.
"""

from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_evidence_ledger_foundation_source import (  # noqa: E402
    DEFAULT_SOURCE_PATH,
    FoundationSourceFinding,
    load_json_object,
    validate_evidence_ledger_foundation_source,
)


def test_default_foundation_source_validates() -> None:
    result = validate_evidence_ledger_foundation_source()

    assert result.ok is True
    assert result.findings == ()
    assert result.source_id == "foundation-evidence-ledger-source.v1"
    assert result.source_version == 1
    assert result.source_hash.startswith("sha256:")
    assert result.source_authority_count == 3
    assert result.evidence_record_count == 3
    assert result.required_evidence_kinds == ("transaction", "email", "api_response")
    assert result.observed_evidence_kinds == ("api_response", "email", "transaction")


def test_foundation_source_rejects_marker_drift(tmp_path: Path) -> None:
    payload = _source_payload()
    payload["source_is_not_live_evidence"] = False
    candidate_path = _write_candidate(tmp_path, payload)

    result = validate_evidence_ledger_foundation_source(source_path=candidate_path)

    assert result.ok is False
    assert _has_rule(result.findings, "foundation_source_schema_violation")
    assert _has_rule(result.findings, "foundation_source_marker_invalid")


def test_foundation_source_rejects_unknown_evidence_source(tmp_path: Path) -> None:
    payload = _source_payload()
    payload["evidence_records"][0]["source_id"] = "undeclared-source"
    candidate_path = _write_candidate(tmp_path, payload)

    result = validate_evidence_ledger_foundation_source(source_path=candidate_path)

    assert result.ok is False
    assert _has_rule(result.findings, "foundation_source_evidence_unknown_source")
    assert result.evidence_record_count == 3


def test_foundation_source_rejects_forbidden_authority_domain(tmp_path: Path) -> None:
    payload = _source_payload()
    payload["evidence_records"][1]["authority_domain"] = "payment_settlement"
    candidate_path = _write_candidate(tmp_path, payload)

    result = validate_evidence_ledger_foundation_source(source_path=candidate_path)

    assert result.ok is False
    assert _has_rule(result.findings, "foundation_source_authority_domain_uncovered")
    assert _has_rule(result.findings, "foundation_source_forbidden_authority_domain")


def test_foundation_source_rejects_missing_required_evidence_kind(tmp_path: Path) -> None:
    payload = _source_payload()
    payload["evidence_records"] = payload["evidence_records"][:2]
    candidate_path = _write_candidate(tmp_path, payload)

    result = validate_evidence_ledger_foundation_source(source_path=candidate_path)

    assert result.ok is False
    assert _has_rule(result.findings, "foundation_source_required_evidence_missing")
    assert result.observed_evidence_kinds == ("email", "transaction")


def test_foundation_source_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _source_payload()
    payload["evidence_records"][0]["raw_payload"]["api_token"] = "token=abc123"
    candidate_path = _write_candidate(tmp_path, payload)

    result = validate_evidence_ledger_foundation_source(source_path=candidate_path)

    assert result.ok is False
    assert _has_rule(result.findings, "foundation_source_secret_key_forbidden")
    assert _has_rule(result.findings, "foundation_source_secret_value_forbidden")


def _source_payload() -> dict[str, object]:
    return deepcopy(load_json_object(DEFAULT_SOURCE_PATH, "default source"))


def _write_candidate(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "foundation_evidence_source.candidate.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _has_rule(findings: tuple[FoundationSourceFinding, ...], rule_id: str) -> bool:
    return any(finding.rule_id == rule_id for finding in findings)
