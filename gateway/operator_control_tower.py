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
    return _normalize_text_tuple(tuple(str(item) for item in value), "evidence_refs", allow_empty=True)


def _int_field(read_model: Mapping[str, Any], field_name: str) -> int:
    value = int(read_model.get(field_name, 0) or 0)
    return max(0, value)


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
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
