"""Tests for the nested-mind reconciliation CLI.

Purpose: verify operator reconciliation can append the final P3 readiness
evidence from a stored commit witness.
Governance scope: read-only reconciliation script.
Dependencies: nested_mind_reconcile_observation.py and evidence store.
Invariants: no write connector is used; reconciliation report is appended.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from mcoi_runtime.adapters import JsonConnectorOutcome
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus
from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
)
from mcoi_runtime.persistence import NestedMindEvidenceStore

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nested_mind_reconcile_observation.py"


def _module():
    spec = importlib.util.spec_from_file_location("nested_mind_reconcile_observation", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _clock() -> str:
    return "2026-05-31T00:00:00+00:00"


def _result(result_id: str) -> ConnectorResult:
    return ConnectorResult(
        result_id=result_id,
        connector_id="nested-mind-readonly",
        status=ConnectorStatus.SUCCEEDED,
        response_digest="d" * 64,
        started_at=_clock(),
        finished_at=_clock(),
    )


def _witness() -> NestedMindCommitWitness:
    return NestedMindCommitWitness(
        witness_id="witness-1",
        proposal_evidence_id="evidence-1",
        mind_id="root",
        mullu_receipt_hash="mullu-receipt-hash-1",
        nested_mind_commit_hash="commit-hash-1",
        nested_mind_history_hash="history-hash-1",
        witnessed_at=_clock(),
        status=NestedMindCommitWitnessStatus.VERIFIED,
    )


def test_reconcile_cli_appends_verified_reconciliation(tmp_path, monkeypatch, capsys) -> None:
    module = _module()
    store_path = tmp_path / "evidence.jsonl"
    store = NestedMindEvidenceStore(store_path)
    store.record_commit_witness(_witness())
    monkeypatch.setattr(
        module,
        "mount_nested_mind_connector_from_env",
        lambda **_: FakeBootstrap(FakeReadConnector()),
    )

    exit_code = module.main(
        [
            "--store",
            str(store_path),
            "--plan-id",
            "plan-1",
            "--witness-id",
            "witness-1",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    entries = NestedMindEvidenceStore(store_path).list_by_mind_id("root")

    assert exit_code == 0
    assert output["status"] == "verified"
    assert [entry.record_type for entry in entries] == ["commit_witness", "reconciliation_report"]


class FakeBootstrap:
    def __init__(self, connector: object) -> None:
        self.connector = connector


class FakeReadConnector:
    def read_projection_json(self, mind_id: str) -> JsonConnectorOutcome:
        assert mind_id == "root"
        return JsonConnectorOutcome(
            connector_result=_result("projection-result-1"),
            json_payload={"commit_hash": "commit-hash-1", "history_hash": "history-hash-1"},
        )

    def verify_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        assert mind_id == "root"
        return JsonConnectorOutcome(
            connector_result=_result("audit-result-1"),
            json_payload={"verified_history_hash": "history-hash-1"},
        )

    def replay_history_json(self, mind_id: str) -> JsonConnectorOutcome:
        assert mind_id == "root"
        return JsonConnectorOutcome(
            connector_result=_result("replay-result-1"),
            json_payload={"causal_chain_verified": True},
        )
