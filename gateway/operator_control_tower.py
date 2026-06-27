"""Gateway operator control tower foundation.

Purpose: aggregate governed platform read models into one read-only operator
    control tower snapshot.
Governance scope: live runs, approvals, risk, budgets, capabilities, workflows,
    incidents, proof, audit, deployment witness, policy, learning, compliance,
    and commercial signals.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - The tower is observational and side-effect free.
  - Every panel declares its source surface and freshness.
  - Missing or unhealthy panels emit bounded operator signals.
  - Raw tool descriptors and mutable execution handles are never exposed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from html import escape
from typing import Any, Mapping

from gateway.command_spine import canonical_hash


class OperatorPanelKind(StrEnum):
    """Control tower panels expected by enterprise operators."""

    LIVE_RUNS = "live_runs"
    APPROVALS = "approvals"
    RISK_QUEUE = "risk_queue"
    BUDGET_CENTER = "budget_center"
    TENANT_ADMIN = "tenant_admin"
    CAPABILITY_HEALTH = "capability_health"
    WORKFLOW_MONITOR = "workflow_monitor"
    INCIDENT_CENTER = "incident_center"
    PROOF_EXPLORER = "proof_explorer"
    AUDIT_EXPLORER = "audit_explorer"
    DEPLOYMENT_WITNESS = "deployment_witness"
    POLICY_STUDIO = "policy_studio"
    LEARNING_QUEUE = "learning_queue"
    COMPLIANCE_CENTER = "compliance_center"
    COMMERCIAL_CENTER = "commercial_center"


class OperatorSignalSeverity(StrEnum):
    """Operator signal severity."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PanelHealth(StrEnum):
    """Panel health status."""

    OK = "ok"
    DEGRADED = "degraded"
    MISSING = "missing"


_REQUIRED_PANELS = tuple(OperatorPanelKind)
_SENSITIVE_KEYS = frozenset({"raw_tool_surface", "raw_tool_descriptor", "execution_handle", "secret", "credential"})


