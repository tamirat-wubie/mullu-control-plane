"""Forge live-runtime evidence chain read-model validator tests.

Purpose: verify the Forge live-runtime evidence chain is projected read-only
without claiming live evidence, runtime authority, or terminal closure.
Governance scope: read-model stage ordering, source population-gate binding,
authority denial, and fixture drift rejection.
Dependencies: scripts.validate_forge_live_runtime_evidence_chain_read_model.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - The read model remains projection-only.
  - All stages remain AwaitingEvidence.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_evidence_chain_read_model
from scripts.validate_forge_live_runtime_evidence_chain_read_model import (
    DEFAULT_READ_MODEL,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_evidence_chain_read_model,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_evidence_chain_read_model_is_valid() -> None:
    validation, produced_read_model = validate_forge_live_runtime_evidence_chain_read_model()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.read_model_id == "forge-live-runtime-evidence-chain-read-model.v1"
    assert validation.read_model_status == "blocked_awaiting_live_runtime_evidence"
    assert validation.stage_count == 9
    assert validation.blocked_stage_count == 9
    assert produced_read_model["continuation_count"] == 4
    assert produced_read_model["live_evidence_present"] is False
    assert produced_read_model["runtime_authority_effect"] is False


def test_produced_evidence_chain_read_model_matches_schema() -> None:
    read_model = build_foundation_forge_live_runtime_evidence_chain_read_model()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), read_model)

    assert errors == []
    assert read_model["read_model_mode"] == "foundation_live_runtime_evidence_chain_projection"
    assert len(read_model["stage_items"]) == 9
    assert len(read_model["continuation_items"]) == 4
    assert all(item["solver_outcome"] == "AwaitingEvidence" for item in read_model["stage_items"])
    assert all(item["authority_effect"] is False for item in read_model["stage_items"])
    assert all(item["hash_included"] is False for item in read_model["continuation_items"])
    assert all(item["authority_effect"] is False for item in read_model["continuation_items"])


def test_validator_rejects_live_evidence_and_authority_overclaim(tmp_path: Path) -> None:
    read_model = _load_read_model()
    read_model["live_evidence_present"] = True
    read_model["runtime_authority_effect"] = True
    read_model["read_model_status"] = "complete"
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("live_evidence_present" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)
    assert any("read_model_status" in error for error in validation.errors)


def test_validator_rejects_stage_completion_overclaim(tmp_path: Path) -> None:
    read_model = _load_read_model()
    item = read_model["stage_items"][0]
    item["solver_outcome"] = "SolvedVerified"
    item["authority_effect"] = True
    item["artifact_hash"] = ""
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("live_runtime_readiness_gate.solver_outcome" in error for error in validation.errors)
    assert any("live_runtime_readiness_gate.authority_effect" in error for error in validation.errors)
    assert any("live_runtime_readiness_gate.artifact_hash" in error for error in validation.errors)


def test_validator_rejects_order_and_count_drift(tmp_path: Path) -> None:
    read_model = _load_read_model()
    items = read_model["stage_items"]
    read_model["stage_items"] = [items[1], items[0], *items[2:]]
    read_model["stage_count"] = 8
    read_model["blocked_stage_count"] = 8
    continuation_items = read_model["continuation_items"]
    read_model["continuation_items"] = [continuation_items[1], continuation_items[0], *continuation_items[2:]]
    read_model["continuation_count"] = 2
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("stage_items order drift" in error for error in validation.errors)
    assert any("stage_count drift" in error for error in validation.errors)
    assert any("blocked_stage_count drift" in error for error in validation.errors)
    assert any("continuation_items order drift" in error for error in validation.errors)
    assert any("continuation_count drift" in error for error in validation.errors)


def test_validator_rejects_continuation_hash_and_authority_overclaim(tmp_path: Path) -> None:
    read_model = _load_read_model()
    item = read_model["continuation_items"][0]
    item["hash_included"] = True
    item["hash_exclusion_reason"] = "hash_available"
    item["solver_outcome"] = "SolvedVerified"
    item["authority_effect"] = True
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("live_runtime_operator_evidence_request.hash_included" in error for error in validation.errors)
    assert any("live_runtime_operator_evidence_request.hash_exclusion_reason" in error for error in validation.errors)
    assert any("live_runtime_operator_evidence_request.solver_outcome" in error for error in validation.errors)
    assert any("live_runtime_operator_evidence_request.authority_effect" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    read_model = _load_read_model()
    read_model["disallowed_authority"]["state_write_runtime_registered"] = True
    read_model["disallowed_authority"]["commit_allowed"] = True
    read_model["disallowed_authority"]["terminal_closure"] = True
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_source_population_gate_hash_drift(tmp_path: Path) -> None:
    read_model = _load_read_model()
    read_model["source_signed_receipt_population_gate_hash"] = "0" * 64
    read_model_path = _write_read_model(tmp_path, read_model)

    validation, _produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=DEFAULT_SCHEMA,
        read_model_path=read_model_path,
    )

    assert validation.ok is False
    assert any("source_signed_receipt_population_gate_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_read_model() -> dict[str, Any]:
    return json.loads(DEFAULT_READ_MODEL.read_text(encoding="utf-8"))


def _write_read_model(tmp_path: Path, read_model: dict[str, Any]) -> Path:
    read_model_path = tmp_path / "forge_live_runtime_evidence_chain_read_model.foundation.json"
    read_model_path.write_text(json.dumps(read_model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return read_model_path
