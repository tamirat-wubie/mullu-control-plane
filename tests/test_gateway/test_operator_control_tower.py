"""Gateway operator control tower tests.

Purpose: verify unified operator panel aggregation, missing-panel signaling,
review/block signaling, raw surface blocking, and schema contract behavior.
Governance scope: read-only operator visibility across production operations.
Dependencies: gateway.operator_control_tower and its public JSON schema.
Invariants:
  - Every required operator panel appears in the snapshot.
  - Missing panels emit bounded warning signals.
  - Raw tool surfaces emit critical signals and remain unexposed.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.operator_control_tower import (
    OperatorControlTowerBuilder,
    OperatorPanelKind,
    OperatorSignalSeverity,
    PanelHealth,
    operator_control_tower_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "operator_control_tower_snapshot.schema.json"
NOW = "2026-05-06T12:00:00Z"


def test_control_tower_builds_all_required_panels_when_sources_are_attached() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    panel_names = {panel.panel for panel in snapshot.panels}

    assert snapshot.panel_count == len(OperatorPanelKind)
    assert panel_names == set(OperatorPanelKind)
    assert snapshot.overall_health is PanelHealth.OK
    assert snapshot.missing_panel_count == 0
    assert snapshot.degraded_panel_count == 0
    assert snapshot.critical_signal_count == 0
    assert snapshot.raw_tool_surface_exposed is False
    assert snapshot.snapshot_hash


def test_missing_panels_emit_bounded_warning_signals() -> None:
    builder = OperatorControlTowerBuilder()
    builder.attach_panel(OperatorPanelKind.LIVE_RUNS, _read_model("runs", item_count=3))
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)

    assert snapshot.overall_health is PanelHealth.MISSING
    assert snapshot.missing_panel_count == len(OperatorPanelKind) - 1
    assert len(snapshot.signals) == len(OperatorPanelKind) - 1
    assert all(signal.severity is OperatorSignalSeverity.WARNING for signal in snapshot.signals)
    assert all(signal.reason == "panel_read_model_missing" for signal in snapshot.signals)


def test_review_and_blocked_items_degrade_panel_and_emit_signal() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.APPROVALS,
        _read_model("approvals", item_count=4, blocked_count=1, review_count=2, evidence_refs=("case:approval-1",)),
    )
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    approvals = next(panel for panel in snapshot.panels if panel.panel is OperatorPanelKind.APPROVALS)
    approval_signal = next(signal for signal in snapshot.signals if signal.panel is OperatorPanelKind.APPROVALS)

    assert snapshot.overall_health is PanelHealth.DEGRADED
    assert snapshot.degraded_panel_count == 1
    assert approvals.health is PanelHealth.DEGRADED
    assert approvals.blocked_count == 1
    assert approvals.review_count == 2
    assert approval_signal.reason == "operator_review_or_blocked_items_present"
    assert "case:approval-1" in approval_signal.evidence_refs


def test_raw_tool_surface_is_not_exposed_and_raises_critical_signal() -> None:
    builder = _full_builder()
    builder.attach_panel(
        OperatorPanelKind.CAPABILITY_HEALTH,
        {
            **_read_model("capability", item_count=7),
            "raw_tool_surface_exposed": True,
            "metadata": {"secret": "redacted", "visible": "yes"},
        },
    )
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    capability = next(panel for panel in snapshot.panels if panel.panel is OperatorPanelKind.CAPABILITY_HEALTH)
    signal = next(signal for signal in snapshot.signals if signal.panel is OperatorPanelKind.CAPABILITY_HEALTH)

    assert snapshot.raw_tool_surface_exposed is False
    assert snapshot.critical_signal_count == 1
    assert snapshot.overall_health is PanelHealth.DEGRADED
    assert capability.health is PanelHealth.DEGRADED
    assert capability.metadata == {"visible": "yes"}
    assert signal.severity is OperatorSignalSeverity.CRITICAL
    assert signal.reason == "raw_operator_surface_exposed"


def test_snapshot_rejects_raw_surface_true() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)

    with pytest.raises(ValueError, match="raw_tool_surface_must_not_be_exposed"):
        type(snapshot)(**{**snapshot.to_json_dict(), "panels": snapshot.panels, "signals": snapshot.signals, "raw_tool_surface_exposed": True})


def test_operator_control_tower_snapshot_schema_exposes_panel_contract() -> None:
    builder = _full_builder()
    snapshot = builder.build(tenant_id="tenant-a", generated_at=NOW)
    payload = operator_control_tower_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:operator-control-tower-snapshot:1"
    assert "approval" not in schema["$defs"]["panel"]["enum"]
    assert "approvals" in schema["$defs"]["panel"]["enum"]
    assert payload["raw_tool_surface_exposed"] is False
    assert snapshot.snapshot_hash


def _full_builder() -> OperatorControlTowerBuilder:
    builder = OperatorControlTowerBuilder()
    for panel in OperatorPanelKind:
        builder.attach_panel(panel, _read_model(panel.value, item_count=1))
    return builder


def _read_model(
    source_surface: str,
    *,
    item_count: int,
    blocked_count: int = 0,
    review_count: int = 0,
    evidence_refs: tuple[str, ...] = ("witness:ok",),
) -> dict[str, object]:
    return {
        "source_surface": source_surface,
        "item_count": item_count,
        "freshness_seconds": 30,
        "signal_count": 0,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "evidence_refs": evidence_refs,
        "raw_tool_surface_exposed": False,
        "metadata": {"owner": "operator"},
    }
