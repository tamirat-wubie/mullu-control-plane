"""Tests for Agentic Service Harness read-model persistence rehearsal.

Purpose: verify append-only local persistence for read-only harness read models.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_model_persistence.
Invariants: duplicate records fail closed, hash-chain replay is validated,
secret-like payloads are rejected, and replayed models remain read-only.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_read_model_persistence import (  # noqa: E402
    AppendOnlyHarnessReadModelStore,
    HarnessReadModelPersistenceError,
    DEFAULT_EXAMPLE,
    persist_read_model_records,
    rebuild_read_model,
    validate_agentic_service_harness_read_model_persistence,
    write_agentic_service_harness_read_model_persistence_validation,
)


def _default_read_model() -> dict:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def test_harness_read_model_persistence_accepts_default_rehearsal() -> None:
    validation = validate_agentic_service_harness_read_model_persistence()

    assert validation.ok, validation.errors
    assert validation.example_path == "examples/agentic_service_harness_read_models.foundation.json"
    assert validation.persisted_record_count == validation.replayed_record_count
    assert validation.persisted_record_count == 12
    assert len(validation.chain_head) == 64
    assert validation.duplicate_rejected is True
    assert validation.secret_rejected is True
    assert validation.rebuilt_matches_source is True


def test_harness_read_model_store_replays_source_projection(tmp_path: Path) -> None:
    source = _default_read_model()
    store = AppendOnlyHarnessReadModelStore(tmp_path / "harness-read-models.jsonl")
    persist_read_model_records(source, store, causal_ref="test://source")

    reloaded = AppendOnlyHarnessReadModelStore(tmp_path / "harness-read-models.jsonl")
    rebuilt = rebuild_read_model(reloaded.entries)

    assert len(store.entries) == 12
    assert len(reloaded.entries) == len(store.entries)
    assert reloaded.chain_head == store.chain_head
    assert rebuilt == source
    assert rebuilt["projection_scope"]["read_only"] is True
    assert rebuilt["durable_entity_bindings"]["store_mode"] == "append_only_jsonl_rehearsal"
    assert rebuilt["permission_snapshot"]["can_deploy"] is False


def test_harness_read_model_store_rejects_duplicate_record(tmp_path: Path) -> None:
    source = _default_read_model()
    store = AppendOnlyHarnessReadModelStore(tmp_path / "harness-read-models.jsonl")
    persist_read_model_records(source, store, causal_ref="test://source")
    first_entry_count = len(store.entries)
    scope = source["projection_scope"]

    with pytest.raises(HarnessReadModelPersistenceError, match="duplicate record"):
        store.append(
            record_kind="projection_scope",
            record_id=scope["project_id"],
            tenant_id=scope["tenant_id"],
            project_id=scope["project_id"],
            payload=scope,
            causal_ref="test://duplicate",
        )

    assert first_entry_count == 12
    assert len(store.entries) == first_entry_count
    assert store.chain_head == store.entries[-1]["entry_hash"]


def test_harness_read_model_store_rejects_sensitive_payload(tmp_path: Path) -> None:
    source = _default_read_model()
    scope = source["projection_scope"]
    store = AppendOnlyHarnessReadModelStore(tmp_path / "harness-read-models.jsonl")

    with pytest.raises(HarnessReadModelPersistenceError, match="forbidden sensitive key"):
        store.append(
            record_kind="receipt",
            record_id="receipt.secret",
            tenant_id=scope["tenant_id"],
            project_id=scope["project_id"],
            payload={"receipt_id": "receipt.secret", "access_token": "ghp_forbidden"},
            causal_ref="test://secret",
        )

    assert store.entries == ()
    assert store.chain_head == "GENESIS"
    assert not (tmp_path / "harness-read-models.jsonl").exists()


def test_harness_read_model_store_rejects_corrupted_chain(tmp_path: Path) -> None:
    source = _default_read_model()
    store_path = tmp_path / "harness-read-models.jsonl"
    store = AppendOnlyHarnessReadModelStore(store_path)
    persist_read_model_records(source, store, causal_ref="test://source")
    lines = store_path.read_text(encoding="utf-8").splitlines()
    corrupted = json.loads(lines[1])
    corrupted["previous_entry_hash"] = "wrong"
    lines[1] = json.dumps(corrupted, sort_keys=True, separators=(",", ":"))
    store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(HarnessReadModelPersistenceError, match="previous_entry_hash mismatch"):
        AppendOnlyHarnessReadModelStore(store_path)

    assert len(lines) == 12
    assert corrupted["record_kind"] == "projection_scope"
    assert corrupted["previous_entry_hash"] == "wrong"


def test_harness_read_model_persistence_writer_records_failures(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic_service_harness_read_model_persistence_validation.json"
    validation = validate_agentic_service_harness_read_model_persistence()
    written = write_agentic_service_harness_read_model_persistence_validation(
        validation,
        output_path,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ok"] is True
    assert payload["persisted_record_count"] == 12
    assert payload["duplicate_rejected"] is True
    assert payload["secret_rejected"] is True
