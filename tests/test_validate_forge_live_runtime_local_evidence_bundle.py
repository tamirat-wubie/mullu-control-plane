"""Forge live-runtime local evidence bundle validator tests.

Purpose: verify the Forge live-runtime local evidence bundle remains local
design evidence and cannot claim live runtime closure.
Governance scope: local artifact evidence, live evidence denial, blocker
status, production authority denial, commit denial, and fixture drift.
Dependencies: scripts.validate_forge_live_runtime_local_evidence_bundle.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Live evidence remains not collected.
  - Blockers remain open.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_local_evidence_bundle
from scripts.validate_forge_live_runtime_local_evidence_bundle import (
    DEFAULT_BUNDLE,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_local_evidence_bundle,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_local_evidence_bundle_is_valid() -> None:
    validation, produced_bundle = validate_forge_live_runtime_local_evidence_bundle()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.bundle_id == "forge-live-runtime-local-evidence-bundle.v1"
    assert validation.bundle_status == "local_design_artifacts_available"
    assert validation.local_evidence_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_bundle["solver_outcome"] == "AwaitingEvidence"
    assert produced_bundle["disallowed_authority"]["commit_allowed"] is False


def test_produced_local_evidence_bundle_matches_schema() -> None:
    bundle = build_foundation_forge_live_runtime_local_evidence_bundle()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), bundle)

    assert errors == []
    assert bundle["readiness_status"] == "blocked_awaiting_live_evidence"
    assert len(bundle["local_evidence_items"]) == 10
    assert all(item["live_evidence_status"] == "not_collected" for item in bundle["local_evidence_items"])
    assert all(item["blocker_status"] == "open" for item in bundle["local_evidence_items"])


def test_validator_rejects_live_evidence_overclaim(tmp_path: Path) -> None:
    bundle = _load_bundle()
    bundle["local_evidence_items"][0]["live_evidence_status"] = "collected"
    bundle["local_evidence_items"][0]["blocker_status"] = "closed"
    bundle_path = _write_bundle(tmp_path, bundle)

    validation, _produced_bundle = validate_forge_live_runtime_local_evidence_bundle(
        schema_path=DEFAULT_SCHEMA,
        bundle_path=bundle_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.live_evidence_status" in error for error in validation.errors)
    assert any("managed_key_custody.blocker_status" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    bundle = _load_bundle()
    bundle["disallowed_authority"]["state_write_runtime_registered"] = True
    bundle["disallowed_authority"]["commit_allowed"] = True
    bundle["disallowed_authority"]["terminal_closure"] = True
    bundle_path = _write_bundle(tmp_path, bundle)

    validation, _produced_bundle = validate_forge_live_runtime_local_evidence_bundle(
        schema_path=DEFAULT_SCHEMA,
        bundle_path=bundle_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    bundle = _load_bundle()
    items = bundle["local_evidence_items"]
    bundle["local_evidence_items"] = [items[1], items[0], *items[2:]]
    bundle["blocked_reasons"] = bundle["blocked_reasons"][1:]
    bundle_path = _write_bundle(tmp_path, bundle)

    validation, _produced_bundle = validate_forge_live_runtime_local_evidence_bundle(
        schema_path=DEFAULT_SCHEMA,
        bundle_path=bundle_path,
    )

    assert validation.ok is False
    assert any("local_evidence_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_collection_packet_hash_drift(tmp_path: Path) -> None:
    bundle = _load_bundle()
    bundle["source_collection_packet_hash"] = "0" * 64
    bundle_path = _write_bundle(tmp_path, bundle)

    validation, _produced_bundle = validate_forge_live_runtime_local_evidence_bundle(
        schema_path=DEFAULT_SCHEMA,
        bundle_path=bundle_path,
    )

    assert validation.ok is False
    assert any("source_collection_packet_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_bundle() -> dict[str, Any]:
    return json.loads(DEFAULT_BUNDLE.read_text(encoding="utf-8"))


def _write_bundle(tmp_path: Path, bundle: dict[str, Any]) -> Path:
    bundle_path = tmp_path / "forge_live_runtime_local_evidence_bundle.foundation.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle_path
