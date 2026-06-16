"""Tests for personal-assistant component witness collection.

Purpose: prove local component evidence can be collected without enabling
connector, deployment, or assistant execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_component_witness and checked-in
component fixtures.
Invariants:
  - SolvedVerified requires draft-only component and no-effect boundaries.
  - Drifted request paths preserve AwaitingEvidence.
  - Raw private connector payloads are not serialized.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_component_witness import (  # noqa: E402
    DEFAULT_BUNDLE,
    DEFAULT_GRAPH,
    DEFAULT_LIFECYCLE,
    FORBIDDEN_CLAIMS,
    collect_personal_assistant_component_witness,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _write_json(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_component_witness_closes_from_checked_in_component_evidence() -> None:
    receipt = collect_personal_assistant_component_witness(now_utc=FIXED_NOW)
    summary = receipt["summary"]  # type: ignore[index]
    boundary = receipt["effect_boundary"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["component_witness_verified"] is True
    assert summary["request_path_witness_verified"] is True
    assert summary["lifecycle_witness_verified"] is True
    assert boundary["can_call_connector"] is False
    assert boundary["raw_private_connector_payloads_serialized"] is False


def test_component_witness_preserves_awaiting_evidence_when_request_path_drifts(tmp_path: Path) -> None:
    graph = json.loads(DEFAULT_GRAPH.read_text(encoding="utf-8"))
    graph["edges"] = [
        edge
        for edge in graph["edges"]
        if edge.get("edge_id") != "edge.personal_assistant.request_path_next.gmail_account_binding_gate"
    ]
    graph_path = _write_json(tmp_path, "component_graph.json", graph)

    receipt = collect_personal_assistant_component_witness(
        graph_path=graph_path,
        bundle_path=DEFAULT_BUNDLE,
        lifecycle_path=DEFAULT_LIFECYCLE,
        now_utc=FIXED_NOW,
    )

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["witness_closed"] is False  # type: ignore[index]
    assert receipt["request_path_witness"]["inbox_probe_path_bound"] is False  # type: ignore[index]


def test_component_witness_blocks_live_authority_drift(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE.read_text(encoding="utf-8"))
    bundle["can_call_connector"] = True
    bundle["live_connector_send_enabled"] = True
    bundle_path = _write_json(tmp_path, "component_bundle.json", bundle)

    receipt = collect_personal_assistant_component_witness(
        graph_path=DEFAULT_GRAPH,
        bundle_path=bundle_path,
        lifecycle_path=DEFAULT_LIFECYCLE,
        now_utc=FIXED_NOW,
    )
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["no_effect_boundary_verified"] is False  # type: ignore[index]
    assert receipt["effect_boundary"]["can_call_connector"] is True  # type: ignore[index]
    assert receipt["effect_boundary"]["live_connector_send_enabled"] is True  # type: ignore[index]
    assert "access_token" not in serialized
    assert "client_secret" not in serialized


def test_component_witness_cli_writes_closed_receipt(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    output_path = tmp_path / "personal_assistant_component_witness.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["summary"]["witness_closed"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert payload["forbidden_claims_preserved"] == list(FORBIDDEN_CLAIMS)
    assert captured.err == ""
