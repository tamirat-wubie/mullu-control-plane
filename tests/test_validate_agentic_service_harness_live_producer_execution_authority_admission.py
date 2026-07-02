"""Tests for live producer execution authority admission validation.

Purpose: lock live producer execution authority admission as AwaitingEvidence
without granting live effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_execution_authority_admission.
Invariants: admission validation rejects component satisfaction, authority drift,
mutation routes, and secret-bearing keys.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_admission import (  # noqa: E402
    ADMISSION_ID,
    DEFAULT_FIXTURE,
    REQUIRED_COMPONENT_IDS,
    main,
    validate_live_producer_execution_authority_admission,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, admission: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_admission.json"
    path.write_text(json.dumps(admission, indent=2), encoding="utf-8")
    return path


def test_live_producer_execution_authority_admission_accepts_default_fixture() -> None:
    validation, admission = validate_live_producer_execution_authority_admission()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.admission_id == ADMISSION_ID
    assert validation.admission_status == "blocked_awaiting_live_execution_authority_components"
    assert validation.required_component_count == 9
    assert validation.missing_evidence_count == 9
    assert tuple(item["component_id"] for item in admission["required_components"]) == REQUIRED_COMPONENT_IDS


def test_live_producer_execution_authority_admission_rejects_component_satisfaction(tmp_path: Path) -> None:
    admission = _load_fixture()
    changed = copy.deepcopy(admission)
    changed["required_components"][0]["required_ref"] = "receipt://already-satisfied"
    changed["required_components"][0]["status"] = "SolvedVerified"
    changed["missing_evidence"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_admission(fixture_path=_write_fixture(tmp_path, changed))

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "required_ref must stay future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "AwaitingEvidence" in serialized_errors


def test_live_producer_execution_authority_admission_rejects_authority_drift(tmp_path: Path) -> None:
    admission = _load_fixture()
    changed = copy.deepcopy(admission)
    changed["live_execution_authorized"] = True
    changed["authority_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_admission(fixture_path=_write_fixture(tmp_path, changed))

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "live_execution_authorized" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_live_producer_execution_authority_admission_rejects_route_and_credential_value(tmp_path: Path) -> None:
    admission = _load_fixture()
    changed = copy.deepcopy(admission)
    changed["next_action"] = "POST /api/v1/harness/live-producer access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_admission(fixture_path=_write_fixture(tmp_path, changed))

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_live_producer_execution_authority_admission_rejects_secret_bearing_key(tmp_path: Path) -> None:
    admission = _load_fixture()
    changed = copy.deepcopy(admission)
    changed["api_key_ref"] = "future://agentic-service-harness/live-producer/not-a-value"

    validation, _ = validate_live_producer_execution_authority_admission(fixture_path=_write_fixture(tmp_path, changed))

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "unexpected property 'api_key_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_live_producer_execution_authority_admission_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["admission_id"] == ADMISSION_ID
    assert payload["required_component_count"] == 9
    assert payload["missing_evidence_count"] == 9