@dataclass(frozen=True, slots=True)
class OperatorTowerSignal:
    """Bounded operator signal emitted from a panel."""

    signal_id: str
    panel: OperatorPanelKind
    severity: OperatorSignalSeverity
    reason: str
    evidence_refs: tuple[str, ...]
    signal_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.signal_id, "signal_id")
        _require_text(self.reason, "reason")
        if not isinstance(self.panel, OperatorPanelKind):
            raise ValueError("operator_panel_invalid")
        if not isinstance(self.severity, OperatorSignalSeverity):
            raise ValueError("operator_signal_severity_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OperatorTowerPanelState:
    """Read-only panel state for one operator page."""

    panel: OperatorPanelKind
    source_surface: str
    health: PanelHealth
    item_count: int
    freshness_seconds: int
    signal_count: int
    blocked_count: int
    review_count: int
    evidence_refs: tuple[str, ...]
    panel_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.panel, OperatorPanelKind):
            raise ValueError("operator_panel_invalid")
        _require_text(self.source_surface, "source_surface")
        if not isinstance(self.health, PanelHealth):
            raise ValueError("panel_health_invalid")
        for field_name in ("item_count", "freshness_seconds", "signal_count", "blocked_count", "review_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name}_non_negative")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", _redacted_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class OperatorControlTowerSnapshot:
    """Unified operator control tower read model."""

    tower_id: str
    tenant_id: str
    generated_at: str
    panels: tuple[OperatorTowerPanelState, ...]
    signals: tuple[OperatorTowerSignal, ...]
    overall_health: PanelHealth
    panel_count: int
    missing_panel_count: int
    degraded_panel_count: int
    critical_signal_count: int
    raw_tool_surface_exposed: bool
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("tower_id", "tenant_id", "generated_at"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "panels", tuple(self.panels))
        object.__setattr__(self, "signals", tuple(self.signals))
        if self.raw_tool_surface_exposed is not False:
            raise ValueError("raw_tool_surface_must_not_be_exposed")
        if not isinstance(self.overall_health, PanelHealth):
            raise ValueError("panel_health_invalid")
        for field_name in ("panel_count", "missing_panel_count", "degraded_panel_count", "critical_signal_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name}_non_negative")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class OperatorControlTowerBuilder:
    """Build deterministic operator control tower snapshots."""

    def __init__(self, *, tower_id: str = "operator-control-tower") -> None:
        self._tower_id = tower_id
        self._panel_inputs: dict[OperatorPanelKind, Mapping[str, Any]] = {}

    def attach_panel(self, panel: OperatorPanelKind, read_model: Mapping[str, Any]) -> None:
        """Attach one governed read model to a panel."""
        if not isinstance(panel, OperatorPanelKind):
            raise ValueError("operator_panel_invalid")
        self._panel_inputs[panel] = dict(read_model)

    def build(self, *, tenant_id: str, generated_at: str) -> OperatorControlTowerSnapshot:
        """Build a hash-bearing tower snapshot."""
        _require_text(tenant_id, "tenant_id")
        _require_text(generated_at, "generated_at")
        panels: list[OperatorTowerPanelState] = []
        signals: list[OperatorTowerSignal] = []
        for panel in _REQUIRED_PANELS:
            state, panel_signals = self._panel_state(panel)
            panels.append(state)
            signals.extend(panel_signals)
        overall_health = _overall_health(panels, signals)
        snapshot = OperatorControlTowerSnapshot(
            tower_id=self._tower_id,
            tenant_id=tenant_id,
            generated_at=generated_at,
            panels=tuple(panels),
            signals=tuple(signals),
            overall_health=overall_health,
            panel_count=len(panels),
            missing_panel_count=sum(1 for panel in panels if panel.health == PanelHealth.MISSING),
            degraded_panel_count=sum(1 for panel in panels if panel.health == PanelHealth.DEGRADED),
            critical_signal_count=sum(1 for signal in signals if signal.severity == OperatorSignalSeverity.CRITICAL),
            raw_tool_surface_exposed=False,
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _panel_state(self, panel: OperatorPanelKind) -> tuple[OperatorTowerPanelState, tuple[OperatorTowerSignal, ...]]:
        read_model = self._panel_inputs.get(panel)
        if read_model is None:
            signal = _stamp_signal(OperatorTowerSignal(
                signal_id="pending",
                panel=panel,
                severity=OperatorSignalSeverity.WARNING,
                reason="panel_read_model_missing",
                evidence_refs=(),
            ))
            return _stamp_panel(OperatorTowerPanelState(
                panel=panel,
                source_surface=panel.value,
                health=PanelHealth.MISSING,
                item_count=0,
                freshness_seconds=0,
                signal_count=1,
                blocked_count=0,
                review_count=0,
                evidence_refs=(),
                metadata={},
            )), (signal,)

        if _raw_surface_exposed(read_model):
            signal = _stamp_signal(OperatorTowerSignal(
                signal_id="pending",
                panel=panel,
                severity=OperatorSignalSeverity.CRITICAL,
                reason="raw_operator_surface_exposed",
                evidence_refs=(),
            ))
            state = _panel_from_read_model(panel, read_model, health=PanelHealth.DEGRADED, signal_count=1)
            return state, (signal,)

        blocked_count = _int_field(read_model, "blocked_count")
        review_count = _int_field(read_model, "review_count")
        signal_count = _int_field(read_model, "signal_count")
        health = PanelHealth.OK
        signal_items: list[OperatorTowerSignal] = []
        if blocked_count or review_count:
            health = PanelHealth.DEGRADED
            signal_items.append(_stamp_signal(OperatorTowerSignal(
                signal_id="pending",
                panel=panel,
                severity=OperatorSignalSeverity.WARNING,
                reason="operator_review_or_blocked_items_present",
                evidence_refs=_evidence_refs(read_model),
            )))
            signal_count += 1
        state = _panel_from_read_model(panel, read_model, health=health, signal_count=signal_count)
        return state, tuple(signal_items)


def operator_control_tower_snapshot_to_json_dict(snapshot: OperatorControlTowerSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of the tower snapshot."""
    return snapshot.to_json_dict()


def render_operator_control_tower(snapshot: OperatorControlTowerSnapshot) -> str:
    """Render the read-only operator control tower dashboard."""
    payload = snapshot.to_json_dict()
    capability_panel = next(
        (
            panel
            for panel in payload.get("panels", ())
            if isinstance(panel, Mapping) and panel.get("panel") == OperatorPanelKind.CAPABILITY_HEALTH.value
        ),
        {},
    )
    capability_metadata = capability_panel.get("metadata", {}) if isinstance(capability_panel, Mapping) else {}
    if not isinstance(capability_metadata, Mapping):
        capability_metadata = {}
    workflow = capability_metadata.get("developer_workflow_v1", {})
    if not isinstance(workflow, Mapping):
        workflow = {}
    workflow_summary = capability_metadata.get("developer_workflow_summary", {})
    if not isinstance(workflow_summary, Mapping):
        workflow_summary = {}
    workflow_panel = next(
        (
            panel
            for panel in payload.get("panels", ())
            if isinstance(panel, Mapping) and panel.get("panel") == OperatorPanelKind.WORKFLOW_MONITOR.value
        ),
        {},
    )
    workflow_panel_metadata = workflow_panel.get("metadata", {}) if isinstance(workflow_panel, Mapping) else {}
    if not isinstance(workflow_panel_metadata, Mapping):
        workflow_panel_metadata = {}
    workflow_run_summary = workflow_panel_metadata.get("developer_workflow_run", {})
    if not isinstance(workflow_run_summary, Mapping):
        workflow_run_summary = {}
    panel_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(panel.get('panel', '')))}</td>"
        f"<td>{escape(str(panel.get('health', '')))}</td>"
        f"<td>{int(panel.get('item_count', 0) or 0)}</td>"
        f"<td>{int(panel.get('blocked_count', 0) or 0)}</td>"
        f"<td>{int(panel.get('review_count', 0) or 0)}</td>"
        f"<td>{escape(str(panel.get('source_surface', '')))}</td>"
        "</tr>"
        for panel in payload.get("panels", ())
        if isinstance(panel, Mapping)
    )
    signal_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(signal.get('panel', '')))}</td>"
        f"<td>{escape(str(signal.get('severity', '')))}</td>"
        f"<td>{escape(str(signal.get('reason', '')))}</td>"
        "</tr>"
        for signal in payload.get("signals", ())
        if isinstance(signal, Mapping)
    )
    if not signal_rows:
        signal_rows = '<tr><td colspan="3">No operator signals</td></tr>'
    task = str(workflow_summary.get("task") or "Mullu Developer Workflow v1")
    status = str(workflow.get("status") or workflow_summary.get("status") or "")
    reason = str(workflow_summary.get("reason") or "")
    next_unlock = str(workflow.get("next_unlock") or workflow_summary.get("next_unlock") or "")
    risk = str(workflow_summary.get("risk") or "")
    action_needed = str(workflow_summary.get("action_needed") or "")
    workflow_run_status = str(workflow_run_summary.get("status") or "")
    workflow_current_task = str(workflow_run_summary.get("current_task_id") or "")
    workflow_task_count = int(workflow_run_summary.get("task_count", 0) or 0)
    workflow_run_href = str(workflow_panel_metadata.get("developer_workflow_href") or "/operator/developer-workflow")
    workflow_run_read_model_href = str(
        workflow_panel_metadata.get("developer_workflow_read_model_href")
        or "/operator/developer-workflow/read-model"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Operator Control Tower</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; background: #f7f8fa; }}
    main {{ max-width: 1240px; margin: 0 auto; }}
    header, section {{ margin-bottom: 22px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 18px; }}
    a {{ color: #0969da; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .metric {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 8px 10px; background: #fff; }}
    .task {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
    .field {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #fff; }}
    .field strong {{ display: block; font-size: 12px; color: #57606a; margin-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef1f4; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Mullu Operator Control Tower</h1>
    <nav>
      <a href="/operator/control-tower/read-model">json read model</a>
      <a href="/operator/capabilities">capability console</a>
      <a href="/operator/capabilities/friction-control/read-model?domain=software_dev">friction control</a>
      <a href="{escape(workflow_run_href)}">developer workflow</a>
      <a href="/operator/current-task">current task</a>
      <a href="/operator/plan-review">plan review</a>
      <a href="/operator/approvals">approvals</a>
      <a href="/operator/receipts">receipts</a>
    </nav>
    <div class="metrics">
      <span class="metric">Health: {escape(str(payload.get("overall_health", "")))}</span>
      <span class="metric">Panels: {int(payload.get("panel_count", 0) or 0)}</span>
      <span class="metric">Missing: {int(payload.get("missing_panel_count", 0) or 0)}</span>
      <span class="metric">Degraded: {int(payload.get("degraded_panel_count", 0) or 0)}</span>
      <span class="metric">Critical: {int(payload.get("critical_signal_count", 0) or 0)}</span>
    </div>
  </header>
  <section>
    <h2>Developer Workflow</h2>
    <div class="task">
      <span class="field"><strong>Task</strong>{escape(task)}</span>
      <span class="field"><strong>Status</strong>{escape(status)}</span>
      <span class="field"><strong>Reason</strong>{escape(reason)}</span>
      <span class="field"><strong>Next unlock</strong>{escape(next_unlock)}</span>
      <span class="field"><strong>Risk</strong>{escape(risk)}</span>
      <span class="field"><strong>Action needed</strong>{escape(action_needed)}</span>
      <span class="field"><strong>Run status</strong>{escape(workflow_run_status)}</span>
      <span class="field"><strong>Current stage</strong>{escape(workflow_current_task)}</span>
      <span class="field"><strong>Stages</strong>{workflow_task_count}</span>
      <span class="field"><strong>Run receipt</strong><a href="{escape(workflow_run_read_model_href)}">workflow JSON</a></span>
    </div>
  </section>
  <section>
    <h2>Panels</h2>
    <table>
      <thead><tr><th>Panel</th><th>Health</th><th>Items</th><th>Blocked</th><th>Review</th><th>Source</th></tr></thead>
      <tbody>{panel_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Signals</h2>
    <table>
      <thead><tr><th>Panel</th><th>Severity</th><th>Reason</th></tr></thead>
      <tbody>{signal_rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>"""


def _panel_from_read_model(
    panel: OperatorPanelKind,
    read_model: Mapping[str, Any],
    *,
    health: PanelHealth,
    signal_count: int,
) -> OperatorTowerPanelState:
    return _stamp_panel(OperatorTowerPanelState(
        panel=panel,
        source_surface=str(read_model.get("source_surface") or panel.value),
        health=health,
        item_count=_int_field(read_model, "item_count"),
        freshness_seconds=_int_field(read_model, "freshness_seconds"),
        signal_count=signal_count,
        blocked_count=_int_field(read_model, "blocked_count"),
        review_count=_int_field(read_model, "review_count"),
        evidence_refs=_evidence_refs(read_model),
        metadata=dict(read_model.get("metadata") or {}),
    ))


def _overall_health(
    panels: list[OperatorTowerPanelState],
    signals: list[OperatorTowerSignal],
) -> PanelHealth:
    if any(signal.severity == OperatorSignalSeverity.CRITICAL for signal in signals):
        return PanelHealth.DEGRADED
    if any(panel.health == PanelHealth.MISSING for panel in panels):
        return PanelHealth.MISSING
    if any(panel.health == PanelHealth.DEGRADED for panel in panels):
        return PanelHealth.DEGRADED
    return PanelHealth.OK


def _stamp_panel(panel: OperatorTowerPanelState) -> OperatorTowerPanelState:
    payload = panel.to_json_dict()
    payload["panel_hash"] = ""
    return replace(panel, panel_hash=canonical_hash(payload))


def _stamp_signal(signal: OperatorTowerSignal) -> OperatorTowerSignal:
    payload = signal.to_json_dict()
    payload["signal_hash"] = ""
    signal_hash = canonical_hash(payload)
    return replace(signal, signal_id=f"operator-signal-{signal_hash[:16]}", signal_hash=signal_hash)


def _raw_surface_exposed(read_model: Mapping[str, Any]) -> bool:
    if read_model.get("raw_tool_surface_exposed") is True:
        return True
    return any(key in _SENSITIVE_KEYS for key in read_model)


def _redacted_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in dict(metadata).items()
        if str(key) not in _SENSITIVE_KEYS
    }


def _evidence_refs(read_model: Mapping[str, Any]) -> tuple[str, ...]:
    value = read_model.get("evidence_refs") or ()
    if isinstance(value, str):
        value = (value,)
    if not isinstance(value, (list, tuple)):
        return ()
    if not all(isinstance(item, str) for item in value):
        return ()
    return _normalize_text_tuple(tuple(value), "evidence_refs", allow_empty=True)


def _int_field(read_model: Mapping[str, Any], field_name: str) -> int:
    value = int(read_model.get(field_name, 0) or 0)
    return max(0, value)


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"{field_name}_invalid")
    normalized = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
