"""Tests for typed nested-mind projection import contracts.

Purpose: verify that Phase 2 nested-mind projection import is schema-shaped,
receipt-bound, and still read-only.
Governance scope: Γ projection/audit/replay import validation only; no proposal,
child-mind creation, lawbook mutation, or nested-mind commit-writing authority.
Dependencies: nested_mind contracts and canonical connector result contract.
Invariants: mutation-shaped payloads are rejected, public projections cannot
carry sensitive state keys, imports bind to succeeded connector receipts, and
projection imports do not admit content into memory.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts.nested_mind import (
    NestedMindHistorySurface,
    NestedMindImportStatus,
    NestedMindProjectionEnvelope,
    NestedMindProjectionImportReceipt,
    NestedMindProjectionScope,
    build_nested_mind_projection_import_receipt,
    nested_mind_projection_hash,
    parse_nested_mind_history_payload,
    parse_nested_mind_projection_payload,
)


def _connector_result(status: ConnectorStatus = ConnectorStatus.SUCCEEDED) -> ConnectorResult:
    return ConnectorResult(
        result_id="connector-result-1",
        connector_id="nested-mind-readonly",
        status=status,
        response_digest="a" * 64,
        started_at="2026-05-30T00:00:00+00:00",
        finished_at="2026-05-30T00:00:01+00:00",
    )


def _projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mind_id": "root",
        "scope": "public",
        "sequence": 7,
        "commit_hash": "commit-7",
        "state_hash": "state-7",
        "lawbook_hash": "lawbook-1",
        "history_hash": "history-7",
        "projected_at": "2026-05-30T00:00:00+00:00",
        "state": {"goal": "observe nested symbolic state"},
        "metadata": {"projection_policy": "public"},
    }
    payload.update(overrides)
    return payload


def test_parse_projection_payload_builds_typed_envelope() -> None:
    envelope = parse_nested_mind_projection_payload(_projection_payload())

    assert isinstance(envelope, NestedMindProjectionEnvelope)
    assert envelope.mind_id == "root"
    assert envelope.scope is NestedMindProjectionScope.PUBLIC
    assert envelope.sequence == 7
    assert envelope.commit_hash == "commit-7"
    assert envelope.state["goal"] == "observe nested symbolic state"


def test_projection_hash_is_deterministic_for_equivalent_payloads() -> None:
    first = parse_nested_mind_projection_payload(_projection_payload())
    second = parse_nested_mind_projection_payload(_projection_payload())

    assert nested_mind_projection_hash(first) == nested_mind_projection_hash(second)


def test_public_projection_rejects_sensitive_state_keys() -> None:
    payload = _projection_payload(state={"api_token": "must-not-cross-gamma"})

    with pytest.raises(ValueError, match="sensitive state keys"):
        parse_nested_mind_projection_payload(payload)


def test_internal_projection_may_carry_sensitive_keys_without_public_import() -> None:
    payload = _projection_payload(
        scope="internal",
        state={"api_token": "internal-only"},
    )

    envelope = parse_nested_mind_projection_payload(payload)

    assert envelope.scope is NestedMindProjectionScope.INTERNAL
    assert envelope.state["api_token"] == "internal-only"


def test_projection_payload_rejects_mutation_shape() -> None:
    payload = _projection_payload(patch={"op": "set", "key": "x", "value": 1})

    with pytest.raises(ValueError, match="must not include mutation keys"):
        parse_nested_mind_projection_payload(payload)


def test_projection_import_receipt_binds_to_succeeded_connector_result() -> None:
    envelope = parse_nested_mind_projection_payload(_projection_payload())

    receipt = build_nested_mind_projection_import_receipt(
        envelope,
        connector_result=_connector_result(),
        receipt_id="nested-import-1",
        imported_at="2026-05-30T00:00:02+00:00",
    )

    assert receipt.status is NestedMindImportStatus.ACCEPTED
    assert receipt.connector_result_id == "connector-result-1"
    assert receipt.connector_response_digest == "a" * 64
    assert receipt.projection_hash == nested_mind_projection_hash(envelope)
    assert receipt.admitted_to_memory is False


def test_projection_import_requires_succeeded_connector_result() -> None:
    envelope = parse_nested_mind_projection_payload(_projection_payload())

    with pytest.raises(ValueError, match="must have succeeded"):
        build_nested_mind_projection_import_receipt(
            envelope,
            connector_result=_connector_result(ConnectorStatus.FAILED),
            receipt_id="nested-import-1",
            imported_at="2026-05-30T00:00:02+00:00",
        )


def test_projection_import_receipt_cannot_admit_to_memory() -> None:
    with pytest.raises(ValueError, match="does not admit content into memory"):
        NestedMindProjectionImportReceipt(
            receipt_id="nested-import-1",
            mind_id="root",
            scope=NestedMindProjectionScope.PUBLIC,
            connector_result_id="connector-result-1",
            connector_response_digest="a" * 64,
            projection_hash="projection-hash",
            state_hash="state-7",
            commit_hash="commit-7",
            imported_at="2026-05-30T00:00:02+00:00",
            status=NestedMindImportStatus.ACCEPTED,
            admitted_to_memory=True,
        )


def test_history_payloads_are_typed_without_state_import() -> None:
    envelope = parse_nested_mind_history_payload(
        {
            "mind_id": "root",
            "verified": True,
            "history_hash": "history-7",
            "checked_at": "2026-05-30T00:00:03+00:00",
            "sequence": 7,
        },
        surface=NestedMindHistorySurface.AUDIT,
    )

    assert envelope.surface is NestedMindHistorySurface.AUDIT
    assert envelope.verified is True
    assert envelope.history_hash == "history-7"
    assert envelope.sequence == 7
