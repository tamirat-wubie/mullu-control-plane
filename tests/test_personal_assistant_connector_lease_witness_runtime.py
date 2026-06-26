"""Tests for personal-assistant connector/lease witness runtime envelopes.

Purpose: prove replay/rollback witness evidence can produce no-effect connector
witness refs and inactive dispatch lease refs before execution-worker admission.
Governance scope: connector refs, tenant/scope/revocation refs, inactive lease
refs, receipt alignment, private payload redaction, and Foundation Mode
boundaries.
Dependencies: mcoi_runtime.personal_assistant connector/lease witness builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the connector/lease schema.
  - Live connector receipts are not claimed.
  - Dispatch leases remain inactive and no execution-worker admission occurs.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_connector_lease_witness,
    build_default_personal_assistant_replay_rollback_witness,
    build_personal_assistant_connector_lease_witness_envelope,
)
from scripts.validate_personal_assistant_connector_lease_witness import (
    _validate_connector_lease_witness_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
WITNESS_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_connector_lease_witness.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_connector_lease_witness_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_connector_lease_witness()
    witness_schema = _load_schema(WITNESS_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    witness = envelope["witnesses"][0]

    assert _validate_schema_instance(witness_schema, envelope) == []
    assert _validate_connector_lease_witness_semantics(envelope, receipt_schema) == ()
    assert envelope["witness_count"] == 1
    assert envelope["source_projection"] == "replay_rollback_witness"
    assert envelope["effect_boundary"]["connector_lease_witness_allowed"] is True
    assert envelope["effect_boundary"]["connector_witness_ref_binding_allowed"] is True
    assert envelope["effect_boundary"]["dispatch_lease_ref_binding_allowed"] is True
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_lease_active"] is False
    assert envelope["effect_boundary"]["live_connector_receipt_present"] is False
    assert envelope["effect_boundary"]["live_connector_execution_allowed"] is False
    assert witness["connector_witness"]["connector_family"] == "gmail"
    assert witness["connector_witness"]["connector_tenant_bound"] is True
    assert witness["connector_witness"]["connector_revocation_path_recorded"] is True
    assert witness["connector_witness"]["live_connector_witness_ref_bound"] is True
    assert witness["connector_witness"]["live_connector_witness_state"] == "ref_bound_live_receipt_awaiting_evidence"
    assert witness["connector_witness"]["live_connector_receipt_present"] is False
    assert witness["connector_witness"]["connector_mutation_allowed"] is False
    assert witness["dispatch_lease_witness"]["dispatch_lease_ref_bound"] is True
    assert witness["dispatch_lease_witness"]["dispatch_lease_state"] == "candidate_inactive"
    assert witness["dispatch_lease_witness"]["dispatch_lease_active"] is False
    assert witness["dispatch_lease_witness"]["dispatch_allowed"] is False
    assert witness["operator_reapproval_gate"]["operator_reapproval_required"] is True
    assert witness["operator_reapproval_gate"]["operator_reapproval_present"] is False
    assert witness["receipt"]["decision"] == "deferred"


def test_runtime_connector_lease_witness_rejects_empty_source_witnesses() -> None:
    replay_witness = build_default_personal_assistant_replay_rollback_witness()
    replay_witness["witnesses"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=replay_witness,
        )

    assert "requires at least one replay/rollback witness" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_connector_lease_witness_rejects_source_receipt_drift() -> None:
    replay_witness = build_default_personal_assistant_replay_rollback_witness()
    replay_witness["witnesses"][0]["receipt"]["decision"] = "allowed"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=replay_witness,
        )

    assert "replay/rollback receipt must be deferred" in str(exc_info.value)
    assert replay_witness["witnesses"][0]["witness_id"] in str(exc_info.value)


def test_runtime_connector_lease_witness_rejects_source_effect_boundary_drift() -> None:
    replay_witness = copy.deepcopy(build_default_personal_assistant_replay_rollback_witness())
    replay_witness["effect_boundary"]["dispatch_lease_binding_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=replay_witness,
        )

    assert "effect_boundary.dispatch_lease_binding_allowed must be false" in str(exc_info.value)
    assert "dispatch lease" not in str(exc_info.value).lower()


def test_runtime_connector_lease_witness_rejects_dispatch_blocker_drift() -> None:
    replay_witness = build_default_personal_assistant_replay_rollback_witness()
    replay_witness["witnesses"][0]["dispatch_blockers"]["dispatch_lease_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=replay_witness,
        )

    assert "dispatch_blockers.dispatch_lease_present must be false" in str(exc_info.value)
    assert replay_witness["witnesses"][0]["witness_id"] in str(exc_info.value)


def test_runtime_connector_lease_witness_rejects_raw_private_fields_and_secret_values() -> None:
    raw_witness = build_default_personal_assistant_replay_rollback_witness()
    secret_witness = build_default_personal_assistant_replay_rollback_witness()
    raw_witness["witnesses"][0]["raw_connector_witness"] = "private connector payload"
    secret_witness["witnesses"][0]["receipt"]["actions_taken"].append("rotate Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=raw_witness,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_connector_lease_witness_envelope(
            generated_at="2026-06-14T00:07:00+00:00",
            replay_rollback_witness=secret_witness,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private connector payload" not in str(raw_exc.value)
