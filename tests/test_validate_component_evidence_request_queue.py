"""Tests for Component Harness evidence request queue validation.

Purpose: prove evidence request queues remain request-only, source-bound, and
non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_evidence_request_queue and
foundation Component Harness fixtures.
Invariants: request queues do not submit, accept, approve, grant, execute, or
claim terminal closure.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mcoi_runtime.app.component_evidence_request_queue import (
    ComponentEvidenceRequestQueueError,
    build_component_evidence_request_queue,
)
from scripts.validate_component_evidence_request_queue import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_evidence_request_queue,
    write_component_evidence_request_queue_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_evidence_request_queue.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _request_slots(payload: dict[str, object]) -> list[dict[str, object]]:
    slots = payload["request_slots"]
    assert isinstance(slots, list)
    return slots


def test_component_evidence_request_queue_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_evidence_request_queue()
    output_path = tmp_path / "component-evidence-request-queue-validation.json"

    written_path = write_component_evidence_request_queue_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.bundle_count == 3
    assert validation.request_slot_count == 7
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_evidence_request_queue_validation.json"


def test_component_evidence_request_queue_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_evidence_request_queue()

    assert example == projection
    assert example["queue_is_not_execution_authority"] is True
    assert example["evidence_submitted"] is False
    assert example["terminal_closure_allowed"] is False
    assert example["summary"]["unknown_proof_state_count"] == 7


def test_component_evidence_request_queue_rejects_execution_and_acceptance_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["can_execute"] = True
    payload["evidence_accepted"] = True
    payload["terminal_closure_allowed"] = True
    slot = _request_slots(payload)[0]
    slot["evidence_accepted"] = True
    slot["authority_granted"] = True

    validation = validate_component_evidence_request_queue(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "can_execute must be false" in serialized_errors
    assert "evidence_accepted must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors


def test_component_evidence_request_queue_rejects_missing_blockers_and_validators(tmp_path: Path) -> None:
    payload = _default_payload()
    slot = _request_slots(payload)[0]
    slot["blocked_actions"] = ["connector_call"]
    slot["claim_firewall_blocking_claim_ids"] = []
    slot["required_validator_refs"] = ["component_bundle_compiler_validator"]

    validation = validate_component_evidence_request_queue(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked_actions must include terminal_closure" in serialized_errors
    assert "must carry claim firewall blocking claim ids" in serialized_errors
    assert "must require component_claim_firewall_validator" in serialized_errors


def test_component_evidence_request_queue_runtime_rejects_unsafe_bundle_source() -> None:
    payload = _default_payload()
    source_bundle = {
        "compiler_is_not_execution_authority": True,
        "live_execution_enabled": True,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "bundle_id": "unsafe_bundle",
        "compilation_id": "component_bundle_compilation.unsafe_bundle.v1",
        "outcome": "GovernanceBlocked",
        "blocked_actions": ["terminal_closure"],
        "missing_evidence": ["operator_approval_receipt"],
    }
    claim_firewall = {
        "firewall_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "claim_checks": [{"claim_id": "blocked.production_ready", "decision": "blocked"}],
    }

    with pytest.raises(ComponentEvidenceRequestQueueError, match="live_execution_enabled must be false"):
        build_component_evidence_request_queue(
            bundle_compilations=[source_bundle],
            claim_firewall=claim_firewall,
        )

    assert deepcopy(payload)["summary"]["request_slot_count"] == 7
