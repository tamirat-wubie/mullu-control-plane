"""Purpose: verify canonical MCOI runtime fixtures round-trip through MCOI contracts.
Governance scope: exact witness conformance for MCOI-only runtime contract surfaces.
Dependencies: shared MCOI runtime fixtures and incident/recovery contract modules.
Invariants: canonical payload witnesses preserve exact JSON rendering across incident and recovery contracts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcoi_runtime.contracts.incident import (
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryDecision,
    RecoveryDecisionStatus,
)
from mcoi_runtime.contracts.recovery import RecoveryRecord


FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "mcoi_runtime"


def _load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _build_incident_record(payload: dict) -> IncidentRecord:
    return IncidentRecord(
        incident_id=payload["incident_id"],
        severity=IncidentSeverity(payload["severity"]),
        status=IncidentStatus(payload["status"]),
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        failure_family=payload["failure_family"],
        message=payload["message"],
        occurred_at=payload["occurred_at"],
        run_id=payload["run_id"],
        skill_id=payload["skill_id"],
        provider_id=payload["provider_id"],
        escalation_id=payload["escalation_id"],
        metadata=payload["metadata"],
    )


def _build_recovery_decision(payload: dict) -> RecoveryDecision:
    return RecoveryDecision(
        decision_id=payload["decision_id"],
        incident_id=payload["incident_id"],
        action=RecoveryAction(payload["action"]),
        status=RecoveryDecisionStatus(payload["status"]),
        reason=payload["reason"],
        autonomy_mode=payload["autonomy_mode"],
        profile_id=payload["profile_id"],
    )


def _build_recovery_attempt(payload: dict) -> RecoveryAttempt:
    return RecoveryAttempt(
        attempt_id=payload["attempt_id"],
        incident_id=payload["incident_id"],
        decision_id=payload["decision_id"],
        action=RecoveryAction(payload["action"]),
        succeeded=payload["succeeded"],
        started_at=payload["started_at"],
        finished_at=payload["finished_at"],
        error_message=payload["error_message"],
        result_run_id=payload["result_run_id"],
    )


def _build_recovery_record(payload: dict) -> RecoveryRecord:
    return RecoveryRecord(
        recovery_id=payload["recovery_id"],
        execution_id=payload["execution_id"],
        trace_id=payload["trace_id"],
        recorded_at=payload["recorded_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("incident_record.json", _build_incident_record),
        ("recovery_decision.json", _build_recovery_decision),
        ("recovery_attempt.json", _build_recovery_attempt),
        ("recovery_record.json", _build_recovery_record),
    ],
)
def test_mcoi_runtime_fixture_round_trips_exactly_through_mcoi_contracts(
    fixture_name: str,
    builder,
) -> None:
    fixture_payload = _load_fixture(fixture_name)
    contract = builder(fixture_payload)

    rendered = contract.to_json_dict()

    assert isinstance(rendered, dict)
    assert rendered == fixture_payload
    assert json.loads(contract.to_json()) == fixture_payload
