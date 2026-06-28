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
_LOCAL_ROLLBACK_FLOW_DRY_RUN_PLACEHOLDER = (
    "python scripts/run_developer_workflow_local_rollback_flow.py "
    "--rollback-summary .change_assurance/developer_workflow_local_rollback_summary_packet.generated.json "
    "--artifact-id <artifact_id> "
    "--approved-by operator "
    "--approval-evidence-ref approval://local/rollback-flow/operator-command "
    "--json"
)
_LOCAL_ROLLBACK_SUMMARY_PACKET_PATH = ".change_assurance/developer_workflow_local_rollback_summary_packet.generated.json"
_LOCAL_ROLLBACK_APPROVAL_PACKET_PATH = ".change_assurance/developer_workflow_local_rollback_approval_packet.generated.json"
_LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH = (
    ".change_assurance/developer_workflow_local_rollback_execution_receipt.generated.json"
)
_LOCAL_ROLLBACK_RECEIPT_HREF_BASE = "/operator/control-tower/local-rollback-receipt"


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


def _bounded_bundle_receipts(receipts: object) -> list[dict[str, Any]]:
    if not isinstance(receipts, list):
        return []
    rows: list[dict[str, Any]] = []
    for receipt in receipts[:8]:
        if not isinstance(receipt, Mapping):
            continue
        rows.append({
            "receipt_id": str(receipt.get("receipt_id") or ""),
            "label": str(receipt.get("label") or ""),
            "status": str(receipt.get("status") or ""),
            "stage": str(receipt.get("stage") or ""),
            "required": receipt.get("required") is True,
            "source": str(receipt.get("source") or ""),
            "evidence_refs": [
                str(ref)
                for ref in receipt.get("evidence_refs", ())
                if str(ref).strip()
            ],
        })
    return rows


def _bounded_attachment_rows(attachments: object) -> list[dict[str, Any]]:
    if not isinstance(attachments, list):
        return []
    rows: list[dict[str, Any]] = []
    for attachment in attachments[:8]:
        if not isinstance(attachment, Mapping):
            continue
        rows.append({
            "receipt_id": str(attachment.get("receipt_id") or ""),
            "label": str(attachment.get("label") or ""),
            "status": str(attachment.get("status") or ""),
            "stage": str(attachment.get("stage") or ""),
            "action": str(attachment.get("action") or ""),
            "source": str(attachment.get("source") or ""),
            "evidence_refs": [
                str(ref)
                for ref in attachment.get("evidence_refs", ())
                if str(ref).strip()
            ],
        })
    return rows


def _bounded_rollback_artifact_rows(artifacts: object) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list):
        return []
    rows: list[dict[str, Any]] = []
    for artifact in artifacts[:32]:
        if not isinstance(artifact, Mapping):
            continue
        rows.append({
            "artifact_id": str(artifact.get("artifact_id") or ""),
            "path": str(artifact.get("path") or ""),
            "rollback_command": str(artifact.get("rollback_command") or ""),
            "required_confirmation": artifact.get("required_confirmation") is True,
        })
    return rows


def _bounded_rollback_approval_artifact_rows(artifacts: object) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list):
        return []
    rows: list[dict[str, Any]] = []
    for artifact in artifacts[:32]:
        if not isinstance(artifact, Mapping):
            continue
        rows.append({
            "artifact_id": str(artifact.get("artifact_id") or ""),
            "path": str(artifact.get("path") or ""),
            "rollback_command": str(artifact.get("rollback_command") or ""),
            "approval_status": str(artifact.get("approval_status") or "pending"),
            "execution_allowed": artifact.get("execution_allowed") is True,
            "required_confirmation": artifact.get("required_confirmation") is True,
        })
    return rows


def _bounded_rollback_execution_artifact_rows(artifacts: object) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list):
        return []
    rows: list[dict[str, Any]] = []
    for artifact in artifacts[:32]:
        if not isinstance(artifact, Mapping):
            continue
        rows.append({
            "artifact_id": str(artifact.get("artifact_id") or ""),
            "path": str(artifact.get("path") or ""),
            "resolved_path": str(artifact.get("resolved_path") or ""),
            "action_status": str(artifact.get("action_status") or "skipped"),
            "path_within_workspace": artifact.get("path_within_workspace") is True,
            "pre_exists": artifact.get("pre_exists") is True,
            "post_exists": artifact.get("post_exists") is True,
            "error_message": str(artifact.get("error_message") or ""),
        })
    return rows


def _local_rollback_receipt_availability_projection(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return bounded availability for the rollback action card receipt links."""

    statuses = {
        "summary": _receipt_availability_status(source.get("summary")),
        "approval": _receipt_availability_status(source.get("approval")),
        "execution": _receipt_availability_status(source.get("execution")),
    }
    return {
        **statuses,
        "available_count": sum(1 for status in statuses.values() if status == "available"),
        "required_count": 3,
    }


def _receipt_availability_status(value: object) -> str:
    status = str(value or "unavailable")
    return status if status in {"available", "unavailable"} else "unavailable"


def _local_rollback_readiness_verdict(value: object) -> str:
    verdict = str(value or "awaiting_selection")
    allowed = {
        "awaiting_selection",
        "awaiting_summary_receipt",
        "awaiting_approval_receipt",
        "ready_for_dry_run",
    }
    return verdict if verdict in allowed else "awaiting_selection"


def operator_control_tower_status_receipt(snapshot: OperatorControlTowerSnapshot) -> dict[str, Any]:
    """Return a compact audit receipt for the current dashboard focus state."""
    payload = snapshot.to_json_dict()
    panels = {
        str(panel.get("panel") or ""): panel
        for panel in payload.get("panels", ())
        if isinstance(panel, Mapping)
    }
    capability_panel = panels.get(OperatorPanelKind.CAPABILITY_HEALTH.value, {})
    workflow_panel = panels.get(OperatorPanelKind.WORKFLOW_MONITOR.value, {})
    capability_metadata = capability_panel.get("metadata", {}) if isinstance(capability_panel, Mapping) else {}
    workflow_metadata = workflow_panel.get("metadata", {}) if isinstance(workflow_panel, Mapping) else {}
    if not isinstance(capability_metadata, Mapping):
        capability_metadata = {}
    if not isinstance(workflow_metadata, Mapping):
        workflow_metadata = {}
    workflow_monitor_summary = workflow_metadata.get("workflow_monitor_summary", {})
    operator_action_card = workflow_metadata.get("operator_action_card", {})
    next_action_summary = workflow_metadata.get("next_action_summary", {})
    approval_readiness_summary = workflow_metadata.get("approval_readiness_summary", {})
    operator_decision_summary = workflow_metadata.get("operator_decision_summary", {})
    friction_reduction_summary = workflow_metadata.get("friction_reduction_summary", {})
    safe_automatic_action_candidates = capability_metadata.get("safe_automatic_action_candidates", ())
    safe_local_action_queue_summary = capability_metadata.get("safe_local_action_queue_summary", {})
    dangerous_zone_blockers = capability_metadata.get("dangerous_zone_blockers", ())
    dangerous_action_blocker_summary = capability_metadata.get("dangerous_action_blocker_summary", {})
    lab_real_world_summary = capability_metadata.get("lab_real_world_summary", {})
    approval_boundary_summary = capability_metadata.get("approval_boundary_summary", {})
    rollback_control_summary = capability_metadata.get("rollback_control_summary", {})
    capability_registry_summary = capability_metadata.get("capability_registry_summary", {})
    friction_mode_summary = capability_metadata.get("friction_mode_summary", {})
    safe_vs_dangerous_summary = capability_metadata.get("safe_vs_dangerous_summary", {})
    unlock_readiness_summary = capability_metadata.get("unlock_readiness_summary", {})
    control_system_summary = capability_metadata.get("control_system_summary", {})
    workflow_summary = capability_metadata.get("developer_workflow_summary", {})
    sandbox_to_pr_packet = workflow_metadata.get("sandbox_to_pr_packet", {})
    sandbox_to_pr_focus = workflow_metadata.get("sandbox_to_pr_focus", {})
    sandbox_to_pr_summary = workflow_metadata.get("sandbox_to_pr_summary", {})
    sandbox_receipt_attachment_packet = workflow_metadata.get("sandbox_receipt_attachment_packet", {})
    sandbox_receipt_attachment_readiness_summary = workflow_metadata.get(
        "sandbox_receipt_attachment_readiness_summary", {}
    )
    local_sandbox_proof_report = workflow_metadata.get("local_sandbox_proof_report", {})
    local_sandbox_proof_readiness_summary = workflow_metadata.get("local_sandbox_proof_readiness_summary", {})
    local_rollback_summary_packet = workflow_metadata.get("local_rollback_summary_packet", {})
    local_rollback_approval_packet = workflow_metadata.get("local_rollback_approval_packet", {})
    local_rollback_execution_receipt = workflow_metadata.get("local_rollback_execution_receipt", {})
    local_rollback_receipts_summary = workflow_metadata.get("local_rollback_receipts_summary", {})
    local_rollback_flow_command = workflow_metadata.get("local_rollback_flow_command", {})
    local_rollback_flow_readiness_summary = workflow_metadata.get("local_rollback_flow_readiness_summary", {})
    pr_readiness_bundle = workflow_metadata.get("pr_readiness_bundle", {})
    pr_readiness_summary = workflow_metadata.get("pr_readiness_summary", {})
    evidence_progress_summary = workflow_metadata.get("evidence_progress_summary", {})
    developer_workflow_operator_receipt = workflow_metadata.get("developer_workflow_operator_receipt", {})
    developer_workflow_operator_receipt_summary = workflow_metadata.get(
        "developer_workflow_operator_receipt_summary", {}
    )
    developer_workflow_run = workflow_metadata.get("developer_workflow_run", {})
    sandbox_receipt_bundle_summary = workflow_metadata.get("sandbox_receipt_bundle_summary", {})
    developer_workflow_readiness_summary = workflow_metadata.get("developer_workflow_readiness_summary", {})
    developer_workflow_milestone_summary = workflow_metadata.get("developer_workflow_milestone_summary", {})
    if not isinstance(workflow_monitor_summary, Mapping):
        workflow_monitor_summary = {}
    if not isinstance(operator_action_card, Mapping):
        operator_action_card = {}
    if not isinstance(next_action_summary, Mapping):
        next_action_summary = {}
    if not isinstance(approval_readiness_summary, Mapping):
        approval_readiness_summary = {}
    if not isinstance(operator_decision_summary, Mapping):
        operator_decision_summary = {}
    if not isinstance(friction_reduction_summary, Mapping):
        friction_reduction_summary = {}
    if not isinstance(safe_automatic_action_candidates, list):
        safe_automatic_action_candidates = []
    if not isinstance(safe_local_action_queue_summary, Mapping):
        safe_local_action_queue_summary = {}
    if not isinstance(dangerous_zone_blockers, list):
        dangerous_zone_blockers = []
    if not isinstance(dangerous_action_blocker_summary, Mapping):
        dangerous_action_blocker_summary = {}
    if not isinstance(lab_real_world_summary, Mapping):
        lab_real_world_summary = {}
    if not isinstance(approval_boundary_summary, Mapping):
        approval_boundary_summary = {}
    if not isinstance(rollback_control_summary, Mapping):
        rollback_control_summary = {}
    if not isinstance(capability_registry_summary, Mapping):
        capability_registry_summary = {}
    if not isinstance(friction_mode_summary, Mapping):
        friction_mode_summary = {}
    if not isinstance(safe_vs_dangerous_summary, Mapping):
        safe_vs_dangerous_summary = {}
    if not isinstance(unlock_readiness_summary, Mapping):
        unlock_readiness_summary = {}
    if not isinstance(control_system_summary, Mapping):
        control_system_summary = {}
    if not isinstance(workflow_summary, Mapping):
        workflow_summary = {}
    if not isinstance(sandbox_to_pr_packet, Mapping):
        sandbox_to_pr_packet = {}
    if not isinstance(sandbox_to_pr_focus, Mapping):
        sandbox_to_pr_focus = {}
    if not isinstance(sandbox_to_pr_summary, Mapping):
        sandbox_to_pr_summary = {}
    if not isinstance(sandbox_receipt_attachment_packet, Mapping):
        sandbox_receipt_attachment_packet = {}
    if not isinstance(sandbox_receipt_attachment_readiness_summary, Mapping):
        sandbox_receipt_attachment_readiness_summary = {}
    if not isinstance(local_sandbox_proof_report, Mapping):
        local_sandbox_proof_report = {}
    if not isinstance(local_sandbox_proof_readiness_summary, Mapping):
        local_sandbox_proof_readiness_summary = {}
    if not isinstance(local_rollback_summary_packet, Mapping):
        local_rollback_summary_packet = {}
    if not isinstance(local_rollback_approval_packet, Mapping):
        local_rollback_approval_packet = {}
    if not isinstance(local_rollback_execution_receipt, Mapping):
        local_rollback_execution_receipt = {}
    if not isinstance(local_rollback_receipts_summary, Mapping):
        local_rollback_receipts_summary = {}
    if not isinstance(local_rollback_flow_command, Mapping):
        local_rollback_flow_command = {}
    if not isinstance(local_rollback_flow_readiness_summary, Mapping):
        local_rollback_flow_readiness_summary = {}
    rollback_receipt_availability = local_rollback_flow_command.get("receipt_availability", {})
    if not isinstance(rollback_receipt_availability, Mapping):
        rollback_receipt_availability = {}
    rollback_selected_artifact_ids = [
        str(item)
        for item in local_rollback_flow_command.get("selected_artifact_ids", ())
        if str(item).strip()
    ][:32]
    if not isinstance(pr_readiness_bundle, Mapping):
        pr_readiness_bundle = {}
    if not isinstance(pr_readiness_summary, Mapping):
        pr_readiness_summary = {}
    if not isinstance(evidence_progress_summary, Mapping):
        evidence_progress_summary = {}
    if not isinstance(developer_workflow_operator_receipt, Mapping):
        developer_workflow_operator_receipt = {}
    if not isinstance(developer_workflow_operator_receipt_summary, Mapping):
        developer_workflow_operator_receipt_summary = {}
    if not isinstance(developer_workflow_run, Mapping):
        developer_workflow_run = {}
    if not isinstance(sandbox_receipt_bundle_summary, Mapping):
        sandbox_receipt_bundle_summary = {}
    if not isinstance(developer_workflow_readiness_summary, Mapping):
        developer_workflow_readiness_summary = {}
    if not isinstance(developer_workflow_milestone_summary, Mapping):
        developer_workflow_milestone_summary = {}
    sandbox_bundle_receipts = developer_workflow_run.get("sandbox_receipt_bundle_receipts", ())
    if not isinstance(sandbox_bundle_receipts, list):
        sandbox_bundle_receipts = []
    sandbox_bundle_next_receipt = next(
        (
            receipt
            for receipt in sandbox_bundle_receipts
            if isinstance(receipt, Mapping) and str(receipt.get("status") or "") != "complete"
        ),
        {},
    )
    if not isinstance(sandbox_bundle_next_receipt, Mapping):
        sandbox_bundle_next_receipt = {}
    sandbox_to_pr_receipts = sandbox_to_pr_packet.get("receipts", {})
    if not isinstance(sandbox_to_pr_receipts, Mapping):
        sandbox_to_pr_receipts = {}
    sandbox_to_pr_approval = sandbox_to_pr_packet.get("approval", {})
    if not isinstance(sandbox_to_pr_approval, Mapping):
        sandbox_to_pr_approval = {}
    sandbox_to_pr_pr_candidate = sandbox_to_pr_packet.get("pr_candidate", {})
    if not isinstance(sandbox_to_pr_pr_candidate, Mapping):
        sandbox_to_pr_pr_candidate = {}
    safe_candidate_count = int(safe_vs_dangerous_summary.get("safe_candidate_count") or len(safe_automatic_action_candidates))
    dangerous_blocker_count = int(
        safe_vs_dangerous_summary.get("dangerous_blocker_count") or len(dangerous_zone_blockers)
    )
    first_dangerous_blocker = dangerous_zone_blockers[0] if dangerous_zone_blockers else {}
    if not isinstance(first_dangerous_blocker, Mapping):
        first_dangerous_blocker = {}
    dangerous_required_evidence = dangerous_action_blocker_summary.get("required_evidence", ())
    if not isinstance(dangerous_required_evidence, list):
        dangerous_required_evidence = []
    dangerous_required_evidence = [
        str(item)
        for item in dangerous_required_evidence
        if str(item).strip()
    ][:8]
    if not dangerous_required_evidence:
        fallback_evidence = first_dangerous_blocker.get("required_evidence", ())
        if isinstance(fallback_evidence, list):
            dangerous_required_evidence = [
                str(item)
                for item in fallback_evidence
                if str(item).strip()
            ][:8]
    safe_vs_dangerous_message = str(
        safe_vs_dangerous_summary.get("operator_message")
        or (
            f"{safe_candidate_count} local-lab candidates available; "
            f"{dangerous_blocker_count} real-world zones blocked pending explicit approval"
        )
    )
    first_safe_candidate = safe_automatic_action_candidates[0] if safe_automatic_action_candidates else {}
    if not isinstance(first_safe_candidate, Mapping):
        first_safe_candidate = {}
    safe_local_queue_count = int(
        safe_local_action_queue_summary.get("candidate_count") or len(safe_automatic_action_candidates)
    )
    safe_local_queue_mode = str(
        safe_local_action_queue_summary.get("recommended_mode")
        or friction_mode_summary.get("foundation_recommended_mode")
        or "fast"
    )
    safe_local_queue_message = str(
        safe_local_action_queue_summary.get("operator_message")
        or (
            f"{safe_local_queue_count} safe local actions queued for {safe_local_queue_mode} mode; "
            "approval not required for local preparation"
        )
    )
    workflow = capability_metadata.get("developer_workflow_v1", {})
    if not isinstance(workflow, Mapping):
        workflow = {}
    lab_safe_candidate_count = int(
        lab_real_world_summary.get("lab_safe_candidate_count") or len(safe_automatic_action_candidates)
    )
    lab_fast_ready_count = int(
        lab_real_world_summary.get("fast_mode_lab_ready_count")
        or capability_metadata.get("fast_mode_lab_ready_count", 0)
        or 0
    )
    lab_dangerous_blocker_count = int(
        lab_real_world_summary.get("dangerous_blocker_count") or len(dangerous_zone_blockers)
    )
    lab_dangerous_approval_count = int(
        lab_real_world_summary.get("dangerous_approval_required_count")
        or sum(
            1
            for item in dangerous_zone_blockers
            if isinstance(item, Mapping) and item.get("approval_required") is True
        )
    )
    lab_real_world_write_status = str(
        lab_real_world_summary.get("real_world_write_status")
        or capability_metadata.get("real_world_write_status")
        or "blocked"
    )
    lab_mode_allowed = lab_real_world_summary.get("lab_mode_allowed")
    if not isinstance(lab_mode_allowed, bool):
        lab_mode_allowed = workflow.get("lab_mode_allowed") is True
    lab_real_world_effects_allowed = lab_real_world_summary.get("real_world_effects_allowed")
    if not isinstance(lab_real_world_effects_allowed, bool):
        lab_real_world_effects_allowed = workflow.get("real_world_effects_allowed") is True
    lab_real_world_message = str(
        lab_real_world_summary.get("operator_message")
        or (
            f"Lab mode can prepare {lab_safe_candidate_count} local candidates; "
            f"real-world writes remain {lab_real_world_write_status}; "
            f"{lab_dangerous_approval_count} dangerous zones need approval"
        )
    )
    next_unlock_queue = capability_metadata.get("next_unlock_queue", ())
    if not isinstance(next_unlock_queue, list):
        next_unlock_queue = []
    approval_local_auto_count = int(
        approval_boundary_summary.get("local_auto_candidate_count") or len(safe_automatic_action_candidates)
    )
    approval_unlock_count = int(
        approval_boundary_summary.get("approval_unlock_count")
        or sum(
            1
            for item in next_unlock_queue
            if isinstance(item, Mapping) and str(item.get("next_unlock") or "") == "approval"
        )
    )
    approval_dangerous_count = int(
        approval_boundary_summary.get("dangerous_approval_required_count")
        or sum(
            1
            for item in dangerous_zone_blockers
            if isinstance(item, Mapping) and item.get("approval_required") is True
        )
    )
    approval_pr_required = approval_boundary_summary.get("pr_approval_required")
    if not isinstance(approval_pr_required, bool):
        approval_pr_required = False
    approval_next_capability_id = str(approval_boundary_summary.get("next_approval_capability_id") or "")
    approval_boundary = str(
        approval_boundary_summary.get("approval_boundary") or "before_pr_or_real_world_effect"
    )
    approval_boundary_message = str(
        approval_boundary_summary.get("operator_message")
        or (
            f"{approval_local_auto_count} local automatic candidates; "
            f"{approval_unlock_count} capability unlocks need approval; "
            f"{approval_dangerous_count} dangerous zones remain approval-bound"
        )
    )
    rollback_summary = capability_metadata.get("rollback_summary", {})
    if not isinstance(rollback_summary, Mapping):
        rollback_summary = {}
    rollback_control_default_count = int(
        rollback_control_summary.get("rollback_default_count")
        or rollback_summary.get("rollback_default_count", 0)
        or 0
    )
    rollback_control_required_count = int(
        rollback_control_summary.get("rollback_required_count")
        or rollback_summary.get("rollback_required_count", 0)
        or 0
    )
    rollback_control_capability_count = int(
        rollback_control_summary.get("capability_count") or capability_panel.get("item_count", 0) or 0
    )
    rollback_control_default_ready = rollback_control_summary.get("rollback_default_ready")
    if not isinstance(rollback_control_default_ready, bool):
        rollback_control_default_ready = (
            rollback_control_default_count > 0
            and rollback_control_default_count >= rollback_control_required_count
        )
    rollback_control_policy_ready = rollback_control_summary.get("sandbox_to_pr_policy_ready")
    if not isinstance(rollback_control_policy_ready, bool):
        rollback_control_policy_ready = False
    rollback_control_policy = str(
        rollback_control_summary.get("rollback_policy")
        or rollback_summary.get("rollback_policy")
        or "If Mullu can change it, Mullu must also know how to undo it."
    )
    rollback_control_receipt_source = str(
        rollback_control_summary.get("rollback_receipt_source")
        or rollback_summary.get("rollback_receipt_source")
        or "developer_workflow_run.software_receipt_binding.stage_evidence.rollback_completed"
    )
    rollback_control_message = str(
        rollback_control_summary.get("operator_message")
        or (
            f"{rollback_control_default_count} capabilities carry rollback default; "
            f"{rollback_control_required_count} unlocks require rollback evidence; "
            "rollback execution remains receipt-bound"
        )
    )
    mode_selector = capability_metadata.get("mode_selector", {})
    if not isinstance(mode_selector, Mapping):
        mode_selector = {}
    mode_summary = mode_selector.get("summary", {})
    if not isinstance(mode_summary, Mapping):
        mode_summary = {}

    def _mode_count(mode: str, key: str) -> int:
        counts = mode_summary.get(mode, {})
        if not isinstance(counts, Mapping):
            return 0
        return int(counts.get(key, 0) or 0)

    friction_default_mode = str(friction_mode_summary.get("default_mode") or mode_selector.get("default_mode") or "balanced")
    friction_recommended_mode = str(
        friction_mode_summary.get("foundation_recommended_mode")
        or mode_selector.get("foundation_recommended_mode")
        or "fast"
    )
    friction_strict_allowed = int(
        friction_mode_summary.get("strict_allowed_count") or _mode_count("strict", "allowed_count")
    )
    friction_strict_approval = int(
        friction_mode_summary.get("strict_approval_required_count")
        or _mode_count("strict", "approval_required_count")
    )
    friction_strict_blocked = int(
        friction_mode_summary.get("strict_blocked_count") or _mode_count("strict", "blocked_count")
    )
    friction_balanced_allowed = int(
        friction_mode_summary.get("balanced_allowed_count") or _mode_count("balanced", "allowed_count")
    )
    friction_balanced_approval = int(
        friction_mode_summary.get("balanced_approval_required_count")
        or _mode_count("balanced", "approval_required_count")
    )
    friction_balanced_blocked = int(
        friction_mode_summary.get("balanced_blocked_count") or _mode_count("balanced", "blocked_count")
    )
    friction_fast_allowed = int(
        friction_mode_summary.get("fast_allowed_count") or _mode_count("fast", "allowed_count")
    )
    friction_fast_approval = int(
        friction_mode_summary.get("fast_approval_required_count") or _mode_count("fast", "approval_required_count")
    )
    friction_fast_blocked = int(
        friction_mode_summary.get("fast_blocked_count") or _mode_count("fast", "blocked_count")
    )
    friction_mode_message = str(
        friction_mode_summary.get("operator_message")
        or (
            f"{friction_recommended_mode} mode recommended for local lab; "
            f"fast allows {friction_fast_allowed} capabilities; "
            f"balanced holds {friction_balanced_approval} approvals"
        )
    )
    registry_required_evidence = capability_registry_summary.get("next_required_evidence", ())
    if not isinstance(registry_required_evidence, list):
        registry_required_evidence = []
    registry_required_evidence = [str(value) for value in registry_required_evidence if str(value).strip()][:8]
    registry_capability_count = int(
        capability_registry_summary.get("capability_count") or capability_panel.get("item_count", 0) or 0
    )
    registry_preflight_ready_count = int(capability_registry_summary.get("preflight_ready_count") or 0)
    registry_blocked_count = int(
        capability_registry_summary.get("blocked_count") or capability_panel.get("blocked_count", 0) or 0
    )
    registry_approval_required_count = int(
        capability_registry_summary.get("approval_required_count") or capability_panel.get("review_count", 0) or 0
    )
    registry_pending_unlock_count = int(
        capability_registry_summary.get("pending_unlock_count") or len(next_unlock_queue)
    )
    registry_next_capability_id = str(capability_registry_summary.get("next_blocked_capability_id") or "")
    registry_next_reason = str(capability_registry_summary.get("next_blocked_reason") or "review")
    registry_message = str(
        capability_registry_summary.get("operator_message")
        or (
            f"{registry_preflight_ready_count} capabilities preflight-ready; "
            f"{registry_blocked_count} capabilities blocked; next evidence is "
            f"{registry_next_reason} for {registry_next_capability_id or 'capability review'}"
        )
    )
    unlock_pending_count = int(unlock_readiness_summary.get("pending_unlock_count") or len(next_unlock_queue))
    unlock_safe_candidate_count = int(
        unlock_readiness_summary.get("safe_candidate_count") or len(safe_automatic_action_candidates)
    )
    unlock_dangerous_blocker_count = int(
        unlock_readiness_summary.get("dangerous_blocker_count") or len(dangerous_zone_blockers)
    )
    unlock_required_evidence = unlock_readiness_summary.get("next_required_evidence", ())
    if not isinstance(unlock_required_evidence, list):
        unlock_required_evidence = []
    unlock_required_evidence = [str(value) for value in unlock_required_evidence if str(value).strip()][:8]
    unlock_approval_blocker_count = int(
        unlock_readiness_summary.get("dangerous_blockers_requiring_approval")
        or sum(
            1
            for item in dangerous_zone_blockers
            if isinstance(item, Mapping) and item.get("approval_required") is True
        )
    )
    unlock_next_capability_id = str(unlock_readiness_summary.get("next_capability_id") or "")
    unlock_next_unlock = str(unlock_readiness_summary.get("next_unlock") or "approval")
    unlock_message = str(
        unlock_readiness_summary.get("operator_message")
        or (
            f"{unlock_pending_count} pending unlocks; next evidence for "
            f"{unlock_next_capability_id or 'capability review'} is {unlock_next_unlock}; "
            f"{unlock_approval_blocker_count} dangerous zones require explicit approval"
        )
    )
    control_required_evidence = control_system_summary.get("next_required_evidence", ())
    if not isinstance(control_required_evidence, list):
        control_required_evidence = []
    control_required_evidence = [str(value) for value in control_required_evidence if str(value).strip()][:8]
    control_message = str(
        control_system_summary.get("operator_message")
        or (
            f"Control system in {friction_recommended_mode} mode; "
            f"{unlock_safe_candidate_count} safe local candidates; next unlock {unlock_next_unlock}"
        )
    )
    next_attachment = sandbox_receipt_attachment_packet.get("next_attachment", {})
    if not isinstance(next_attachment, Mapping):
        next_attachment = {}
    receipt = {
        "receipt_type": "operator_control_tower_status_receipt.v1",
        "tower_id": str(payload.get("tower_id") or ""),
        "tenant_id": str(payload.get("tenant_id") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
        "projection_only": True,
        "external_effects_allowed": False,
        "snapshot_hash": str(payload.get("snapshot_hash") or ""),
        "overall_health": str(payload.get("overall_health") or ""),
        "missing_panel_count": int(payload.get("missing_panel_count", 0) or 0),
        "degraded_panel_count": int(payload.get("degraded_panel_count", 0) or 0),
        "task": str(workflow_summary.get("task") or "Mullu Developer Workflow v1"),
        "status": str(workflow_summary.get("status") or ""),
        "reason": str(workflow_summary.get("reason") or ""),
        "next_unlock": str(workflow_summary.get("next_unlock") or ""),
        "action_needed": str(workflow_summary.get("action_needed") or ""),
        "control_tower_headline_summary": {
            "summary_id": "control_tower_headline.foundation",
            "task": str(control_system_summary.get("task") or "Mullu Developer Workflow v1"),
            "status": str(control_system_summary.get("status") or workflow_summary.get("status") or ""),
            "headline_status": (
                "local_lab_ready"
                if friction_reduction_summary.get("local_continuation_allowed") is True
                else "blocked"
            ),
            "current_milestone": str(
                friction_reduction_summary.get("current_milestone")
                or developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                friction_reduction_summary.get("current_blocker")
                or operator_decision_summary.get("current_blocker")
                or "sandbox_receipts_incomplete"
            ),
            "recommended_mode": str(
                control_system_summary.get("recommended_mode")
                or friction_mode_summary.get("foundation_recommended_mode")
                or "fast"
            ),
            "safe_local_candidate_count": int(
                safe_local_action_queue_summary.get("candidate_count") or len(safe_automatic_action_candidates)
            ),
            "dangerous_blocker_count": int(
                dangerous_action_blocker_summary.get("blocker_count") or len(dangerous_zone_blockers)
            ),
            "local_continuation_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "next_action": str(
                operator_decision_summary.get("recommended_action")
                or next_action_summary.get("primary_action")
                or "inspect workflow receipts"
            ),
            "next_evidence_id": str(
                friction_reduction_summary.get("next_evidence_id")
                or evidence_progress_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "external_effects_allowed": False,
            "operator_message": (
                "Control tower headline: local lab can continue; "
                f"{int(safe_local_action_queue_summary.get('candidate_count') or len(safe_automatic_action_candidates))} "
                "safe local candidates; "
                f"{int(dangerous_action_blocker_summary.get('blocker_count') or len(dangerous_zone_blockers))} "
                "dangerous zones blocked"
            ),
        },
        "local_lab_readiness_summary": {
            "summary_id": "local_lab_readiness.foundation",
            "readiness_status": (
                "awaiting_evidence"
                if int(evidence_progress_summary.get("pending_count") or 0) > 0
                else "ready_to_prepare"
            ),
            "lab_mode_allowed": lab_real_world_summary.get("lab_mode_allowed") is True,
            "local_continuation_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "safe_candidate_count": int(
                safe_local_action_queue_summary.get("candidate_count") or len(safe_automatic_action_candidates)
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "rollback_receipt_available_count": int(
                local_rollback_flow_readiness_summary.get("receipt_available_count") or 0
            ),
            "rollback_receipt_required_count": int(
                local_rollback_flow_readiness_summary.get("receipt_required_count") or 0
            ),
            "rollback_ready": (
                int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
            ),
            "next_action": str(
                operator_decision_summary.get("recommended_action")
                or next_action_summary.get("primary_action")
                or "inspect workflow receipts"
            ),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Local lab readiness awaiting evidence; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending; "
                f"rollback receipts {int(local_rollback_flow_readiness_summary.get('receipt_available_count') or 0)}/"
                f"{int(local_rollback_flow_readiness_summary.get('receipt_required_count') or 0)}"
            ),
        },
        "local_resume_plan_summary": {
            "summary_id": "local_resume_plan.foundation",
            "resume_status": (
                "ready_for_local_continuation"
                if friction_reduction_summary.get("local_continuation_allowed") is True
                else "blocked_pending_approval"
            ),
            "continue_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "recommended_mode": str(
                control_system_summary.get("recommended_mode")
                or friction_mode_summary.get("foundation_recommended_mode")
                or "fast"
            ),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or friction_reduction_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or friction_reduction_summary.get("current_blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                operator_decision_summary.get("recommended_action")
                or next_action_summary.get("primary_action")
                or "inspect workflow receipts"
            ),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "safe_candidate_count": int(
                safe_local_action_queue_summary.get("candidate_count") or len(safe_automatic_action_candidates)
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "rollback_ready": (
                int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
            ),
            "approval_required_now": operator_decision_summary.get("operator_review_required_now") is True,
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Resume plan: continue local lab in "
                f"{str(control_system_summary.get('recommended_mode') or friction_mode_summary.get('foundation_recommended_mode') or 'fast')} mode; "
                f"next evidence {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_action_card": {
            "card_id": str(operator_action_card.get("card_id") or "developer_workflow_next_action"),
            "title": str(operator_action_card.get("title") or "Next developer workflow action"),
            "status": str(
                operator_action_card.get("status")
                or workflow_monitor_summary.get("readiness_status")
                or sandbox_to_pr_packet.get("status")
                or "awaiting_receipts"
            ),
            "reason": str(
                operator_action_card.get("reason")
                or workflow_monitor_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "primary_action": str(
                operator_action_card.get("primary_action")
                or workflow_monitor_summary.get("next_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "primary_href": str(
                operator_action_card.get("primary_href")
                or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
            ),
            "focus_id": str(
                operator_action_card.get("focus_id")
                or sandbox_to_pr_focus.get("focus_id")
                or "sandbox_patch_receipt"
            ),
            "focus_label": str(
                operator_action_card.get("focus_label")
                or sandbox_to_pr_focus.get("label")
                or "Sandbox patch receipt"
            ),
            "focus_status": str(
                operator_action_card.get("focus_status")
                or sandbox_to_pr_focus.get("status")
                or "pending"
            ),
            "task_id": str(
                operator_action_card.get("task_id")
                or workflow_monitor_summary.get("current_task_id")
                or developer_workflow_run.get("current_task_id")
                or ""
            ),
            "risk": str(operator_action_card.get("risk") or "low, local lab only"),
            "execution_boundary": str(
                operator_action_card.get("execution_boundary")
                or workflow_monitor_summary.get("execution_boundary")
                or "local_lab_only"
            ),
            "approval_required": operator_action_card.get("approval_required") is True,
            "external_effects_allowed": False,
        },
        "next_action_summary": {
            "summary_id": str(next_action_summary.get("summary_id") or "next_action.foundation"),
            "status": str(
                next_action_summary.get("status")
                or operator_action_card.get("status")
                or sandbox_to_pr_packet.get("status")
                or "awaiting_receipts"
            ),
            "reason": str(
                next_action_summary.get("reason")
                or operator_action_card.get("reason")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "primary_action": str(
                next_action_summary.get("primary_action")
                or operator_action_card.get("primary_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "primary_href": str(
                next_action_summary.get("primary_href")
                or operator_action_card.get("primary_href")
                or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
            ),
            "focus_id": str(
                next_action_summary.get("focus_id")
                or operator_action_card.get("focus_id")
                or sandbox_to_pr_focus.get("focus_id")
                or "sandbox_patch_receipt"
            ),
            "focus_label": str(
                next_action_summary.get("focus_label")
                or operator_action_card.get("focus_label")
                or sandbox_to_pr_focus.get("label")
                or "Sandbox patch receipt"
            ),
            "focus_status": str(
                next_action_summary.get("focus_status")
                or operator_action_card.get("focus_status")
                or sandbox_to_pr_focus.get("status")
                or "pending"
            ),
            "focus_source": str(next_action_summary.get("focus_source") or sandbox_to_pr_focus.get("source") or ""),
            "required_evidence": [
                str(item)
                for item in next_action_summary.get("required_evidence", ())
                if str(item).strip()
            ][:8],
            "required_evidence_count": int(
                next_action_summary.get("required_evidence_count")
                or len([item for item in next_action_summary.get("required_evidence", ()) if str(item).strip()])
            ),
            "approval_required": (
                next_action_summary.get("approval_required")
                if isinstance(next_action_summary.get("approval_required"), bool)
                else operator_action_card.get("approval_required") is True
            ),
            "risk": str(next_action_summary.get("risk") or "low, local lab only"),
            "operator_message": str(
                next_action_summary.get("operator_message")
                or "Next action inspect workflow receipts; focus sandbox_patch_receipt"
            ),
            "execution_boundary": str(next_action_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "approval_readiness_summary": {
            "summary_id": str(
                approval_readiness_summary.get("summary_id") or "approval_readiness.foundation"
            ),
            "approval_required": (
                approval_readiness_summary.get("approval_required")
                if isinstance(approval_readiness_summary.get("approval_required"), bool)
                else sandbox_to_pr_approval.get("required") is True
            ),
            "operator_approval_status": str(
                approval_readiness_summary.get("operator_approval_status")
                or sandbox_to_pr_approval.get("status")
                or "pending"
            ),
            "approval_missing": (
                approval_readiness_summary.get("approval_missing")
                if isinstance(approval_readiness_summary.get("approval_missing"), bool)
                else sandbox_to_pr_approval.get("status") != "complete"
            ),
            "current_blocker": str(
                approval_readiness_summary.get("current_blocker")
                or sandbox_to_pr_packet.get("blocker")
                or operator_action_card.get("reason")
                or "sandbox_receipts_incomplete"
            ),
            "approval_boundary": str(
                approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "next_approval_action": str(
                approval_readiness_summary.get("next_approval_action")
                or "complete sandbox receipts before requesting approval"
            ),
            "approval_target_href": str(
                approval_readiness_summary.get("approval_target_href")
                or operator_action_card.get("primary_href")
                or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
            ),
            "pr_candidate_status": str(
                approval_readiness_summary.get("pr_candidate_status")
                or sandbox_to_pr_pr_candidate.get("status")
                or "pending"
            ),
            "ready_for_pr_candidate_preparation": (
                approval_readiness_summary.get("ready_for_pr_candidate_preparation")
                if isinstance(approval_readiness_summary.get("ready_for_pr_candidate_preparation"), bool)
                else False
            ),
            "external_pr_execution_allowed": False,
            "operator_message": str(
                approval_readiness_summary.get("operator_message")
                or "Approval pending; sandbox_receipts_incomplete remains current blocker"
            ),
            "execution_boundary": str(approval_readiness_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "operator_decision_summary": {
            "summary_id": str(operator_decision_summary.get("summary_id") or "operator_decision.foundation"),
            "decision_status": str(
                operator_decision_summary.get("decision_status")
                or next_action_summary.get("status")
                or "awaiting_receipts"
            ),
            "decision_kind": str(operator_decision_summary.get("decision_kind") or "evidence_collection"),
            "current_milestone": str(
                operator_decision_summary.get("current_milestone")
                or developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                operator_decision_summary.get("current_blocker")
                or approval_readiness_summary.get("current_blocker")
                or next_action_summary.get("reason")
                or "sandbox_receipts_incomplete"
            ),
            "recommended_action": str(
                operator_decision_summary.get("recommended_action")
                or next_action_summary.get("primary_action")
                or "inspect workflow receipts"
            ),
            "action_href": str(
                operator_decision_summary.get("action_href")
                or next_action_summary.get("primary_href")
                or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
            ),
            "next_evidence_id": str(
                operator_decision_summary.get("next_evidence_id")
                or evidence_progress_summary.get("next_evidence_id")
                or next_action_summary.get("focus_id")
                or "sandbox_patch_receipt"
            ),
            "operator_review_required_now": (
                operator_decision_summary.get("operator_review_required_now")
                if isinstance(operator_decision_summary.get("operator_review_required_now"), bool)
                else False
            ),
            "operator_review_required_before_external_effect": (
                operator_decision_summary.get("operator_review_required_before_external_effect")
                if isinstance(operator_decision_summary.get("operator_review_required_before_external_effect"), bool)
                else approval_readiness_summary.get("approval_required") is True
            ),
            "approval_status": str(
                operator_decision_summary.get("approval_status")
                or approval_readiness_summary.get("operator_approval_status")
                or "pending"
            ),
            "local_continuation_boundary": str(
                operator_decision_summary.get("local_continuation_boundary") or "local_lab_only"
            ),
            "external_effects_allowed": False,
            "operator_message": str(
                operator_decision_summary.get("operator_message")
                or "Decision collect_sandbox_receipts can continue in local lab; approval pending before PR or real-world effect"
            ),
        },
        "friction_reduction_summary": {
            "summary_id": str(
                friction_reduction_summary.get("summary_id") or "friction_reduction.foundation"
            ),
            "reduction_status": str(
                friction_reduction_summary.get("reduction_status")
                or "local_continuation_ready"
            ),
            "current_milestone": str(
                friction_reduction_summary.get("current_milestone")
                or operator_decision_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                friction_reduction_summary.get("current_blocker")
                or operator_decision_summary.get("current_blocker")
                or "sandbox_receipts_incomplete"
            ),
            "local_continuation_allowed": (
                friction_reduction_summary.get("local_continuation_allowed")
                if isinstance(friction_reduction_summary.get("local_continuation_allowed"), bool)
                else operator_decision_summary.get("operator_review_required_now") is not True
            ),
            "pending_evidence_count": int(
                friction_reduction_summary.get("pending_evidence_count")
                or evidence_progress_summary.get("pending_count")
                or 0
            ),
            "next_evidence_id": str(
                friction_reduction_summary.get("next_evidence_id")
                or evidence_progress_summary.get("next_evidence_id")
                or operator_decision_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "operator_review_required_now": (
                friction_reduction_summary.get("operator_review_required_now")
                if isinstance(friction_reduction_summary.get("operator_review_required_now"), bool)
                else operator_decision_summary.get("operator_review_required_now") is True
            ),
            "external_effects_allowed": False,
            "operator_message": str(
                friction_reduction_summary.get("operator_message")
                or (
                    "Friction reduced to collect_sandbox_receipts; continue local evidence collection, "
                    "while PR and real-world effects remain approval-bound"
                )
            ),
        },
        "safe_local_action_queue_summary": {
            "summary_id": str(
                safe_local_action_queue_summary.get("summary_id")
                or "safe_local_action_queue.foundation"
            ),
            "queue_status": str(
                safe_local_action_queue_summary.get("queue_status")
                or ("ready" if safe_local_queue_count else "empty")
            ),
            "candidate_count": safe_local_queue_count,
            "first_candidate_id": str(
                safe_local_action_queue_summary.get("first_candidate_id")
                or first_safe_candidate.get("candidate_id")
                or ""
            ),
            "first_zone": str(
                safe_local_action_queue_summary.get("first_zone")
                or first_safe_candidate.get("zone")
                or ""
            ),
            "first_action": str(
                safe_local_action_queue_summary.get("first_action")
                or first_safe_candidate.get("primary_action")
                or "prepare safe local sandbox work"
            ),
            "recommended_mode": safe_local_queue_mode,
            "approval_required": False,
            "local_execution_boundary": str(
                safe_local_action_queue_summary.get("local_execution_boundary") or "local_lab_only"
            ),
            "external_effects_allowed": False,
            "operator_message": safe_local_queue_message,
        },
        "dangerous_action_blocker_summary": {
            "summary_id": str(
                dangerous_action_blocker_summary.get("summary_id")
                or "dangerous_action_blocker.foundation"
            ),
            "blocker_status": str(
                dangerous_action_blocker_summary.get("blocker_status")
                or ("blocked" if dangerous_blocker_count else "clear")
            ),
            "blocker_count": int(
                dangerous_action_blocker_summary.get("blocker_count") or dangerous_blocker_count
            ),
            "first_blocker_id": str(
                dangerous_action_blocker_summary.get("first_blocker_id")
                or first_dangerous_blocker.get("blocker_id")
                or ""
            ),
            "first_zone": str(
                dangerous_action_blocker_summary.get("first_zone")
                or first_dangerous_blocker.get("zone")
                or ""
            ),
            "first_reason": str(
                dangerous_action_blocker_summary.get("first_reason")
                or first_dangerous_blocker.get("reason")
                or "dangerous_zone_requires_explicit_approval"
            ),
            "required_evidence": dangerous_required_evidence,
            "approval_required": (
                dangerous_action_blocker_summary.get("approval_required")
                if isinstance(dangerous_action_blocker_summary.get("approval_required"), bool)
                else dangerous_blocker_count > 0
            ),
            "rollback_required": (
                dangerous_action_blocker_summary.get("rollback_required")
                if isinstance(dangerous_action_blocker_summary.get("rollback_required"), bool)
                else dangerous_blocker_count > 0
            ),
            "real_world_execution_boundary": str(
                dangerous_action_blocker_summary.get("real_world_execution_boundary") or "real_world"
            ),
            "external_effects_allowed": False,
            "operator_message": str(
                dangerous_action_blocker_summary.get("operator_message")
                or (
                    f"{dangerous_blocker_count} dangerous real-world zones blocked; "
                    "approval, rollback, and effect receipt required before execution"
                )
            ),
        },
        "safe_automatic_action_candidates": [
            {
                "candidate_id": str(item.get("candidate_id") or ""),
                "zone": str(item.get("zone") or ""),
                "title": str(item.get("title") or ""),
                "status": str(item.get("status") or "candidate"),
                "primary_action": str(item.get("primary_action") or ""),
                "primary_href": str(item.get("primary_href") or "/operator/control-tower?domain=software_dev"),
                "risk": str(item.get("risk") or "low, local lab only"),
                "execution_boundary": str(item.get("execution_boundary") or "local_lab_only"),
                "approval_required": item.get("approval_required") is True,
                "external_effects_allowed": False,
            }
            for item in safe_automatic_action_candidates
            if isinstance(item, Mapping)
        ],
        "dangerous_zone_blockers": [
            {
                "blocker_id": str(item.get("blocker_id") or ""),
                "zone": str(item.get("zone") or ""),
                "title": str(item.get("title") or ""),
                "status": str(item.get("status") or "blocked"),
                "reason": str(item.get("reason") or "dangerous_zone_requires_explicit_approval"),
                "required_evidence": [
                    str(value)
                    for value in item.get("required_evidence", ())
                    if str(value).strip()
                ] if isinstance(item.get("required_evidence", ()), list) else [],
                "risk": str(item.get("risk") or "high, real-world boundary"),
                "execution_boundary": str(item.get("execution_boundary") or "real_world"),
                "approval_required": item.get("approval_required") is True,
                "external_effects_allowed": False,
            }
            for item in dangerous_zone_blockers
            if isinstance(item, Mapping)
        ],
        "lab_real_world_summary": {
            "summary_id": str(lab_real_world_summary.get("summary_id") or "lab_real_world.foundation"),
            "lab_mode_allowed": lab_mode_allowed,
            "lab_safe_candidate_count": lab_safe_candidate_count,
            "fast_mode_lab_ready_count": lab_fast_ready_count,
            "real_world_effects_allowed": lab_real_world_effects_allowed,
            "real_world_write_status": lab_real_world_write_status,
            "dangerous_blocker_count": lab_dangerous_blocker_count,
            "dangerous_approval_required_count": lab_dangerous_approval_count,
            "operator_message": lab_real_world_message,
            "lab_execution_boundary": str(lab_real_world_summary.get("lab_execution_boundary") or "local_lab_only"),
            "real_world_execution_boundary": str(
                lab_real_world_summary.get("real_world_execution_boundary") or "real_world"
            ),
            "external_effects_allowed": False,
        },
        "approval_boundary_summary": {
            "summary_id": str(approval_boundary_summary.get("summary_id") or "approval_boundary.foundation"),
            "local_auto_candidate_count": approval_local_auto_count,
            "approval_unlock_count": approval_unlock_count,
            "dangerous_approval_required_count": approval_dangerous_count,
            "pr_approval_required": approval_pr_required,
            "approval_boundary": approval_boundary,
            "next_approval_capability_id": approval_next_capability_id,
            "operator_message": approval_boundary_message,
            "execution_boundary": str(approval_boundary_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "rollback_control_summary": {
            "summary_id": str(rollback_control_summary.get("summary_id") or "rollback_control.foundation"),
            "rollback_default_count": rollback_control_default_count,
            "rollback_required_count": rollback_control_required_count,
            "capability_count": rollback_control_capability_count,
            "rollback_default_ready": rollback_control_default_ready,
            "sandbox_to_pr_policy_ready": rollback_control_policy_ready,
            "rollback_policy": rollback_control_policy,
            "rollback_receipt_source": rollback_control_receipt_source,
            "operator_message": rollback_control_message,
            "execution_boundary": str(rollback_control_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "capability_registry_summary": {
            "summary_id": str(capability_registry_summary.get("summary_id") or "capability_registry.foundation"),
            "capability_count": registry_capability_count,
            "preflight_ready_count": registry_preflight_ready_count,
            "blocked_count": registry_blocked_count,
            "approval_required_count": registry_approval_required_count,
            "pending_unlock_count": registry_pending_unlock_count,
            "next_blocked_capability_id": registry_next_capability_id,
            "next_blocked_reason": registry_next_reason,
            "next_required_evidence": registry_required_evidence,
            "next_required_evidence_count": len(registry_required_evidence),
            "operator_message": registry_message,
            "execution_boundary": str(capability_registry_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "friction_mode_summary": {
            "summary_id": str(friction_mode_summary.get("summary_id") or "friction_mode.foundation"),
            "default_mode": friction_default_mode,
            "foundation_recommended_mode": friction_recommended_mode,
            "strict_allowed_count": friction_strict_allowed,
            "strict_approval_required_count": friction_strict_approval,
            "strict_blocked_count": friction_strict_blocked,
            "balanced_allowed_count": friction_balanced_allowed,
            "balanced_approval_required_count": friction_balanced_approval,
            "balanced_blocked_count": friction_balanced_blocked,
            "fast_allowed_count": friction_fast_allowed,
            "fast_approval_required_count": friction_fast_approval,
            "fast_blocked_count": friction_fast_blocked,
            "operator_message": friction_mode_message,
            "execution_boundary": str(friction_mode_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "safe_vs_dangerous_summary": {
            "summary_id": str(safe_vs_dangerous_summary.get("summary_id") or "safe_vs_dangerous.local_lab"),
            "safe_candidate_count": safe_candidate_count,
            "dangerous_blocker_count": dangerous_blocker_count,
            "first_safe_zone": str(safe_vs_dangerous_summary.get("first_safe_zone") or ""),
            "first_safe_action": str(
                safe_vs_dangerous_summary.get("first_safe_action")
                or "prepare safe local sandbox work"
            ),
            "first_dangerous_zone": str(safe_vs_dangerous_summary.get("first_dangerous_zone") or ""),
            "first_dangerous_reason": str(
                safe_vs_dangerous_summary.get("first_dangerous_reason")
                or "dangerous_zone_requires_explicit_approval"
            ),
            "operator_message": safe_vs_dangerous_message,
            "safe_execution_boundary": str(
                safe_vs_dangerous_summary.get("safe_execution_boundary") or "local_lab_only"
            ),
            "dangerous_execution_boundary": str(
                safe_vs_dangerous_summary.get("dangerous_execution_boundary") or "real_world"
            ),
            "external_effects_allowed": False,
        },
        "unlock_readiness_summary": {
            "summary_id": str(unlock_readiness_summary.get("summary_id") or "unlock_readiness.local_lab"),
            "pending_unlock_count": unlock_pending_count,
            "safe_candidate_count": unlock_safe_candidate_count,
            "dangerous_blocker_count": unlock_dangerous_blocker_count,
            "next_capability_id": unlock_next_capability_id,
            "next_unlock": unlock_next_unlock,
            "next_required_evidence": unlock_required_evidence,
            "next_required_evidence_count": len(unlock_required_evidence),
            "safe_candidates_ready": int(
                unlock_readiness_summary.get("safe_candidates_ready") or len(safe_automatic_action_candidates)
            ),
            "dangerous_blockers_requiring_approval": unlock_approval_blocker_count,
            "operator_message": unlock_message,
            "execution_boundary": str(unlock_readiness_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "control_system_summary": {
            "summary_id": str(control_system_summary.get("summary_id") or "control_system.foundation"),
            "task": str(control_system_summary.get("task") or workflow_summary.get("task") or "Mullu Developer Workflow v1"),
            "status": str(control_system_summary.get("status") or workflow_summary.get("status") or ""),
            "recommended_mode": str(
                control_system_summary.get("recommended_mode") or friction_recommended_mode
            ),
            "lab_mode_allowed": (
                control_system_summary.get("lab_mode_allowed")
                if isinstance(control_system_summary.get("lab_mode_allowed"), bool)
                else lab_mode_allowed
            ),
            "capability_count": int(control_system_summary.get("capability_count") or registry_capability_count),
            "pending_unlock_count": int(control_system_summary.get("pending_unlock_count") or unlock_pending_count),
            "safe_candidate_count": int(control_system_summary.get("safe_candidate_count") or unlock_safe_candidate_count),
            "dangerous_blocker_count": int(
                control_system_summary.get("dangerous_blocker_count") or unlock_dangerous_blocker_count
            ),
            "next_capability_id": str(
                control_system_summary.get("next_capability_id") or unlock_next_capability_id
            ),
            "next_unlock": str(control_system_summary.get("next_unlock") or unlock_next_unlock),
            "next_required_evidence": control_required_evidence or unlock_required_evidence,
            "next_required_evidence_count": int(
                control_system_summary.get("next_required_evidence_count")
                or len(control_required_evidence or unlock_required_evidence)
            ),
            "risk": str(control_system_summary.get("risk") or "low, local lab only"),
            "action_needed": str(
                control_system_summary.get("action_needed")
                or workflow_summary.get("action_needed")
                or "inspect workflow receipts"
            ),
            "operator_message": control_message,
            "execution_boundary": str(control_system_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "workflow_monitor_summary": {
            "monitor_status": str(
                workflow_monitor_summary.get("monitor_status")
                or (
                    "blocked"
                    if int(workflow_panel.get("blocked_count", 0) or 0)
                    else "review"
                    if int(workflow_panel.get("review_count", 0) or 0)
                    else "monitoring"
                )
            ),
            "current_task_id": str(
                workflow_monitor_summary.get("current_task_id")
                or workflow_metadata.get("current_task_id")
                or developer_workflow_run.get("current_task_id")
                or ""
            ),
            "current_task_count": int(
                workflow_monitor_summary.get("current_task_count")
                or workflow_metadata.get("current_task_count")
                or 0
            ),
            "plan_review_count": int(
                workflow_monitor_summary.get("plan_review_count")
                or workflow_metadata.get("plan_review_count")
                or 0
            ),
            "blocked_count": int(
                workflow_monitor_summary.get("blocked_count")
                or workflow_panel.get("blocked_count")
                or 0
            ),
            "review_count": int(
                workflow_monitor_summary.get("review_count")
                or workflow_panel.get("review_count")
                or 0
            ),
            "workflow_status": str(
                workflow_monitor_summary.get("workflow_status")
                or developer_workflow_run.get("status")
                or "waiting_for_approval"
            ),
            "readiness_status": str(
                workflow_monitor_summary.get("readiness_status")
                or sandbox_to_pr_packet.get("status")
                or "awaiting_receipts"
            ),
            "blocker": str(
                workflow_monitor_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                workflow_monitor_summary.get("next_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "execution_boundary": str(
                workflow_monitor_summary.get("execution_boundary")
                or sandbox_to_pr_packet.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "sandbox_to_pr": {
            "status": str(sandbox_to_pr_packet.get("status") or ""),
            "blocker": str(sandbox_to_pr_packet.get("blocker") or ""),
            "next_action": str(sandbox_to_pr_packet.get("next_action") or ""),
            "focus": dict(sandbox_to_pr_focus),
        },
        "sandbox_to_pr_summary": {
            "status": str(
                sandbox_to_pr_summary.get("status")
                or sandbox_to_pr_packet.get("status")
                or "awaiting_receipts"
            ),
            "blocker": str(
                sandbox_to_pr_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "focus_id": str(
                sandbox_to_pr_summary.get("focus_id")
                or sandbox_to_pr_focus.get("focus_id")
                or "sandbox_patch_receipt"
            ),
            "focus_status": str(
                sandbox_to_pr_summary.get("focus_status")
                or sandbox_to_pr_focus.get("status")
                or "pending"
            ),
            "next_action": str(
                sandbox_to_pr_summary.get("next_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "next_evidence_count": int(
                sandbox_to_pr_summary.get("next_evidence_count")
                or len(
                    [
                        item
                        for item in sandbox_to_pr_packet.get("next_evidence", ())
                        if isinstance(item, Mapping)
                    ]
                )
            ),
            "receipt_completed_count": int(
                sandbox_to_pr_summary.get("receipt_completed_count")
                or sandbox_to_pr_receipts.get("completed_count")
                or 0
            ),
            "receipt_required_count": int(
                sandbox_to_pr_summary.get("receipt_required_count")
                or sandbox_to_pr_receipts.get("required_count")
                or 0
            ),
            "operator_approval_status": str(
                sandbox_to_pr_summary.get("operator_approval_status")
                or sandbox_to_pr_approval.get("status")
                or "pending"
            ),
            "pr_candidate_status": str(
                sandbox_to_pr_summary.get("pr_candidate_status")
                or sandbox_to_pr_pr_candidate.get("status")
                or "pending"
            ),
            "execution_boundary": str(
                sandbox_to_pr_summary.get("execution_boundary")
                or sandbox_to_pr_packet.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "pr_readiness": {
            "bundle_id": str(pr_readiness_bundle.get("bundle_id") or "pr_readiness_bundle.v1"),
            "readiness_status": str(pr_readiness_bundle.get("readiness_status") or "awaiting_sandbox_receipts"),
            "ready_for_external_pr_execution": pr_readiness_bundle.get("ready_for_external_pr_execution") is True,
            "first_blocker": str(pr_readiness_bundle.get("first_blocker") or "unknown"),
            "next_evidence": [
                str(item)
                for item in pr_readiness_bundle.get("next_evidence", ())
                if str(item).strip()
            ][:8],
        },
        "pr_readiness_summary": {
            "readiness_status": str(
                pr_readiness_summary.get("readiness_status")
                or pr_readiness_bundle.get("readiness_status")
                or "awaiting_sandbox_receipts"
            ),
            "ready_for_external_pr_execution": (
                pr_readiness_summary.get("ready_for_external_pr_execution") is True
                or pr_readiness_bundle.get("ready_for_external_pr_execution") is True
            ),
            "first_blocker": str(
                pr_readiness_summary.get("first_blocker") or pr_readiness_bundle.get("first_blocker") or "unknown"
            ),
            "next_evidence_count": int(
                pr_readiness_summary.get("next_evidence_count")
                or len([item for item in pr_readiness_bundle.get("next_evidence", ()) if str(item).strip()])
            ),
            "receipt_completed_count": int(
                pr_readiness_summary.get("receipt_completed_count")
                or (
                    pr_readiness_bundle.get("receipt_progress", {}).get("completed_count")
                    if isinstance(pr_readiness_bundle.get("receipt_progress", {}), Mapping)
                    else 0
                )
                or 0
            ),
            "receipt_required_count": int(
                pr_readiness_summary.get("receipt_required_count")
                or (
                    pr_readiness_bundle.get("receipt_progress", {}).get("required_count")
                    if isinstance(pr_readiness_bundle.get("receipt_progress", {}), Mapping)
                    else 0
                )
                or 0
            ),
            "preview_only": (
                pr_readiness_summary.get("preview_only")
                if "preview_only" in pr_readiness_summary
                else pr_readiness_bundle.get("preview_only")
            ) is True,
            "execution_performed": False,
            "external_effects_allowed": False,
            "pr_creation_allowed": False,
            "branch_push_allowed": False,
        },
        "evidence_progress_summary": {
            "summary_id": str(evidence_progress_summary.get("summary_id") or "evidence_progress.foundation"),
            "status": str(evidence_progress_summary.get("status") or "awaiting_evidence"),
            "completed_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or sandbox_receipt_attachment_readiness_summary.get("next_receipt_id")
                or "sandbox_patch_receipt"
            ),
            "next_action": str(
                evidence_progress_summary.get("next_action")
                or sandbox_receipt_attachment_readiness_summary.get("next_action")
                or "inspect workflow receipts"
            ),
            "blocker": str(
                evidence_progress_summary.get("blocker")
                or next_action_summary.get("reason")
                or "sandbox_receipts_incomplete"
            ),
            "sandbox_receipt_completed_count": int(
                evidence_progress_summary.get("sandbox_receipt_completed_count")
                or sandbox_receipt_attachment_readiness_summary.get("completed_count")
                or 0
            ),
            "sandbox_receipt_required_count": int(
                evidence_progress_summary.get("sandbox_receipt_required_count")
                or sandbox_receipt_attachment_readiness_summary.get("required_count")
                or 0
            ),
            "sandbox_bundle_completed_count": int(
                evidence_progress_summary.get("sandbox_bundle_completed_count")
                or sandbox_receipt_bundle_summary.get("completed_count")
                or 0
            ),
            "sandbox_bundle_required_count": int(
                evidence_progress_summary.get("sandbox_bundle_required_count")
                or sandbox_receipt_bundle_summary.get("required_count")
                or 0
            ),
            "rollback_receipt_available_count": int(
                evidence_progress_summary.get("rollback_receipt_available_count")
                or local_rollback_flow_readiness_summary.get("receipt_available_count")
                or 0
            ),
            "rollback_receipt_required_count": int(
                evidence_progress_summary.get("rollback_receipt_required_count")
                or local_rollback_flow_readiness_summary.get("receipt_required_count")
                or 0
            ),
            "pr_next_evidence_count": int(
                evidence_progress_summary.get("pr_next_evidence_count")
                or pr_readiness_summary.get("next_evidence_count")
                or 0
            ),
            "operator_message": str(
                evidence_progress_summary.get("operator_message")
                or "0/0 local evidence receipts complete; next sandbox_patch_receipt"
            ),
            "execution_boundary": str(evidence_progress_summary.get("execution_boundary") or "local_lab_only"),
            "external_effects_allowed": False,
        },
        "developer_workflow_operator_receipt": {
            "receipt_id": str(
                developer_workflow_operator_receipt.get("receipt_id") or "developer_workflow_operator_receipt.v1"
            ),
            "schema_ref": str(
                developer_workflow_operator_receipt.get("schema_ref")
                or "schemas/developer_workflow_operator_receipt.schema.json"
            ),
            "solver_outcome": str(developer_workflow_operator_receipt.get("solver_outcome") or "AwaitingEvidence"),
            "readiness_status": str(
                developer_workflow_operator_receipt.get("readiness_status") or "awaiting_sandbox_receipts"
            ),
            "execution_performed": False,
            "ready_for_external_pr_execution": (
                developer_workflow_operator_receipt.get("ready_for_external_pr_execution") is True
            ),
            "command_preview_rendered": developer_workflow_operator_receipt.get("command_preview_rendered") is True,
            "next_evidence": [
                str(item)
                for item in developer_workflow_operator_receipt.get("next_evidence", ())
                if str(item).strip()
            ][:8],
            "receipt_hash": str(developer_workflow_operator_receipt.get("receipt_hash") or canonical_hash({})),
        },
        "developer_workflow_operator_receipt_summary": {
            "solver_outcome": str(
                developer_workflow_operator_receipt_summary.get("solver_outcome")
                or developer_workflow_operator_receipt.get("solver_outcome")
                or "AwaitingEvidence"
            ),
            "readiness_status": str(
                developer_workflow_operator_receipt_summary.get("readiness_status")
                or developer_workflow_operator_receipt.get("readiness_status")
                or "awaiting_sandbox_receipts"
            ),
            "ready_for_external_pr_execution": (
                developer_workflow_operator_receipt_summary.get("ready_for_external_pr_execution") is True
                or developer_workflow_operator_receipt.get("ready_for_external_pr_execution") is True
            ),
            "command_preview_rendered": (
                developer_workflow_operator_receipt_summary.get("command_preview_rendered") is True
                or developer_workflow_operator_receipt.get("command_preview_rendered") is True
            ),
            "next_evidence_count": int(
                developer_workflow_operator_receipt_summary.get("next_evidence_count")
                or len(
                    [
                        item
                        for item in developer_workflow_operator_receipt.get("next_evidence", ())
                        if str(item).strip()
                    ]
                )
            ),
            "execution_performed": False,
            "external_effects_allowed": False,
        },
        "developer_workflow_readiness_summary": {
            "workflow_status": str(
                developer_workflow_readiness_summary.get("workflow_status")
                or developer_workflow_run.get("status")
                or "waiting_for_approval"
            ),
            "current_task_id": str(
                developer_workflow_readiness_summary.get("current_task_id")
                or developer_workflow_run.get("current_task_id")
                or ""
            ),
            "readiness_status": str(
                developer_workflow_readiness_summary.get("readiness_status")
                or sandbox_to_pr_packet.get("status")
                or "unknown"
            ),
            "packet_status": str(
                developer_workflow_readiness_summary.get("packet_status")
                or sandbox_to_pr_packet.get("status")
                or "unknown"
            ),
            "blocker": str(
                developer_workflow_readiness_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "unknown"
            ),
            "receipt_completed_count": int(
                developer_workflow_readiness_summary.get("receipt_completed_count")
                or sandbox_to_pr_receipts.get("completed_count")
                or developer_workflow_run.get("sandbox_receipt_bundle_completed_count")
                or 0
            ),
            "receipt_required_count": int(
                developer_workflow_readiness_summary.get("receipt_required_count")
                or sandbox_to_pr_receipts.get("required_count")
                or developer_workflow_run.get("sandbox_receipt_bundle_required_count")
                or 0
            ),
            "checklist_completed_required_count": int(
                developer_workflow_readiness_summary.get("checklist_completed_required_count")
                or developer_workflow_run.get("receipt_checklist_completed_required_count")
                or 0
            ),
            "checklist_required_count": int(
                developer_workflow_readiness_summary.get("checklist_required_count")
                or developer_workflow_run.get("receipt_checklist_required_count")
                or 0
            ),
            "operator_approval_status": str(
                developer_workflow_readiness_summary.get("operator_approval_status")
                or sandbox_to_pr_approval.get("status")
                or "pending"
            ),
            "pr_candidate_status": str(
                developer_workflow_readiness_summary.get("pr_candidate_status")
                or sandbox_to_pr_pr_candidate.get("status")
                or "pending"
            ),
            "rollback_receipt_status": str(
                developer_workflow_readiness_summary.get("rollback_receipt_status")
                or developer_workflow_run.get("rollback_receipt_status")
                or "not_recorded"
            ),
            "next_action": str(
                developer_workflow_readiness_summary.get("next_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "execution_boundary": str(
                developer_workflow_readiness_summary.get("execution_boundary")
                or sandbox_to_pr_packet.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "developer_workflow_milestone_summary": {
            "summary_id": str(
                developer_workflow_milestone_summary.get("summary_id")
                or "developer_workflow_milestone.foundation"
            ),
            "workflow_status": str(
                developer_workflow_milestone_summary.get("workflow_status")
                or developer_workflow_readiness_summary.get("workflow_status")
                or developer_workflow_run.get("status")
                or "waiting_for_approval"
            ),
            "readiness_status": str(
                developer_workflow_milestone_summary.get("readiness_status")
                or developer_workflow_readiness_summary.get("readiness_status")
                or sandbox_to_pr_packet.get("status")
                or "awaiting_receipts"
            ),
            "current_task_id": str(
                developer_workflow_milestone_summary.get("current_task_id")
                or developer_workflow_readiness_summary.get("current_task_id")
                or developer_workflow_run.get("current_task_id")
                or ""
            ),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or developer_workflow_readiness_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                developer_workflow_milestone_summary.get("next_action")
                or developer_workflow_readiness_summary.get("next_action")
                or sandbox_to_pr_packet.get("next_action")
                or "inspect workflow receipts"
            ),
            "receipt_completed_count": int(
                developer_workflow_milestone_summary.get("receipt_completed_count")
                or developer_workflow_readiness_summary.get("receipt_completed_count")
                or sandbox_to_pr_receipts.get("completed_count")
                or 0
            ),
            "receipt_required_count": int(
                developer_workflow_milestone_summary.get("receipt_required_count")
                or developer_workflow_readiness_summary.get("receipt_required_count")
                or sandbox_to_pr_receipts.get("required_count")
                or 0
            ),
            "operator_approval_status": str(
                developer_workflow_milestone_summary.get("operator_approval_status")
                or developer_workflow_readiness_summary.get("operator_approval_status")
                or sandbox_to_pr_approval.get("status")
                or "pending"
            ),
            "pr_candidate_status": str(
                developer_workflow_milestone_summary.get("pr_candidate_status")
                or developer_workflow_readiness_summary.get("pr_candidate_status")
                or sandbox_to_pr_pr_candidate.get("status")
                or "pending"
            ),
            "operator_message": str(
                developer_workflow_milestone_summary.get("operator_message")
                or "Developer workflow milestone collect_sandbox_receipts; next action inspect workflow receipts"
            ),
            "execution_boundary": str(
                developer_workflow_milestone_summary.get("execution_boundary")
                or developer_workflow_readiness_summary.get("execution_boundary")
                or sandbox_to_pr_packet.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "developer_workflow_completion_summary": {
            "summary_id": "developer_workflow_completion.foundation",
            "workflow_status": str(
                developer_workflow_milestone_summary.get("workflow_status")
                or developer_workflow_readiness_summary.get("workflow_status")
                or developer_workflow_run.get("status")
                or "waiting_for_approval"
            ),
            "completion_status": (
                "ready_for_external_pr_approval"
                if pr_readiness_bundle.get("ready_for_external_pr_execution") is True
                else (
                    "ready_for_operator_approval"
                    if str(sandbox_to_pr_packet.get("blocker") or "") == "operator_approval_missing"
                    else "awaiting_evidence"
                )
            ),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "progress_percent": (
                int(
                    (
                        int(evidence_progress_summary.get("completed_count") or 0)
                        / int(evidence_progress_summary.get("required_count") or 1)
                    )
                    * 100
                )
                if int(evidence_progress_summary.get("required_count") or 0) > 0
                else 0
            ),
            "next_closure_condition": (
                "complete local evidence receipts before approval"
                if int(evidence_progress_summary.get("pending_count") or 0) > 0
                else "request operator approval before PR preparation"
            ),
            "terminal_closure_ready": False,
            "pr_creation_allowed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                f"Developer Workflow completion "
                f"{int(evidence_progress_summary.get('completed_count') or 0)}/"
                f"{int(evidence_progress_summary.get('required_count') or 0)} evidence receipts; "
                f"next closure condition "
                f"{'complete local evidence receipts before approval' if int(evidence_progress_summary.get('pending_count') or 0) > 0 else 'request operator approval before PR preparation'}"
            ),
        },
        "operator_terminal_closure_summary": {
            "summary_id": "operator_terminal_closure.foundation",
            "terminal_status": (
                "ready_for_terminal_review"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "AwaitingEvidence"
            ),
            "closure_ready": False,
            "workflow_status": str(
                developer_workflow_milestone_summary.get("workflow_status")
                or developer_workflow_readiness_summary.get("workflow_status")
                or developer_workflow_run.get("status")
                or "waiting_for_approval"
            ),
            "completion_status": (
                "ready_for_external_pr_approval"
                if pr_readiness_bundle.get("ready_for_external_pr_execution") is True
                else (
                    "ready_for_operator_approval"
                    if str(sandbox_to_pr_packet.get("blocker") or "") == "operator_approval_missing"
                    else "awaiting_evidence"
                )
            ),
            "current_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "review_ready": int(evidence_progress_summary.get("pending_count") or 0) == 0,
            "approval_status": str(
                operator_decision_summary.get("approval_status")
                or approval_readiness_summary.get("operator_approval_status")
                or "pending"
            ),
            "rollback_ready": (
                int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
            ),
            "pr_creation_allowed": False,
            "branch_push_allowed": False,
            "next_closure_condition": (
                "complete local evidence receipts before approval"
                if int(evidence_progress_summary.get("pending_count") or 0) > 0
                else "request operator approval before PR preparation"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Terminal closure AwaitingEvidence; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_resume_checkpoint_summary": {
            "summary_id": "operator_resume_checkpoint.foundation",
            "checkpoint_status": (
                "ready_for_local_resume"
                if friction_reduction_summary.get("local_continuation_allowed") is True
                else "blocked_pending_approval"
            ),
            "resume_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "terminal_status": (
                "ready_for_terminal_review"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "AwaitingEvidence"
            ),
            "recommended_mode": str(
                control_system_summary.get("recommended_mode")
                or friction_mode_summary.get("foundation_recommended_mode")
                or "fast"
            ),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or friction_reduction_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or friction_reduction_summary.get("current_blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                operator_decision_summary.get("recommended_action")
                or next_action_summary.get("primary_action")
                or "inspect workflow receipts"
            ),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "rollback_ready": (
                int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
            ),
            "approval_required_now": operator_decision_summary.get("operator_review_required_now") is True,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Resume checkpoint ready for local lab; "
                f"next evidence {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_sandbox_milestone_summary": {
            "summary_id": "operator_sandbox_milestone.foundation",
            "milestone_status": (
                "ready_for_review"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "awaiting_receipts"
            ),
            "milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or friction_reduction_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "next_action": str(
                evidence_progress_summary.get("next_action")
                or operator_decision_summary.get("recommended_action")
                or "complete sandbox patch, test, diff, and terminal receipts"
            ),
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "required_receipts": [
                "sandbox_patch_receipt",
                "sandbox_test_receipt",
                "sandbox_diff_receipt",
                "dry_run_receipt",
                "rollback_plan_receipt",
                "terminal_review_receipt",
                "operator_approval_packet_receipt",
            ],
            "write_authority_granted": False,
            "pr_creation_allowed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox milestone awaiting receipts; "
                f"next evidence {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_sandbox_receipt_checklist_summary": {
            "summary_id": "operator_sandbox_receipt_checklist.foundation",
            "checklist_status": (
                "complete"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "incomplete"
            ),
            "next_receipt_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "next_receipt_action": str(
                evidence_progress_summary.get("next_action")
                or "attach before state, after state, diff, command, and rollback receipt"
            ),
            "completed_receipt_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_receipt_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_receipt_count": int(evidence_progress_summary.get("pending_count") or 0),
            "receipt_sequence": [
                "sandbox_patch_receipt",
                "sandbox_test_receipt",
                "sandbox_diff_receipt",
                "dry_run_receipt",
                "rollback_plan_receipt",
                "terminal_review_receipt",
                "operator_approval_packet_receipt",
            ],
            "terminal_review_allowed": int(evidence_progress_summary.get("pending_count") or 0) == 0,
            "write_authority_granted": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox checklist incomplete; "
                f"next receipt {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} receipts pending"
            ),
        },
        "operator_sandbox_patch_receipt_summary": {
            "summary_id": "operator_sandbox_patch_receipt.foundation",
            "receipt_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or sandbox_receipt_attachment_readiness_summary.get("next_receipt_id")
                or "sandbox_patch_receipt"
            ),
            "receipt_status": str(
                sandbox_receipt_attachment_readiness_summary.get("next_status")
                or "awaiting_attachment"
            ),
            "required_parts": [
                "before_state",
                "after_state",
                "diff",
                "command",
                "rollback_command",
                "evidence_ref",
            ],
            "next_action": str(
                sandbox_receipt_attachment_readiness_summary.get("next_action")
                or evidence_progress_summary.get("next_action")
                or "attach before state, after state, diff, command, and rollback receipt"
            ),
            "rollback_required": True,
            "dry_run_required": True,
            "write_authority_granted": False,
            "attachment_allowed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch receipt awaiting attachment; required parts before_state, "
                "after_state, diff, command, rollback_command, evidence_ref"
            ),
        },
        "operator_sandbox_patch_command_summary": {
            "summary_id": "operator_sandbox_patch_command.foundation",
            "command_status": "preview_only",
            "receipt_id": "sandbox_patch_receipt",
            "command": (
                "python scripts/collect_developer_workflow_sandbox_receipt_evidence.py "
                "--receipt-id sandbox_patch_receipt "
                "--before-file .change_assurance/before.txt "
                "--after-file .change_assurance/after.txt "
                "--diff-file .change_assurance/sandbox_patch.diff "
                "--command \"apply_patch\" "
                "--rollback-command \"git apply -R .change_assurance/sandbox_patch.diff\" "
                "--evidence-ref proof://developer-workflow-v1/sandbox-patch"
            ),
            "expected_inputs": [
                ".change_assurance/before.txt",
                ".change_assurance/after.txt",
                ".change_assurance/sandbox_patch.diff",
            ],
            "expected_output": "developer_workflow_sandbox_receipt_bundle.collected.json",
            "execution_performed": False,
            "attachment_performed": False,
            "write_authority_granted": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch command preview ready; execution and attachment remain operator-controlled"
            ),
        },
        "operator_sandbox_patch_bundle_preview_summary": {
            "summary_id": "operator_sandbox_patch_bundle_preview.foundation",
            "bundle_status": "preview_only",
            "bundle_path": "developer_workflow_sandbox_receipt_bundle.collected.json",
            "included_receipt_ids": ["sandbox_patch_receipt"],
            "validation_command": (
                "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
                "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
            ),
            "bundle_generation_performed": False,
            "validation_performed": False,
            "attachment_performed": False,
            "write_authority_granted": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch bundle preview ready; bundle generation and validation not executed"
            ),
        },
        "operator_sandbox_patch_validation_readiness_summary": {
            "summary_id": "operator_sandbox_patch_validation_readiness.foundation",
            "validation_status": "blocked_missing_bundle",
            "bundle_path": "developer_workflow_sandbox_receipt_bundle.collected.json",
            "validator_command": (
                "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
                "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
            ),
            "required_before_validation": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
            ],
            "missing_prerequisite_count": 2,
            "validation_performed": False,
            "terminal_review_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch validation blocked until the collected bundle exists and receipt is attached"
            ),
        },
        "operator_sandbox_patch_terminal_review_summary": {
            "summary_id": "operator_sandbox_patch_terminal_review.foundation",
            "review_status": "blocked_until_validation",
            "review_target": "sandbox_patch_receipt",
            "required_before_review": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
            ],
            "missing_prerequisite_count": 3,
            "review_command": (
                "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
                "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
            ),
            "review_performed": False,
            "approval_request_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch terminal review blocked until bundle generation, attachment, and validation complete"
            ),
        },
        "operator_sandbox_patch_approval_readiness_summary": {
            "summary_id": "operator_sandbox_patch_approval_readiness.foundation",
            "approval_status": "blocked_until_terminal_review",
            "approval_target": "sandbox_patch_receipt",
            "required_before_approval": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
                "sandbox_patch_terminal_review_complete",
            ],
            "missing_prerequisite_count": 4,
            "approval_request_allowed": False,
            "approval_request_performed": False,
            "pr_preparation_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch approval blocked until terminal review closes with validated evidence"
            ),
        },
        "operator_sandbox_patch_pr_preparation_readiness_summary": {
            "summary_id": "operator_sandbox_patch_pr_preparation_readiness.foundation",
            "preparation_status": "blocked_until_approval",
            "preparation_target": "local_pr_candidate_packet",
            "required_before_preparation": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
                "sandbox_patch_terminal_review_complete",
                "operator_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "preparation_performed": False,
            "pr_preparation_allowed": False,
            "branch_push_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR preparation blocked until sandbox patch approval is recorded with validated evidence"
            ),
        },
        "operator_sandbox_patch_pr_creation_readiness_summary": {
            "summary_id": "operator_sandbox_patch_pr_creation_readiness.foundation",
            "creation_status": "blocked_until_pr_preparation",
            "creation_target": "github_pull_request",
            "required_before_creation": [
                "local_pr_candidate_packet_prepared",
                "local_pr_candidate_packet_validated",
                "external_pr_execution_approval_recorded",
                "branch_push_authority_bound",
                "github_pr_admission_passed",
            ],
            "missing_prerequisite_count": 5,
            "creation_performed": False,
            "branch_push_allowed": False,
            "pr_creation_allowed": False,
            "connector_call_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR creation blocked until local PR preparation and external PR approval evidence are complete"
            ),
        },
        "operator_sandbox_patch_pr_ci_readiness_summary": {
            "summary_id": "operator_sandbox_patch_pr_ci_readiness.foundation",
            "ci_status": "blocked_until_pr_creation",
            "ci_target": "github_pr_ci_checks",
            "required_before_ci": [
                "github_pull_request_created",
                "pr_metadata_packet_recorded",
                "ci_gate_before_ready_for_review_witness_bound",
                "github_check_read_authority_bound",
                "pr_effect_reconciliation_pending",
            ],
            "missing_prerequisite_count": 5,
            "ci_observation_performed": False,
            "github_poll_allowed": False,
            "check_update_allowed": False,
            "ready_for_review_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR CI readiness blocked until PR creation evidence and CI observation authority are complete"
            ),
        },
        "operator_sandbox_patch_merge_readiness_summary": {
            "summary_id": "operator_sandbox_patch_merge_readiness.foundation",
            "merge_status": "blocked_until_ci_pass",
            "merge_target": "protected_branch_merge",
            "required_before_merge": [
                "github_pull_request_created",
                "ci_checks_passed",
                "review_approval_recorded",
                "rollback_plan_verified",
                "merge_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "merge_performed": False,
            "merge_allowed": False,
            "branch_write_allowed": False,
            "github_call_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Merge readiness blocked until CI pass, review approval, rollback, and merge approval evidence are complete"
            ),
        },
        "operator_sandbox_patch_release_handoff_readiness_summary": {
            "summary_id": "operator_sandbox_patch_release_handoff_readiness.foundation",
            "handoff_status": "blocked_until_terminal_closure",
            "handoff_target": "release_handoff_packet",
            "required_before_handoff": [
                "merge_execution_receipt_recorded",
                "terminal_closure_certificate_minted",
                "effect_reconciliation_witness_bound",
                "rollback_retention_verified",
                "release_notes_prepared",
            ],
            "missing_prerequisite_count": 5,
            "handoff_performed": False,
            "release_publication_allowed": False,
            "deployment_allowed": False,
            "public_claim_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Release handoff blocked until terminal closure, reconciliation, rollback, and release-note evidence are complete"
            ),
        },
        "operator_sandbox_patch_deployment_publication_readiness_summary": {
            "summary_id": "operator_sandbox_patch_deployment_publication_readiness.foundation",
            "publication_status": "blocked_until_release_handoff",
            "publication_target": "deployment_publication_closure_plan",
            "required_before_publication": [
                "release_handoff_packet_prepared",
                "deployment_publication_closure_plan_verified",
                "production_evidence_witness_bound",
                "dns_target_binding_verified",
                "operator_deployment_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "publication_performed": False,
            "deployment_allowed": False,
            "dns_change_allowed": False,
            "production_claim_allowed": False,
            "public_endpoint_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Deployment publication blocked until release handoff, production evidence, DNS binding, and deployment approval evidence are complete"
            ),
        },
        "operator_sandbox_patch_production_monitoring_readiness_summary": {
            "summary_id": "operator_sandbox_patch_production_monitoring_readiness.foundation",
            "monitoring_status": "blocked_until_publication",
            "monitoring_target": "production_monitoring_witness",
            "required_before_monitoring": [
                "deployment_publication_witness_recorded",
                "public_health_witness_bound",
                "runtime_conformance_certificate_available",
                "telemetry_monitoring_plan_verified",
                "incident_rollback_recovery_plan_verified",
            ],
            "missing_prerequisite_count": 5,
            "monitoring_activation_performed": False,
            "monitor_activation_allowed": False,
            "alert_routing_allowed": False,
            "production_claim_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Production monitoring blocked until deployment publication, health, runtime conformance, telemetry, and incident recovery evidence are complete"
            ),
        },
        "operator_sandbox_patch_incident_response_readiness_summary": {
            "summary_id": "operator_sandbox_patch_incident_response_readiness.foundation",
            "incident_status": "blocked_until_monitoring",
            "incident_target": "incident_response_runbook",
            "required_before_incident_response": [
                "production_monitoring_witness_recorded",
                "incident_response_runbook_verified",
                "rollback_execution_receipt_template_bound",
                "containment_evidence_contract_bound",
                "operator_incident_authority_recorded",
            ],
            "missing_prerequisite_count": 5,
            "incident_response_performed": False,
            "containment_allowed": False,
            "rollback_execution_allowed": False,
            "paging_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Incident response blocked until monitoring, runbook, rollback, containment, and operator authority evidence are complete"
            ),
        },
        "operator_sandbox_patch_recovery_closure_readiness_summary": {
            "summary_id": "operator_sandbox_patch_recovery_closure_readiness.foundation",
            "recovery_status": "blocked_until_incident_response",
            "recovery_target": "recovery_closure_packet",
            "required_before_recovery_closure": [
                "incident_containment_evidence_recorded",
                "rollback_or_replay_receipt_recorded",
                "post_incident_verification_passed",
                "operator_recovery_closure_approval_recorded",
                "terminal_recovery_closure_packet_prepared",
            ],
            "missing_prerequisite_count": 5,
            "recovery_closure_performed": False,
            "closure_certification_allowed": False,
            "replay_promotion_allowed": False,
            "post_incident_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Recovery closure blocked until containment, rollback or replay, verification, approval, and terminal recovery packet evidence are complete"
            ),
        },
        "operator_sandbox_patch_trust_ledger_readiness_summary": {
            "summary_id": "operator_sandbox_patch_trust_ledger_readiness.foundation",
            "ledger_status": "blocked_until_recovery_closure",
            "ledger_target": "trust_ledger_anchor_packet",
            "required_before_trust_ledger_anchor": [
                "terminal_recovery_closure_packet_prepared",
                "trust_ledger_bundle_export_prepared",
                "evidence_artifact_hashes_recorded",
                "operator_trust_ledger_anchor_approval_recorded",
                "remote_submission_preflight_passed",
            ],
            "missing_prerequisite_count": 5,
            "ledger_anchor_performed": False,
            "remote_submission_allowed": False,
            "verification_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Trust ledger anchoring blocked until recovery closure, export, hash, approval, and remote submission preflight evidence are complete"
            ),
        },
        "operator_sandbox_patch_terminal_audit_export_readiness_summary": {
            "summary_id": "operator_sandbox_patch_terminal_audit_export_readiness.foundation",
            "audit_export_status": "blocked_until_trust_ledger_anchor",
            "audit_export_target": "terminal_audit_export_package",
            "required_before_terminal_audit_export": [
                "trust_ledger_anchor_receipt_recorded",
                "trust_ledger_anchor_verification_passed",
                "audit_bundle_integrity_report_recorded",
                "operator_audit_export_approval_recorded",
                "export_retention_boundary_verified",
            ],
            "missing_prerequisite_count": 5,
            "audit_export_performed": False,
            "archive_submission_allowed": False,
            "external_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Terminal audit export blocked until trust ledger anchor, verification, integrity, approval, and retention evidence are complete"
            ),
        },
        "operator_sandbox_patch_foundation_closure_readiness_summary": {
            "summary_id": "operator_sandbox_patch_foundation_closure_readiness.foundation",
            "foundation_closure_status": "blocked_until_terminal_audit_export",
            "foundation_closure_target": "foundation_closure_certificate",
            "required_before_foundation_closure": [
                "terminal_audit_export_package_prepared",
                "operator_final_closure_approval_recorded",
                "all_no_effect_denials_preserved",
                "open_gap_register_reviewed",
                "next_iteration_handoff_recorded",
            ],
            "missing_prerequisite_count": 5,
            "foundation_closure_certified": False,
            "promotion_allowed": False,
            "handoff_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Foundation closure blocked until terminal audit export, final approval, denial preservation, gap review, and next-iteration handoff evidence are complete"
            ),
        },
        "operator_sandbox_patch_iteration_resume_readiness_summary": {
            "summary_id": "operator_sandbox_patch_iteration_resume_readiness.foundation",
            "iteration_resume_status": "blocked_until_foundation_closure",
            "iteration_resume_target": "next_iteration_intake_packet",
            "required_before_iteration_resume": [
                "foundation_closure_certificate_recorded",
                "next_iteration_scope_declared",
                "next_iteration_risk_boundary_reviewed",
                "next_iteration_evidence_queue_seeded",
                "operator_resume_intent_recorded",
            ],
            "missing_prerequisite_count": 5,
            "next_iteration_started": False,
            "automatic_resume_allowed": False,
            "authority_carryover_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Iteration resume blocked until foundation closure, next scope, risk boundary, evidence queue, and operator resume intent evidence are complete"
            ),
        },
        "operator_sandbox_patch_next_scope_admission_readiness_summary": {
            "summary_id": "operator_sandbox_patch_next_scope_admission_readiness.foundation",
            "next_scope_admission_status": "blocked_until_iteration_resume",
            "next_scope_target": "next_scope_admission_packet",
            "required_before_next_scope_admission": [
                "next_iteration_intake_packet_prepared",
                "next_scope_boundaries_declared",
                "next_scope_acceptance_criteria_recorded",
                "next_scope_risk_review_recorded",
                "next_scope_rollback_expectations_recorded",
            ],
            "missing_prerequisite_count": 5,
            "scope_admitted": False,
            "execution_allowed": False,
            "authority_promotion_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Next scope admission blocked until intake, boundaries, acceptance criteria, risk review, and rollback expectation evidence are complete"
            ),
        },
        "operator_handoff_summary": {
            "summary_id": "operator_handoff.foundation",
            "handoff_status": (
                "ready_for_local_resume"
                if friction_reduction_summary.get("local_continuation_allowed") is True
                else "blocked_pending_approval"
            ),
            "task": str(control_system_summary.get("task") or workflow_summary.get("task") or "Mullu Developer Workflow v1"),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "current_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                developer_workflow_milestone_summary.get("next_action")
                or operator_decision_summary.get("recommended_action")
                or "inspect workflow receipts"
            ),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "recommended_mode": str(
                control_system_summary.get("recommended_mode")
                or friction_mode_summary.get("foundation_recommended_mode")
                or "fast"
            ),
            "local_resume_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "forbidden_effects": [
                "external_pr_creation",
                "branch_push",
                "merge",
                "deployment",
                "connector_write",
                "real_world_effect",
            ],
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Handoff ready for local resume; "
                f"milestone {str(developer_workflow_milestone_summary.get('current_milestone') or 'collect_sandbox_receipts')}; "
                f"next evidence {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}"
            ),
        },
        "operator_review_readiness_summary": {
            "summary_id": "operator_review_readiness.foundation",
            "review_status": (
                "ready_for_review"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "awaiting_evidence"
            ),
            "review_ready": int(evidence_progress_summary.get("pending_count") or 0) == 0,
            "review_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "next_review_action": (
                "review local diff and approval packet"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "complete local evidence receipts before review"
            ),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "pr_creation_allowed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Review readiness awaiting evidence; "
                f"{int(evidence_progress_summary.get('completed_count') or 0)}/"
                f"{int(evidence_progress_summary.get('required_count') or 0)} evidence receipts complete"
            ),
        },
        "operator_review_packet_summary": {
            "summary_id": "operator_review_packet.foundation",
            "packet_status": (
                "ready_for_review"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "awaiting_evidence"
            ),
            "review_ready": int(evidence_progress_summary.get("pending_count") or 0) == 0,
            "review_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "next_packet_action": (
                "review local diff and approval packet"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "complete local evidence receipts before review packet"
            ),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "approval_required_now": operator_decision_summary.get("operator_review_required_now") is True,
            "pr_creation_allowed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Review packet awaiting evidence; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_blocker_summary": {
            "summary_id": "operator_blocker.foundation",
            "blocker_status": "blocked" if int(evidence_progress_summary.get("pending_count") or 0) > 0 else "clear",
            "active_blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or sandbox_to_pr_packet.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "blocker_class": (
                "local_evidence"
                if int(evidence_progress_summary.get("pending_count") or 0) > 0
                else "approval_boundary"
            ),
            "clearing_action": (
                str(evidence_progress_summary.get("next_action") or "")
                or "complete local evidence receipts before review"
            ),
            "next_evidence_id": str(
                evidence_progress_summary.get("next_evidence_id")
                or friction_reduction_summary.get("next_evidence_id")
                or "sandbox_patch_receipt"
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "approval_required_now": operator_decision_summary.get("operator_review_required_now") is True,
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "local_resume_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Blocker sandbox_receipts_incomplete is local evidence; "
                f"next evidence {str(evidence_progress_summary.get('next_evidence_id') or friction_reduction_summary.get('next_evidence_id') or 'sandbox_patch_receipt')}"
            ),
        },
        "operator_packet_summary": {
            "summary_id": "operator_packet.foundation",
            "packet_status": "awaiting_packets",
            "sandbox_receipt_status": str(sandbox_receipt_bundle_summary.get("bundle_status") or "not_attached"),
            "attachment_status": str(
                sandbox_receipt_attachment_readiness_summary.get("packet_status") or "awaiting_attachments"
            ),
            "local_proof_status": str(local_sandbox_proof_readiness_summary.get("status") or "not_attached"),
            "rollback_receipt_status": str(local_rollback_receipts_summary.get("summary_status") or "not_attached"),
            "pr_readiness_status": str(pr_readiness_summary.get("readiness_status") or "awaiting_sandbox_receipts"),
            "completed_packet_count": int(
                sum(
                    1
                    for status in (
                        sandbox_receipt_bundle_summary.get("bundle_status"),
                        sandbox_receipt_attachment_readiness_summary.get("packet_status"),
                        local_sandbox_proof_readiness_summary.get("status"),
                        local_rollback_receipts_summary.get("summary_status"),
                        pr_readiness_summary.get("readiness_status"),
                    )
                    if str(status or "") in {
                        "complete",
                        "attached",
                        "ready",
                        "ready_for_external_pr_execution",
                    }
                )
            ),
            "required_packet_count": 5,
            "next_packet": str(evidence_progress_summary.get("next_evidence_id") or "sandbox_patch_receipt"),
            "next_packet_action": str(
                evidence_progress_summary.get("next_action")
                or "attach before state, after state, diff, command, and rollback receipt"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Packet summary awaiting sandbox_patch_receipt; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_authority_summary": {
            "summary_id": "operator_authority.foundation",
            "authority_status": "local_lab_only",
            "local_prepare_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "review_allowed": int(evidence_progress_summary.get("pending_count") or 0) == 0,
            "approval_required_now": operator_decision_summary.get("operator_review_required_now") is True,
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "pr_creation_allowed": False,
            "branch_push_allowed": False,
            "connector_write_allowed": False,
            "real_world_effects_allowed": False,
            "forbidden_effect_count": 4,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Authority local_lab_only; local preparation allowed; "
                "PR creation, branch push, connector writes, and real-world effects denied"
            ),
        },
        "operator_risk_summary": {
            "summary_id": "operator_risk.foundation",
            "risk_status": "low_local_lab",
            "risk_level": "low",
            "risk_driver": str(
                developer_workflow_milestone_summary.get("blocker")
                or workflow_monitor_summary.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "risk_scope": "local_lab_only",
            "safe_candidate_count": int(
                safe_local_action_queue_summary.get("candidate_count")
                or len(safe_automatic_action_candidates)
            ),
            "dangerous_blocker_count": int(
                dangerous_action_blocker_summary.get("blocker_count")
                or len(dangerous_zone_blockers)
            ),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "approval_boundary": str(
                friction_reduction_summary.get("approval_boundary")
                or approval_readiness_summary.get("approval_boundary")
                or "before_pr_or_real_world_effect"
            ),
            "rollback_ready": (
                local_rollback_flow_readiness_summary.get("rollback_ready") is True
                or local_rollback_flow_readiness_summary.get("status") == "ready"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Risk is low because execution is local-lab only; "
                f"{int(dangerous_action_blocker_summary.get('blocker_count') or len(dangerous_zone_blockers))} dangerous zones remain blocked"
            ),
        },
        "operator_approval_packet_summary": {
            "summary_id": "operator_approval_packet.foundation",
            "packet_status": (
                "ready_for_approval"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "awaiting_evidence"
            ),
            "approval_required": approval_readiness_summary.get("approval_required") is True,
            "approval_status": str(approval_readiness_summary.get("operator_approval_status") or "pending"),
            "approval_missing": approval_readiness_summary.get("approval_missing") is True,
            "current_blocker": str(
                approval_readiness_summary.get("current_blocker")
                or developer_workflow_milestone_summary.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(evidence_progress_summary.get("next_evidence_id") or "sandbox_patch_receipt"),
            "next_approval_action": str(
                approval_readiness_summary.get("next_approval_action")
                or "complete sandbox receipts before requesting approval"
            ),
            "approval_target_href": str(
                approval_readiness_summary.get("approval_target_href")
                or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
            ),
            "ready_for_pr_candidate_preparation": (
                approval_readiness_summary.get("ready_for_pr_candidate_preparation") is True
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Approval packet awaiting evidence; "
                f"{int(evidence_progress_summary.get('pending_count') or 0)} evidence receipts pending"
            ),
        },
        "operator_evidence_gap_summary": {
            "summary_id": "operator_evidence_gap.foundation",
            "gap_status": (
                "closed"
                if int(evidence_progress_summary.get("pending_count") or 0) == 0
                else "evidence_incomplete"
            ),
            "gap_class": "local_receipts",
            "completed_evidence_count": int(evidence_progress_summary.get("completed_count") or 0),
            "required_evidence_count": int(evidence_progress_summary.get("required_count") or 0),
            "pending_evidence_count": int(evidence_progress_summary.get("pending_count") or 0),
            "next_evidence_id": str(evidence_progress_summary.get("next_evidence_id") or "sandbox_patch_receipt"),
            "next_gap_action": str(
                evidence_progress_summary.get("next_action")
                or "complete sandbox patch, test, diff, and terminal receipts"
            ),
            "approval_blocked": int(evidence_progress_summary.get("pending_count") or 0) > 0,
            "local_continuation_allowed": friction_reduction_summary.get("local_continuation_allowed") is True,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                f"Evidence gap: {int(evidence_progress_summary.get('pending_count') or 0)} "
                f"of {int(evidence_progress_summary.get('required_count') or 0)} receipts still pending"
            ),
        },
        "operator_rollback_gap_summary": {
            "summary_id": "operator_rollback_gap.foundation",
            "gap_status": (
                "ready"
                if (
                    int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                    and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                    >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
                )
                else "rollback_receipts_incomplete"
            ),
            "readiness_verdict": str(
                local_rollback_flow_readiness_summary.get("readiness_verdict") or "awaiting_selection"
            ),
            "command_status": str(
                local_rollback_flow_readiness_summary.get("command_status") or "awaiting_selection"
            ),
            "selected_artifact_count": int(
                local_rollback_flow_readiness_summary.get("selected_artifact_count") or 0
            ),
            "receipt_available_count": int(
                local_rollback_flow_readiness_summary.get("receipt_available_count") or 0
            ),
            "receipt_required_count": int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0),
            "next_rollback_action": str(
                local_rollback_flow_readiness_summary.get("next_action")
                or "select at least one generated artifact before running rollback flow"
            ),
            "dry_run_required": (
                local_rollback_flow_readiness_summary.get("dry_run_required")
                if "dry_run_required" in local_rollback_flow_readiness_summary
                else True
            ),
            "execution_requires_execute_flag": (
                local_rollback_flow_readiness_summary.get("execution_requires_execute_flag")
                if "execution_requires_execute_flag" in local_rollback_flow_readiness_summary
                else True
            ),
            "rollback_ready": (
                int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0) > 0
                and int(local_rollback_flow_readiness_summary.get("receipt_available_count") or 0)
                >= int(local_rollback_flow_readiness_summary.get("receipt_required_count") or 0)
            ),
            "approval_status": str(
                local_rollback_receipts_summary.get("approval_status")
                or local_rollback_approval_packet.get("approval_status")
                or "pending"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "Rollback gap: "
                f"{int(local_rollback_flow_readiness_summary.get('receipt_available_count') or 0)}/"
                f"{int(local_rollback_flow_readiness_summary.get('receipt_required_count') or 0)} "
                "rollback receipts available"
            ),
        },
        "operator_pr_gap_summary": {
            "summary_id": "operator_pr_gap.foundation",
            "gap_status": str(pr_readiness_summary.get("readiness_status") or "awaiting_sandbox_receipts"),
            "first_blocker": str(
                pr_readiness_summary.get("first_blocker")
                or pr_readiness_bundle.get("first_blocker")
                or "sandbox_receipts"
            ),
            "ready_for_external_pr_execution": (
                pr_readiness_summary.get("ready_for_external_pr_execution") is True
                or pr_readiness_bundle.get("ready_for_external_pr_execution") is True
            ),
            "next_evidence_count": int(
                pr_readiness_summary.get("next_evidence_count")
                or pr_readiness_bundle.get("next_evidence_count")
                or 0
            ),
            "receipt_completed_count": int(
                pr_readiness_summary.get("receipt_completed_count")
                or developer_workflow_milestone_summary.get("receipt_completed_count")
                or 0
            ),
            "receipt_required_count": int(
                pr_readiness_summary.get("receipt_required_count")
                or developer_workflow_milestone_summary.get("receipt_required_count")
                or 0
            ),
            "preview_only": (
                pr_readiness_summary.get("preview_only")
                if "preview_only" in pr_readiness_summary
                else True
            ),
            "pr_creation_allowed": False,
            "branch_push_allowed": False,
            "execution_performed": False,
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
            "operator_message": (
                "PR gap: "
                f"{str(pr_readiness_summary.get('readiness_status') or 'awaiting_sandbox_receipts')}; "
                f"first blocker {str(pr_readiness_summary.get('first_blocker') or pr_readiness_bundle.get('first_blocker') or 'sandbox_receipts')}"
            ),
        },
        "operator_dashboard_summary": {
            "summary_id": "operator_dashboard.foundation",
            "task": str(control_system_summary.get("task") or workflow_summary.get("task") or "Mullu Developer Workflow v1"),
            "status": str(control_system_summary.get("status") or workflow_summary.get("status") or ""),
            "current_milestone": str(
                developer_workflow_milestone_summary.get("current_milestone")
                or "collect_sandbox_receipts"
            ),
            "blocker": str(
                developer_workflow_milestone_summary.get("blocker")
                or workflow_monitor_summary.get("blocker")
                or "sandbox_receipts_incomplete"
            ),
            "next_action": str(
                developer_workflow_milestone_summary.get("next_action")
                or control_system_summary.get("action_needed")
                or "inspect workflow receipts"
            ),
            "recommended_mode": str(control_system_summary.get("recommended_mode") or friction_recommended_mode),
            "receipt_completed_count": int(
                developer_workflow_milestone_summary.get("receipt_completed_count")
                or sandbox_to_pr_receipts.get("completed_count")
                or 0
            ),
            "receipt_required_count": int(
                developer_workflow_milestone_summary.get("receipt_required_count")
                or sandbox_to_pr_receipts.get("required_count")
                or 0
            ),
            "pending_unlock_count": int(control_system_summary.get("pending_unlock_count") or unlock_pending_count),
            "safe_candidate_count": int(control_system_summary.get("safe_candidate_count") or unlock_safe_candidate_count),
            "dangerous_blocker_count": int(
                control_system_summary.get("dangerous_blocker_count") or unlock_dangerous_blocker_count
            ),
            "next_unlock": str(control_system_summary.get("next_unlock") or unlock_next_unlock),
            "action_needed": str(
                control_system_summary.get("action_needed")
                or workflow_summary.get("action_needed")
                or "inspect workflow receipts"
            ),
            "risk": str(control_system_summary.get("risk") or "low, local lab only"),
            "operator_message": (
                f"Dashboard summary: {str(developer_workflow_milestone_summary.get('current_milestone') or 'collect_sandbox_receipts')}; "
                f"next action {str(developer_workflow_milestone_summary.get('next_action') or 'inspect workflow receipts')}"
            ),
            "execution_boundary": "local_lab_only",
            "external_effects_allowed": False,
        },
        "sandbox_receipt_bundle": {
            "status": str(developer_workflow_run.get("sandbox_receipt_bundle_status") or "not_attached"),
            "completed_count": int(developer_workflow_run.get("sandbox_receipt_bundle_completed_count", 0) or 0),
            "required_count": int(developer_workflow_run.get("sandbox_receipt_bundle_required_count", 0) or 0),
            "receipts": _bounded_bundle_receipts(sandbox_bundle_receipts),
        },
        "sandbox_receipt_bundle_summary": {
            "status": str(
                sandbox_receipt_bundle_summary.get("status")
                or developer_workflow_run.get("sandbox_receipt_bundle_status")
                or "not_attached"
            ),
            "completed_count": int(
                sandbox_receipt_bundle_summary.get("completed_count")
                or developer_workflow_run.get("sandbox_receipt_bundle_completed_count")
                or 0
            ),
            "required_count": int(
                sandbox_receipt_bundle_summary.get("required_count")
                or developer_workflow_run.get("sandbox_receipt_bundle_required_count")
                or 0
            ),
            "receipt_count": int(
                sandbox_receipt_bundle_summary.get("receipt_count")
                or len([receipt for receipt in sandbox_bundle_receipts if isinstance(receipt, Mapping)])
            ),
            "next_receipt_id": str(
                sandbox_receipt_bundle_summary.get("next_receipt_id")
                or sandbox_bundle_next_receipt.get("receipt_id")
                or "sandbox_patch_receipt"
            ),
            "next_receipt_status": str(
                sandbox_receipt_bundle_summary.get("next_receipt_status")
                or sandbox_bundle_next_receipt.get("status")
                or "pending"
            ),
            "execution_boundary": str(
                sandbox_receipt_bundle_summary.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "sandbox_receipt_attachments": {
            "packet_id": str(
                sandbox_receipt_attachment_packet.get("packet_id")
                or "developer_workflow_sandbox_receipt_attachment_packet.v1"
            ),
            "packet_status": str(sandbox_receipt_attachment_packet.get("packet_status") or "awaiting_attachments"),
            "external_effects_allowed": False,
            "completed_count": int(sandbox_receipt_attachment_packet.get("completed_count", 0) or 0),
            "required_count": int(sandbox_receipt_attachment_packet.get("required_count", 0) or 0),
            "next_attachment": {
                "receipt_id": str(next_attachment.get("receipt_id") or "sandbox_patch_receipt"),
                "label": str(next_attachment.get("label") or "Sandbox patch receipt"),
                "status": str(next_attachment.get("status") or "awaiting_attachment"),
                "action": str(
                    next_attachment.get("action")
                    or "attach before state, after state, diff, command, and rollback receipt"
                ),
            },
            "attachments": _bounded_attachment_rows(sandbox_receipt_attachment_packet.get("attachments", ())),
        },
        "sandbox_receipt_attachment_readiness_summary": {
            "packet_status": str(
                sandbox_receipt_attachment_readiness_summary.get("packet_status")
                or sandbox_receipt_attachment_packet.get("packet_status")
                or "awaiting_attachments"
            ),
            "completed_count": int(
                sandbox_receipt_attachment_readiness_summary.get("completed_count")
                or sandbox_receipt_attachment_packet.get("completed_count")
                or 0
            ),
            "required_count": int(
                sandbox_receipt_attachment_readiness_summary.get("required_count")
                or sandbox_receipt_attachment_packet.get("required_count")
                or 0
            ),
            "next_receipt_id": str(
                sandbox_receipt_attachment_readiness_summary.get("next_receipt_id")
                or next_attachment.get("receipt_id")
                or "sandbox_patch_receipt"
            ),
            "next_label": str(
                sandbox_receipt_attachment_readiness_summary.get("next_label")
                or next_attachment.get("label")
                or "Sandbox patch receipt"
            ),
            "next_status": str(
                sandbox_receipt_attachment_readiness_summary.get("next_status")
                or next_attachment.get("status")
                or "awaiting_attachment"
            ),
            "next_action": str(
                sandbox_receipt_attachment_readiness_summary.get("next_action")
                or next_attachment.get("action")
                or "attach before state, after state, diff, command, and rollback receipt"
            ),
            "execution_boundary": str(
                sandbox_receipt_attachment_readiness_summary.get("execution_boundary")
                or sandbox_receipt_attachment_packet.get("execution_boundary")
                or "local_lab_only"
            ),
            "external_effects_allowed": False,
        },
        "local_sandbox_proof_report": {
            "status": str(local_sandbox_proof_report.get("status") or "not_attached"),
            "ok": local_sandbox_proof_report.get("ok") is True,
            "bundle_status": str(local_sandbox_proof_report.get("bundle_status") or "unknown"),
            "attachment_packet_status": str(
                local_sandbox_proof_report.get("attachment_packet_status") or "unknown"
            ),
            "next_attachment_id": str(local_sandbox_proof_report.get("next_attachment_id") or "unknown"),
            "pr_readiness_status": str(local_sandbox_proof_report.get("pr_readiness_status") or "unknown"),
            "completed_count": int(local_sandbox_proof_report.get("completed_count", 0) or 0),
            "required_count": int(local_sandbox_proof_report.get("required_count", 0) or 0),
            "execution_performed": False,
            "external_effects_allowed": False,
            "generated_artifacts": {
                str(key): str(value)
                for key, value in local_sandbox_proof_report.get("generated_artifacts", {}).items()
                if isinstance(local_sandbox_proof_report.get("generated_artifacts", {}), Mapping)
                and str(key).strip()
                and str(value).strip()
            },
        },
        "local_sandbox_proof_readiness_summary": {
            "proof_status": str(
                local_sandbox_proof_readiness_summary.get("proof_status")
                or local_sandbox_proof_report.get("status")
                or "not_attached"
            ),
            "ok": (
                local_sandbox_proof_readiness_summary.get("ok")
                if "ok" in local_sandbox_proof_readiness_summary
                else local_sandbox_proof_report.get("ok")
            ) is True,
            "bundle_status": str(
                local_sandbox_proof_readiness_summary.get("bundle_status")
                or local_sandbox_proof_report.get("bundle_status")
                or "unknown"
            ),
            "attachment_packet_status": str(
                local_sandbox_proof_readiness_summary.get("attachment_packet_status")
                or local_sandbox_proof_report.get("attachment_packet_status")
                or "unknown"
            ),
            "next_attachment_id": str(
                local_sandbox_proof_readiness_summary.get("next_attachment_id")
                or local_sandbox_proof_report.get("next_attachment_id")
                or "unknown"
            ),
            "pr_readiness_status": str(
                local_sandbox_proof_readiness_summary.get("pr_readiness_status")
                or local_sandbox_proof_report.get("pr_readiness_status")
                or "unknown"
            ),
            "completed_count": int(
                local_sandbox_proof_readiness_summary.get("completed_count")
                or local_sandbox_proof_report.get("completed_count")
                or 0
            ),
            "required_count": int(
                local_sandbox_proof_readiness_summary.get("required_count")
                or local_sandbox_proof_report.get("required_count")
                or 0
            ),
            "execution_performed": False,
            "external_effects_allowed": False,
        },
        "local_rollback_summary_packet": {
            "status": str(local_rollback_summary_packet.get("status") or "not_attached"),
            "packet_status": str(local_rollback_summary_packet.get("packet_status") or "rollback_unavailable"),
            "generated_artifact_count": int(
                local_rollback_summary_packet.get("generated_artifact_count", 0) or 0
            ),
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
            "artifacts": _bounded_rollback_artifact_rows(local_rollback_summary_packet.get("artifacts", ())),
        },
        "local_rollback_approval_packet": {
            "status": str(local_rollback_approval_packet.get("status") or "not_attached"),
            "packet_status": str(
                local_rollback_approval_packet.get("packet_status") or "awaiting_operator_approval"
            ),
            "approval_status": str(local_rollback_approval_packet.get("approval_status") or "pending"),
            "approval_scope": str(local_rollback_approval_packet.get("approval_scope") or "none"),
            "selected_artifact_count": int(
                local_rollback_approval_packet.get("selected_artifact_count", 0) or 0
            ),
            "delete_execution_allowed": local_rollback_approval_packet.get("delete_execution_allowed") is True,
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
            "authorized_artifacts": _bounded_rollback_approval_artifact_rows(
                local_rollback_approval_packet.get("authorized_artifacts", ())
            ),
        },
        "local_rollback_execution_receipt": {
            "status": str(local_rollback_execution_receipt.get("status") or "not_attached"),
            "execution_status": str(
                local_rollback_execution_receipt.get("execution_status") or "blocked_no_approval"
            ),
            "execution_mode": str(local_rollback_execution_receipt.get("execution_mode") or "dry_run"),
            "rollback_execution_performed": (
                local_rollback_execution_receipt.get("rollback_execution_performed") is True
            ),
            "external_effects_allowed": False,
            "target_path_checks_performed": (
                local_rollback_execution_receipt.get("target_path_checks_performed") is True
            ),
            "selected_artifact_count": int(
                local_rollback_execution_receipt.get("selected_artifact_count", 0) or 0
            ),
            "executed_artifact_count": int(
                local_rollback_execution_receipt.get("executed_artifact_count", 0) or 0
            ),
            "skipped_artifact_count": int(
                local_rollback_execution_receipt.get("skipped_artifact_count", 0) or 0
            ),
            "failed_artifact_count": int(
                local_rollback_execution_receipt.get("failed_artifact_count", 0) or 0
            ),
            "artifacts": _bounded_rollback_execution_artifact_rows(
                local_rollback_execution_receipt.get("artifacts", ())
            ),
        },
        "local_rollback_receipts_summary": {
            "summary_status": str(
                local_rollback_receipts_summary.get("summary_status")
                or local_rollback_summary_packet.get("status")
                or "not_attached"
            ),
            "approval_status": str(
                local_rollback_receipts_summary.get("approval_status")
                or local_rollback_approval_packet.get("approval_status")
                or "pending"
            ),
            "execution_status": str(
                local_rollback_receipts_summary.get("execution_status")
                or local_rollback_execution_receipt.get("execution_status")
                or "blocked_no_approval"
            ),
            "execution_mode": str(
                local_rollback_receipts_summary.get("execution_mode")
                or local_rollback_execution_receipt.get("execution_mode")
                or "dry_run"
            ),
            "generated_artifact_count": int(
                local_rollback_receipts_summary.get("generated_artifact_count")
                or local_rollback_summary_packet.get("generated_artifact_count")
                or 0
            ),
            "selected_artifact_count": int(
                local_rollback_receipts_summary.get("selected_artifact_count")
                or local_rollback_approval_packet.get("selected_artifact_count")
                or 0
            ),
            "attached_receipt_count": int(
                local_rollback_receipts_summary.get("attached_receipt_count")
                or sum(
                    1
                    for receipt in (
                        local_rollback_summary_packet,
                        local_rollback_approval_packet,
                        local_rollback_execution_receipt,
                    )
                    if str(receipt.get("status") or "") == "attached"
                )
            ),
            "required_receipt_count": int(local_rollback_receipts_summary.get("required_receipt_count") or 3),
            "delete_execution_allowed": local_rollback_receipts_summary.get("delete_execution_allowed") is True
            or local_rollback_approval_packet.get("delete_execution_allowed") is True,
            "rollback_execution_performed": False,
            "external_effects_allowed": False,
        },
        "local_rollback_flow_command": {
            "status": str(local_rollback_flow_command.get("status") or "awaiting_selection"),
            "action_label": str(local_rollback_flow_command.get("action_label") or "Run local rollback dry-run"),
            "next_action": str(
                local_rollback_flow_command.get("next_action")
                or "select at least one generated artifact before running rollback flow"
            ),
            "command": str(local_rollback_flow_command.get("command") or _LOCAL_ROLLBACK_FLOW_DRY_RUN_PLACEHOLDER),
            "execute_command": str(
                local_rollback_flow_command.get("execute_command")
                or f"{_LOCAL_ROLLBACK_FLOW_DRY_RUN_PLACEHOLDER} --execute"
            ),
            "selected_artifact_ids": [
                str(item) for item in rollback_selected_artifact_ids
            ],
            "rollback_summary_path": str(
                local_rollback_flow_command.get("rollback_summary_path") or _LOCAL_ROLLBACK_SUMMARY_PACKET_PATH
            ),
            "approval_packet_path": str(
                local_rollback_flow_command.get("approval_packet_path") or _LOCAL_ROLLBACK_APPROVAL_PACKET_PATH
            ),
            "dry_run_receipt_path": str(
                local_rollback_flow_command.get("dry_run_receipt_path") or _LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
            ),
            "execution_receipt_path": str(
                local_rollback_flow_command.get("execution_receipt_path") or _LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
            ),
            "rollback_summary_href": str(
                local_rollback_flow_command.get("rollback_summary_href")
                or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=summary"
            ),
            "approval_packet_href": str(
                local_rollback_flow_command.get("approval_packet_href")
                or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=approval"
            ),
            "dry_run_receipt_href": str(
                local_rollback_flow_command.get("dry_run_receipt_href")
                or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=execution"
            ),
            "execution_receipt_href": str(
                local_rollback_flow_command.get("execution_receipt_href")
                or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=execution"
            ),
            "receipt_availability": _local_rollback_receipt_availability_projection(
                rollback_receipt_availability
            ),
            "readiness_verdict": _local_rollback_readiness_verdict(
                local_rollback_flow_command.get("readiness_verdict")
            ),
            "dry_run_required": local_rollback_flow_command.get("dry_run_required", True) is True,
            "execution_requires_execute_flag": (
                local_rollback_flow_command.get("execution_requires_execute_flag", True) is True
            ),
            "external_effects_allowed": False,
        },
        "local_rollback_flow_readiness_summary": {
            "readiness_verdict": _local_rollback_readiness_verdict(
                local_rollback_flow_readiness_summary.get("readiness_verdict")
                or local_rollback_flow_command.get("readiness_verdict")
            ),
            "command_status": str(
                local_rollback_flow_readiness_summary.get("command_status")
                or local_rollback_flow_command.get("status")
                or "awaiting_selection"
            ),
            "selected_artifact_count": int(
                local_rollback_flow_readiness_summary.get("selected_artifact_count")
                or len(rollback_selected_artifact_ids)
            ),
            "receipt_available_count": int(
                local_rollback_flow_readiness_summary.get("receipt_available_count")
                or rollback_receipt_availability.get("available_count")
                or 0
            ),
            "receipt_required_count": int(
                local_rollback_flow_readiness_summary.get("receipt_required_count")
                or rollback_receipt_availability.get("required_count")
                or 3
            ),
            "next_action": str(
                local_rollback_flow_readiness_summary.get("next_action")
                or local_rollback_flow_command.get("next_action")
                or "select at least one generated artifact before running rollback flow"
            ),
            "dry_run_required": (
                local_rollback_flow_readiness_summary.get("dry_run_required")
                if "dry_run_required" in local_rollback_flow_readiness_summary
                else local_rollback_flow_command.get("dry_run_required", True)
            ) is True,
            "execution_requires_execute_flag": (
                local_rollback_flow_readiness_summary.get("execution_requires_execute_flag")
                if "execution_requires_execute_flag" in local_rollback_flow_readiness_summary
                else local_rollback_flow_command.get("execution_requires_execute_flag", True)
            ) is True,
            "external_effects_allowed": False,
        },
        "workflow_run": {
            "status": str(developer_workflow_run.get("status") or ""),
            "current_task_id": str(developer_workflow_run.get("current_task_id") or ""),
            "receipt_checklist_required_count": int(
                developer_workflow_run.get("receipt_checklist_required_count", 0) or 0
            ),
            "receipt_checklist_completed_required_count": int(
                developer_workflow_run.get("receipt_checklist_completed_required_count", 0) or 0
            ),
            "rollback_receipt_status": str(developer_workflow_run.get("rollback_receipt_status") or ""),
        },
        "source_refs": {
            "snapshot": "operator_control_tower_snapshot",
            "capability_panel": "capability_health.metadata.developer_workflow_summary",
            "control_tower_headline_summary": (
                "capability_health.metadata.control_system_summary + "
                "workflow_monitor.metadata.friction_reduction_summary"
            ),
            "local_lab_readiness_summary": (
                "workflow_monitor.metadata.evidence_progress_summary + "
                "workflow_monitor.metadata.local_rollback_flow_readiness_summary"
            ),
            "local_resume_plan_summary": (
                "workflow_monitor.metadata.operator_decision_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_action_card": "workflow_monitor.metadata.operator_action_card",
            "next_action_summary": "workflow_monitor.metadata.next_action_summary",
            "approval_readiness_summary": "workflow_monitor.metadata.approval_readiness_summary",
            "operator_decision_summary": "workflow_monitor.metadata.operator_decision_summary",
            "friction_reduction_summary": "workflow_monitor.metadata.friction_reduction_summary",
            "safe_local_action_queue_summary": "capability_health.metadata.safe_local_action_queue_summary",
            "safe_automatic_action_candidates": "capability_health.metadata.safe_automatic_action_candidates",
            "dangerous_action_blocker_summary": "capability_health.metadata.dangerous_action_blocker_summary",
            "dangerous_zone_blockers": "capability_health.metadata.dangerous_zone_blockers",
            "lab_real_world_summary": "capability_health.metadata.lab_real_world_summary",
            "approval_boundary_summary": "capability_health.metadata.approval_boundary_summary",
            "rollback_control_summary": "capability_health.metadata.rollback_control_summary",
            "capability_registry_summary": "capability_health.metadata.capability_registry_summary",
            "friction_mode_summary": "capability_health.metadata.friction_mode_summary",
            "safe_vs_dangerous_summary": "capability_health.metadata.safe_vs_dangerous_summary",
            "unlock_readiness_summary": "capability_health.metadata.unlock_readiness_summary",
            "control_system_summary": "capability_health.metadata.control_system_summary",
            "workflow_monitor_summary": "workflow_monitor.metadata.workflow_monitor_summary",
            "workflow_panel": "workflow_monitor.metadata.sandbox_to_pr_packet",
            "focus": "workflow_monitor.metadata.sandbox_to_pr_focus",
            "sandbox_to_pr_summary": "workflow_monitor.metadata.sandbox_to_pr_summary",
            "sandbox_receipt_bundle_summary": "workflow_monitor.metadata.sandbox_receipt_bundle_summary",
            "sandbox_receipt_attachments": "workflow_monitor.metadata.sandbox_receipt_attachment_packet",
            "sandbox_receipt_attachment_readiness_summary": (
                "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary"
            ),
            "local_sandbox_proof_report": "workflow_monitor.metadata.local_sandbox_proof_report",
            "local_sandbox_proof_readiness_summary": (
                "workflow_monitor.metadata.local_sandbox_proof_readiness_summary"
            ),
            "local_rollback_summary_packet": "workflow_monitor.metadata.local_rollback_summary_packet",
            "local_rollback_approval_packet": "workflow_monitor.metadata.local_rollback_approval_packet",
            "local_rollback_execution_receipt": "workflow_monitor.metadata.local_rollback_execution_receipt",
            "local_rollback_receipts_summary": "workflow_monitor.metadata.local_rollback_receipts_summary",
            "local_rollback_flow_command": "workflow_monitor.metadata.local_rollback_flow_command",
            "local_rollback_flow_readiness_summary": (
                "workflow_monitor.metadata.local_rollback_flow_readiness_summary"
            ),
            "pr_readiness": "workflow_monitor.metadata.pr_readiness_bundle",
            "pr_readiness_summary": "workflow_monitor.metadata.pr_readiness_summary",
            "evidence_progress_summary": "workflow_monitor.metadata.evidence_progress_summary",
            "developer_workflow_operator_receipt": "workflow_monitor.metadata.developer_workflow_operator_receipt",
            "developer_workflow_operator_receipt_summary": (
                "workflow_monitor.metadata.developer_workflow_operator_receipt_summary"
            ),
            "developer_workflow_readiness_summary": (
                "workflow_monitor.metadata.developer_workflow_readiness_summary"
            ),
            "developer_workflow_milestone_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary"
            ),
            "developer_workflow_completion_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_terminal_closure_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_resume_checkpoint_summary": (
                "workflow_monitor.metadata.friction_reduction_summary + "
                "workflow_monitor.metadata.operator_decision_summary"
            ),
            "operator_sandbox_milestone_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_sandbox_receipt_checklist_summary": (
                "workflow_monitor.metadata.evidence_progress_summary + "
                "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary"
            ),
            "operator_sandbox_patch_receipt_summary": (
                "workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_sandbox_patch_command_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt collection command"
            ),
            "operator_sandbox_patch_bundle_preview_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt bundle validation"
            ),
            "operator_sandbox_patch_validation_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt validation readiness"
            ),
            "operator_sandbox_patch_terminal_review_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt terminal review readiness"
            ),
            "operator_sandbox_patch_approval_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt approval readiness"
            ),
            "operator_sandbox_patch_pr_preparation_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt PR preparation readiness"
            ),
            "operator_sandbox_patch_pr_creation_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt PR creation readiness"
            ),
            "operator_sandbox_patch_pr_ci_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt PR CI readiness"
            ),
            "operator_sandbox_patch_merge_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt merge readiness"
            ),
            "operator_sandbox_patch_release_handoff_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt release handoff readiness"
            ),
            "operator_sandbox_patch_deployment_publication_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt deployment publication readiness"
            ),
            "operator_sandbox_patch_production_monitoring_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt production monitoring readiness"
            ),
            "operator_sandbox_patch_incident_response_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt incident response readiness"
            ),
            "operator_sandbox_patch_recovery_closure_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt recovery closure readiness"
            ),
            "operator_sandbox_patch_trust_ledger_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt trust ledger readiness"
            ),
            "operator_sandbox_patch_terminal_audit_export_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt terminal audit export readiness"
            ),
            "operator_sandbox_patch_foundation_closure_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt foundation closure readiness"
            ),
            "operator_sandbox_patch_iteration_resume_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt iteration resume readiness"
            ),
            "operator_sandbox_patch_next_scope_admission_readiness_summary": (
                "docs/21_workflow_runtime.md sandbox_patch_receipt next scope admission readiness"
            ),
            "operator_handoff_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary + "
                "workflow_monitor.metadata.operator_decision_summary"
            ),
            "operator_review_readiness_summary": (
                "workflow_monitor.metadata.evidence_progress_summary + "
                "workflow_monitor.metadata.approval_readiness_summary"
            ),
            "operator_review_packet_summary": (
                "workflow_monitor.metadata.approval_readiness_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_blocker_summary": (
                "workflow_monitor.metadata.developer_workflow_milestone_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_packet_summary": (
                "workflow_monitor.metadata.sandbox_receipt_bundle_summary + "
                "workflow_monitor.metadata.local_rollback_receipts_summary"
            ),
            "operator_authority_summary": (
                "workflow_monitor.metadata.approval_readiness_summary + "
                "capability_health.metadata.lab_real_world_summary"
            ),
            "operator_risk_summary": (
                "capability_health.metadata.dangerous_action_blocker_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_approval_packet_summary": (
                "workflow_monitor.metadata.approval_readiness_summary + "
                "workflow_monitor.metadata.evidence_progress_summary"
            ),
            "operator_evidence_gap_summary": (
                "workflow_monitor.metadata.evidence_progress_summary + "
                "workflow_monitor.metadata.friction_reduction_summary"
            ),
            "operator_rollback_gap_summary": (
                "workflow_monitor.metadata.local_rollback_flow_readiness_summary + "
                "workflow_monitor.metadata.local_rollback_receipts_summary"
            ),
            "operator_pr_gap_summary": (
                "workflow_monitor.metadata.pr_readiness_summary + "
                "workflow_monitor.metadata.pr_readiness_bundle"
            ),
            "operator_dashboard_summary": (
                "capability_health.metadata.control_system_summary + "
                "workflow_monitor.metadata.developer_workflow_milestone_summary"
            ),
        },
        "receipt_hash": "",
    }
    receipt_hash = canonical_hash(receipt)
    receipt["receipt_hash"] = receipt_hash
    receipt["receipt_id"] = f"operator-control-tower-status-{receipt_hash[:16]}"
    return receipt


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
    rollback_summary = capability_metadata.get("rollback_summary", {})
    if not isinstance(rollback_summary, Mapping):
        rollback_summary = {}
    next_unlock_queue = capability_metadata.get("next_unlock_queue", ())
    if not isinstance(next_unlock_queue, list):
        next_unlock_queue = []
    capability_passports = capability_metadata.get("capability_passports", ())
    if not isinstance(capability_passports, list):
        capability_passports = []
    mode_selector = capability_metadata.get("mode_selector", {})
    if not isinstance(mode_selector, Mapping):
        mode_selector = {}
    mode_summary = mode_selector.get("summary", {})
    if not isinstance(mode_summary, Mapping):
        mode_summary = {}
    friction_mode_summary = capability_metadata.get("friction_mode_summary", {})
    if not isinstance(friction_mode_summary, Mapping):
        friction_mode_summary = {}
    mode_capabilities = mode_selector.get("capabilities", ())
    if not isinstance(mode_capabilities, list):
        mode_capabilities = []
    sandbox_to_pr_policy = capability_metadata.get("sandbox_to_pr_policy", {})
    if not isinstance(sandbox_to_pr_policy, Mapping):
        sandbox_to_pr_policy = {}
    safe_zones = tuple(str(zone) for zone in capability_metadata.get("safe_automatic_zones", ()) if str(zone).strip())
    safe_automatic_action_candidates = capability_metadata.get("safe_automatic_action_candidates", ())
    if not isinstance(safe_automatic_action_candidates, list):
        safe_automatic_action_candidates = []
    safe_local_action_queue_summary = capability_metadata.get("safe_local_action_queue_summary", {})
    if not isinstance(safe_local_action_queue_summary, Mapping):
        safe_local_action_queue_summary = {}
    dangerous_zones = tuple(str(zone) for zone in capability_metadata.get("dangerous_zones", ()) if str(zone).strip())
    dangerous_zone_blockers = capability_metadata.get("dangerous_zone_blockers", ())
    if not isinstance(dangerous_zone_blockers, list):
        dangerous_zone_blockers = []
    dangerous_action_blocker_summary = capability_metadata.get("dangerous_action_blocker_summary", {})
    if not isinstance(dangerous_action_blocker_summary, Mapping):
        dangerous_action_blocker_summary = {}
    lab_real_world_summary = capability_metadata.get("lab_real_world_summary", {})
    if not isinstance(lab_real_world_summary, Mapping):
        lab_real_world_summary = {}
    approval_boundary_summary = capability_metadata.get("approval_boundary_summary", {})
    if not isinstance(approval_boundary_summary, Mapping):
        approval_boundary_summary = {}
    rollback_control_summary = capability_metadata.get("rollback_control_summary", {})
    if not isinstance(rollback_control_summary, Mapping):
        rollback_control_summary = {}
    capability_registry_summary = capability_metadata.get("capability_registry_summary", {})
    if not isinstance(capability_registry_summary, Mapping):
        capability_registry_summary = {}
    safe_vs_dangerous_summary = capability_metadata.get("safe_vs_dangerous_summary", {})
    if not isinstance(safe_vs_dangerous_summary, Mapping):
        safe_vs_dangerous_summary = {}
    unlock_readiness_summary = capability_metadata.get("unlock_readiness_summary", {})
    if not isinstance(unlock_readiness_summary, Mapping):
        unlock_readiness_summary = {}
    control_system_summary = capability_metadata.get("control_system_summary", {})
    if not isinstance(control_system_summary, Mapping):
        control_system_summary = {}
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
    workflow_monitor_summary = workflow_panel_metadata.get("workflow_monitor_summary", {})
    if not isinstance(workflow_monitor_summary, Mapping):
        workflow_monitor_summary = {}
    developer_workflow_milestone_summary = workflow_panel_metadata.get("developer_workflow_milestone_summary", {})
    if not isinstance(developer_workflow_milestone_summary, Mapping):
        developer_workflow_milestone_summary = {}
    operator_action_card = workflow_panel_metadata.get("operator_action_card", {})
    if not isinstance(operator_action_card, Mapping):
        operator_action_card = {}
    next_action_summary = workflow_panel_metadata.get("next_action_summary", {})
    if not isinstance(next_action_summary, Mapping):
        next_action_summary = {}
    approval_readiness_summary = workflow_panel_metadata.get("approval_readiness_summary", {})
    if not isinstance(approval_readiness_summary, Mapping):
        approval_readiness_summary = {}
    operator_decision_summary = workflow_panel_metadata.get("operator_decision_summary", {})
    if not isinstance(operator_decision_summary, Mapping):
        operator_decision_summary = {}
    friction_reduction_summary = workflow_panel_metadata.get("friction_reduction_summary", {})
    if not isinstance(friction_reduction_summary, Mapping):
        friction_reduction_summary = {}
    sandbox_to_pr_packet = workflow_panel_metadata.get("sandbox_to_pr_packet", {})
    if not isinstance(sandbox_to_pr_packet, Mapping):
        sandbox_to_pr_packet = {}
    sandbox_to_pr_focus = workflow_panel_metadata.get("sandbox_to_pr_focus", {})
    if not isinstance(sandbox_to_pr_focus, Mapping):
        sandbox_to_pr_focus = {}
    sandbox_receipt_attachment_packet = workflow_panel_metadata.get("sandbox_receipt_attachment_packet", {})
    if not isinstance(sandbox_receipt_attachment_packet, Mapping):
        sandbox_receipt_attachment_packet = {}
    sandbox_receipt_attachment_readiness_summary = workflow_panel_metadata.get(
        "sandbox_receipt_attachment_readiness_summary", {}
    )
    if not isinstance(sandbox_receipt_attachment_readiness_summary, Mapping):
        sandbox_receipt_attachment_readiness_summary = {}
    local_sandbox_proof_report = workflow_panel_metadata.get("local_sandbox_proof_report", {})
    if not isinstance(local_sandbox_proof_report, Mapping):
        local_sandbox_proof_report = {}
    local_rollback_summary_packet = workflow_panel_metadata.get("local_rollback_summary_packet", {})
    if not isinstance(local_rollback_summary_packet, Mapping):
        local_rollback_summary_packet = {}
    local_rollback_approval_packet = workflow_panel_metadata.get("local_rollback_approval_packet", {})
    if not isinstance(local_rollback_approval_packet, Mapping):
        local_rollback_approval_packet = {}
    local_rollback_execution_receipt = workflow_panel_metadata.get("local_rollback_execution_receipt", {})
    if not isinstance(local_rollback_execution_receipt, Mapping):
        local_rollback_execution_receipt = {}
    local_rollback_flow_command = workflow_panel_metadata.get("local_rollback_flow_command", {})
    if not isinstance(local_rollback_flow_command, Mapping):
        local_rollback_flow_command = {}
    local_rollback_flow_readiness_summary = workflow_panel_metadata.get("local_rollback_flow_readiness_summary", {})
    if not isinstance(local_rollback_flow_readiness_summary, Mapping):
        local_rollback_flow_readiness_summary = {}
    pr_readiness_bundle = workflow_panel_metadata.get("pr_readiness_bundle", {})
    if not isinstance(pr_readiness_bundle, Mapping):
        pr_readiness_bundle = {}
    evidence_progress_summary = workflow_panel_metadata.get("evidence_progress_summary", {})
    if not isinstance(evidence_progress_summary, Mapping):
        evidence_progress_summary = {}
    developer_workflow_operator_receipt = workflow_panel_metadata.get("developer_workflow_operator_receipt", {})
    if not isinstance(developer_workflow_operator_receipt, Mapping):
        developer_workflow_operator_receipt = {}
    receipt_checklist = workflow_run_summary.get("receipt_checklist", ())
    if not isinstance(receipt_checklist, list):
        receipt_checklist = []
    sandbox_bundle_receipts = workflow_run_summary.get("sandbox_receipt_bundle_receipts", ())
    if not isinstance(sandbox_bundle_receipts, list):
        sandbox_bundle_receipts = []
    sandbox_to_pr_readiness = workflow_run_summary.get("sandbox_to_pr_readiness", {})
    if not isinstance(sandbox_to_pr_readiness, Mapping):
        sandbox_to_pr_readiness = {}
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
    unlock_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('unlock_level', '')))}</td>"
        f"<td>{escape(str(item.get('next_unlock', '')))}</td>"
        f"<td>{escape(', '.join(str(value) for value in item.get('required_evidence', ())))}</td>"
        f"<td>{int(item.get('blocked_action_count', 0) or 0)}</td>"
        "</tr>"
        for item in next_unlock_queue
        if isinstance(item, Mapping)
    )
    if not unlock_rows:
        unlock_rows = '<tr><td colspan="5">No pending unlock evidence</td></tr>'
    passport_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('unlock_level', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('operating_boundary', '')))}</td>"
        f"<td>{escape(str(item.get('fast_mode_admission', '')))}</td>"
        f"<td>{escape(str(item.get('next_unlock', '')))}</td>"
        f"<td>{escape(str(item.get('rollback_default', False)).lower())}</td>"
        "</tr>"
        for item in capability_passports
        if isinstance(item, Mapping)
    )
    if not passport_rows:
        passport_rows = '<tr><td colspan="7">No capability passports available</td></tr>'
    mode_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('capability_id', '')))}</td>"
        f"<td>{escape(str(item.get('unlock_level', '')))}</td>"
        f"<td>{escape(str(item.get('strict', '')))}</td>"
        f"<td>{escape(str(item.get('balanced', '')))}</td>"
        f"<td>{escape(str(item.get('fast', '')))}</td>"
        f"<td>{escape(str(item.get('recommended_mode', '')))}</td>"
        "</tr>"
        for item in mode_capabilities
        if isinstance(item, Mapping)
    )
    if not mode_rows:
        mode_rows = '<tr><td colspan="6">No mode selector data available</td></tr>'
    safe_action_candidate_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('zone', '')))}</td>"
        f"<td>{escape(str(item.get('title', '')))}</td>"
        f"<td>{escape(str(item.get('status', 'candidate')))}</td>"
        f"<td>{escape(str(item.get('primary_action', '')))}</td>"
        f"<td>{escape(str(item.get('execution_boundary', 'local_lab_only')))}</td>"
        f"<td>{escape(str(item.get('external_effects_allowed', False)).lower())}</td>"
        "</tr>"
        for item in safe_automatic_action_candidates
        if isinstance(item, Mapping)
    )
    if not safe_action_candidate_rows:
        safe_action_candidate_rows = '<tr><td colspan="6">No safe automatic action candidates available</td></tr>'
    safe_local_queue_message = str(
        safe_local_action_queue_summary.get("operator_message")
        or (
            f"{len(safe_automatic_action_candidates)} safe local actions queued for "
            f"{str(friction_mode_summary.get('foundation_recommended_mode') or 'fast')} mode; "
            "approval not required for local preparation"
        )
    )
    safe_local_queue_status = str(safe_local_action_queue_summary.get("queue_status") or "ready")
    safe_local_queue_count = int(
        safe_local_action_queue_summary.get("candidate_count") or len(safe_automatic_action_candidates)
    )
    safe_local_queue_first_id = str(safe_local_action_queue_summary.get("first_candidate_id") or "")
    safe_local_queue_first_zone = str(safe_local_action_queue_summary.get("first_zone") or "")
    safe_local_queue_first_action = str(
        safe_local_action_queue_summary.get("first_action") or "prepare safe local sandbox work"
    )
    safe_local_queue_mode = str(
        safe_local_action_queue_summary.get("recommended_mode")
        or friction_mode_summary.get("foundation_recommended_mode")
        or "fast"
    )
    safe_local_queue_approval_required = safe_local_action_queue_summary.get("approval_required") is True
    safe_local_queue_boundary = str(
        safe_local_action_queue_summary.get("local_execution_boundary") or "local_lab_only"
    )
    safe_local_queue_external_effects = safe_local_action_queue_summary.get("external_effects_allowed") is True
    dangerous_zone_blocker_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('zone', '')))}</td>"
        f"<td>{escape(str(item.get('title', '')))}</td>"
        f"<td>{escape(str(item.get('status', 'blocked')))}</td>"
        f"<td>{escape(str(item.get('reason', '')))}</td>"
        f"<td>{escape(', '.join(str(value) for value in item.get('required_evidence', ()) if str(value).strip()))}</td>"
        f"<td>{escape(str(item.get('risk', 'high, real-world boundary')))}</td>"
        f"<td>{escape(str(item.get('execution_boundary', 'real_world')))}</td>"
        f"<td>{escape(str(item.get('approval_required', True)).lower())}</td>"
        f"<td>{escape(str(item.get('external_effects_allowed', False)).lower())}</td>"
        "</tr>"
        for item in dangerous_zone_blockers
        if isinstance(item, Mapping)
    )
    if not dangerous_zone_blocker_rows:
        dangerous_zone_blocker_rows = '<tr><td colspan="9">No dangerous zone blockers available</td></tr>'
    dangerous_blocker_required_evidence = dangerous_action_blocker_summary.get("required_evidence", ())
    if not isinstance(dangerous_blocker_required_evidence, list):
        dangerous_blocker_required_evidence = []
    dangerous_blocker_evidence_text = ", ".join(
        str(item)
        for item in dangerous_blocker_required_evidence
        if str(item).strip()
    )
    if not dangerous_blocker_evidence_text and dangerous_zone_blockers:
        first_blocker_for_display = dangerous_zone_blockers[0] if isinstance(dangerous_zone_blockers[0], Mapping) else {}
        fallback_required = first_blocker_for_display.get("required_evidence", ())
        if isinstance(fallback_required, list):
            dangerous_blocker_evidence_text = ", ".join(
                str(item)
                for item in fallback_required
                if str(item).strip()
            )
    if not dangerous_blocker_evidence_text:
        dangerous_blocker_evidence_text = "none"
    dangerous_blocker_message = str(
        dangerous_action_blocker_summary.get("operator_message")
        or (
            f"{len(dangerous_zone_blockers)} dangerous real-world zones blocked; "
            "approval, rollback, and effect receipt required before execution"
        )
    )
    dangerous_blocker_status = str(dangerous_action_blocker_summary.get("blocker_status") or "blocked")
    dangerous_blocker_count = int(
        dangerous_action_blocker_summary.get("blocker_count") or len(dangerous_zone_blockers)
    )
    dangerous_blocker_first_id = str(dangerous_action_blocker_summary.get("first_blocker_id") or "")
    dangerous_blocker_first_zone = str(dangerous_action_blocker_summary.get("first_zone") or "")
    dangerous_blocker_first_reason = str(
        dangerous_action_blocker_summary.get("first_reason") or "dangerous_zone_requires_explicit_approval"
    )
    dangerous_blocker_approval_required = dangerous_action_blocker_summary.get("approval_required") is True
    dangerous_blocker_rollback_required = dangerous_action_blocker_summary.get("rollback_required") is True
    dangerous_blocker_boundary = str(
        dangerous_action_blocker_summary.get("real_world_execution_boundary") or "real_world"
    )
    dangerous_blocker_external_effects = dangerous_action_blocker_summary.get("external_effects_allowed") is True
    lab_real_world_message = str(
        lab_real_world_summary.get("operator_message")
        or "Lab mode can prepare 0 local candidates; real-world writes remain blocked; 0 dangerous zones need approval"
    )
    lab_real_world_lab_allowed = lab_real_world_summary.get("lab_mode_allowed") is True
    lab_real_world_safe_count = int(lab_real_world_summary.get("lab_safe_candidate_count") or 0)
    lab_real_world_fast_ready = int(lab_real_world_summary.get("fast_mode_lab_ready_count") or 0)
    lab_real_world_effects_allowed = lab_real_world_summary.get("real_world_effects_allowed") is True
    lab_real_world_write_status = str(lab_real_world_summary.get("real_world_write_status") or "blocked")
    lab_real_world_dangerous_count = int(lab_real_world_summary.get("dangerous_blocker_count") or 0)
    lab_real_world_approval_count = int(lab_real_world_summary.get("dangerous_approval_required_count") or 0)
    lab_real_world_lab_boundary = str(lab_real_world_summary.get("lab_execution_boundary") or "local_lab_only")
    lab_real_world_real_boundary = str(lab_real_world_summary.get("real_world_execution_boundary") or "real_world")
    lab_real_world_external_effects = lab_real_world_summary.get("external_effects_allowed") is True
    approval_boundary_message = str(
        approval_boundary_summary.get("operator_message")
        or "0 local automatic candidates; 0 capability unlocks need approval; 0 dangerous zones remain approval-bound"
    )
    approval_boundary_local_auto = int(approval_boundary_summary.get("local_auto_candidate_count") or 0)
    approval_boundary_unlock_count = int(approval_boundary_summary.get("approval_unlock_count") or 0)
    approval_boundary_dangerous_count = int(
        approval_boundary_summary.get("dangerous_approval_required_count") or 0
    )
    approval_boundary_pr_required = approval_boundary_summary.get("pr_approval_required") is True
    approval_boundary_name = str(
        approval_boundary_summary.get("approval_boundary") or "before_pr_or_real_world_effect"
    )
    approval_boundary_next_capability = str(approval_boundary_summary.get("next_approval_capability_id") or "")
    approval_boundary_execution = str(approval_boundary_summary.get("execution_boundary") or "local_lab_only")
    approval_boundary_external_effects = approval_boundary_summary.get("external_effects_allowed") is True
    rollback_control_message = str(
        rollback_control_summary.get("operator_message")
        or "0 capabilities carry rollback default; 0 unlocks require rollback evidence; rollback execution remains receipt-bound"
    )
    rollback_control_default_count = int(rollback_control_summary.get("rollback_default_count") or 0)
    rollback_control_required_count = int(rollback_control_summary.get("rollback_required_count") or 0)
    rollback_control_capability_count = int(rollback_control_summary.get("capability_count") or 0)
    rollback_control_default_ready = rollback_control_summary.get("rollback_default_ready") is True
    rollback_control_policy_ready = rollback_control_summary.get("sandbox_to_pr_policy_ready") is True
    rollback_control_policy = str(
        rollback_control_summary.get("rollback_policy")
        or "If Mullu can change it, Mullu must also know how to undo it."
    )
    rollback_control_receipt_source = str(
        rollback_control_summary.get("rollback_receipt_source")
        or "developer_workflow_run.software_receipt_binding.stage_evidence.rollback_completed"
    )
    rollback_control_boundary = str(rollback_control_summary.get("execution_boundary") or "local_lab_only")
    rollback_control_external_effects = rollback_control_summary.get("external_effects_allowed") is True
    registry_required_evidence = capability_registry_summary.get("next_required_evidence", ())
    if not isinstance(registry_required_evidence, list):
        registry_required_evidence = []
    registry_evidence_text = ", ".join(str(value) for value in registry_required_evidence if str(value).strip())
    registry_message = str(
        capability_registry_summary.get("operator_message")
        or "0 capabilities preflight-ready; 0 capabilities blocked; next evidence is review for capability review"
    )
    registry_capability_count = int(capability_registry_summary.get("capability_count") or 0)
    registry_preflight_ready_count = int(capability_registry_summary.get("preflight_ready_count") or 0)
    registry_blocked_count = int(capability_registry_summary.get("blocked_count") or 0)
    registry_approval_required_count = int(capability_registry_summary.get("approval_required_count") or 0)
    registry_pending_unlock_count = int(capability_registry_summary.get("pending_unlock_count") or 0)
    registry_next_capability = str(capability_registry_summary.get("next_blocked_capability_id") or "")
    registry_next_reason = str(capability_registry_summary.get("next_blocked_reason") or "review")
    registry_evidence_count = int(capability_registry_summary.get("next_required_evidence_count") or 0)
    registry_boundary = str(capability_registry_summary.get("execution_boundary") or "local_lab_only")
    registry_external_effects = capability_registry_summary.get("external_effects_allowed") is True
    safe_vs_dangerous_message = str(
        safe_vs_dangerous_summary.get("operator_message")
        or "0 local-lab candidates available; 0 real-world zones blocked pending explicit approval"
    )
    safe_vs_dangerous_safe_count = int(safe_vs_dangerous_summary.get("safe_candidate_count") or 0)
    safe_vs_dangerous_blocked_count = int(safe_vs_dangerous_summary.get("dangerous_blocker_count") or 0)
    safe_vs_dangerous_first_safe = str(safe_vs_dangerous_summary.get("first_safe_zone") or "")
    safe_vs_dangerous_first_safe_action = str(
        safe_vs_dangerous_summary.get("first_safe_action") or "prepare safe local sandbox work"
    )
    safe_vs_dangerous_first_dangerous = str(safe_vs_dangerous_summary.get("first_dangerous_zone") or "")
    safe_vs_dangerous_first_reason = str(
        safe_vs_dangerous_summary.get("first_dangerous_reason")
        or "dangerous_zone_requires_explicit_approval"
    )
    safe_vs_dangerous_safe_boundary = str(
        safe_vs_dangerous_summary.get("safe_execution_boundary") or "local_lab_only"
    )
    safe_vs_dangerous_dangerous_boundary = str(
        safe_vs_dangerous_summary.get("dangerous_execution_boundary") or "real_world"
    )
    safe_vs_dangerous_external_effects = safe_vs_dangerous_summary.get("external_effects_allowed") is True
    unlock_readiness_message = str(
        unlock_readiness_summary.get("operator_message")
        or "0 pending unlocks; next evidence for capability review is approval; 0 dangerous zones require explicit approval"
    )
    unlock_readiness_pending_count = int(unlock_readiness_summary.get("pending_unlock_count") or 0)
    unlock_readiness_safe_count = int(unlock_readiness_summary.get("safe_candidate_count") or 0)
    unlock_readiness_dangerous_count = int(unlock_readiness_summary.get("dangerous_blocker_count") or 0)
    unlock_readiness_next_capability = str(unlock_readiness_summary.get("next_capability_id") or "")
    unlock_readiness_next_unlock = str(unlock_readiness_summary.get("next_unlock") or "approval")
    unlock_readiness_required_evidence = unlock_readiness_summary.get("next_required_evidence", ())
    if not isinstance(unlock_readiness_required_evidence, list):
        unlock_readiness_required_evidence = []
    unlock_readiness_evidence_text = ", ".join(
        str(value) for value in unlock_readiness_required_evidence if str(value).strip()
    )
    unlock_readiness_evidence_count = int(unlock_readiness_summary.get("next_required_evidence_count") or 0)
    unlock_readiness_safe_ready = int(unlock_readiness_summary.get("safe_candidates_ready") or 0)
    unlock_readiness_approval_blockers = int(
        unlock_readiness_summary.get("dangerous_blockers_requiring_approval") or 0
    )
    unlock_readiness_boundary = str(unlock_readiness_summary.get("execution_boundary") or "local_lab_only")
    unlock_readiness_external_effects = unlock_readiness_summary.get("external_effects_allowed") is True
    control_system_evidence = control_system_summary.get("next_required_evidence", ())
    if not isinstance(control_system_evidence, list):
        control_system_evidence = []
    control_system_evidence_text = ", ".join(str(item) for item in control_system_evidence if str(item).strip())
    if not control_system_evidence_text:
        control_system_evidence_text = "none"
    control_system_message = str(
        control_system_summary.get("operator_message")
        or f"Control system in {friction_mode_recommended} mode; next unlock {unlock_readiness_next_unlock}"
    )
    control_system_task = str(control_system_summary.get("task") or workflow_summary.get("task") or "Mullu Developer Workflow v1")
    control_system_status = str(control_system_summary.get("status") or workflow_summary.get("status") or "")
    control_system_mode = str(control_system_summary.get("recommended_mode") or friction_mode_recommended)
    control_system_lab_allowed = control_system_summary.get("lab_mode_allowed") is True
    control_system_capability_count = int(control_system_summary.get("capability_count") or registry_capability_count)
    control_system_pending_unlock_count = int(
        control_system_summary.get("pending_unlock_count") or unlock_readiness_pending_count
    )
    control_system_safe_count = int(control_system_summary.get("safe_candidate_count") or unlock_readiness_safe_count)
    control_system_dangerous_count = int(
        control_system_summary.get("dangerous_blocker_count") or unlock_readiness_dangerous_count
    )
    control_system_next_capability = str(
        control_system_summary.get("next_capability_id") or unlock_readiness_next_capability
    )
    control_system_next_unlock = str(control_system_summary.get("next_unlock") or unlock_readiness_next_unlock)
    control_system_evidence_count = int(
        control_system_summary.get("next_required_evidence_count") or len(control_system_evidence)
    )
    control_system_risk = str(control_system_summary.get("risk") or "low, local lab only")
    control_system_action = str(control_system_summary.get("action_needed") or workflow_summary.get("action_needed") or "")
    control_system_boundary = str(control_system_summary.get("execution_boundary") or "local_lab_only")
    control_system_external_effects = control_system_summary.get("external_effects_allowed") is True
    checklist_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('label', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('stage', '')))}</td>"
        f"<td>{escape(str(item.get('required', False)).lower())}</td>"
        f"<td>{escape(', '.join(str(ref) for ref in item.get('evidence_refs', ())))}</td>"
        "</tr>"
        for item in receipt_checklist
        if isinstance(item, Mapping)
    )
    if not checklist_rows:
        checklist_rows = '<tr><td colspan="5">No receipt checklist available</td></tr>'
    sandbox_bundle_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('label', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('stage', '')))}</td>"
        f"<td>{escape(str(item.get('required', False)).lower())}</td>"
        f"<td>{escape(', '.join(str(ref) for ref in item.get('evidence_refs', ())))}</td>"
        "</tr>"
        for item in sandbox_bundle_receipts
        if isinstance(item, Mapping)
    )
    if not sandbox_bundle_rows:
        sandbox_bundle_rows = '<tr><td colspan="5">No local sandbox bundle receipts attached</td></tr>'
    sandbox_to_pr_rows = "\n".join((
        "<tr>"
        "<td>Policy</td>"
        "<td>Capability passports</td>"
        f"<td>{escape(str(sandbox_to_pr_policy.get('policy_ready', False)).lower())}</td>"
        "<td>change and PR passports present; rollback default; approval required</td>"
        "</tr>",
        "<tr>"
        "<td>Rollback</td>"
        "<td>Change passport and receipt</td>"
        f"<td>{escape(str(sandbox_to_pr_policy.get('rollback_default', False)).lower())}</td>"
        f"<td>{escape(str(sandbox_to_pr_readiness.get('rollback_receipt_status') or 'not_recorded'))}</td>"
        "</tr>",
        "<tr>"
        "<td>Receipts</td>"
        "<td>Sandbox checklist</td>"
        f"<td>{escape(str(sandbox_to_pr_readiness.get('receipt_checklist_ready', False)).lower())}</td>"
        f"<td>{int(sandbox_to_pr_readiness.get('receipt_checklist_completed_count', 0) or 0)}/"
        f"{int(sandbox_to_pr_readiness.get('receipt_checklist_required_count', 0) or 0)} complete</td>"
        "</tr>",
        "<tr>"
        "<td>Approval</td>"
        "<td>Operator gate</td>"
        f"<td>{escape(str(sandbox_to_pr_policy.get('approval_required', False)).lower())}</td>"
        f"<td>{escape(str(sandbox_to_pr_readiness.get('operator_approval_status') or 'pending'))}</td>"
        "</tr>",
        "<tr>"
        "<td>PR</td>"
        "<td>Candidate preparation</td>"
        f"<td>{escape(str(sandbox_to_pr_readiness.get('readiness_status') or 'unknown'))}</td>"
        f"<td>{escape(str(sandbox_to_pr_readiness.get('next_action') or 'inspect workflow receipts'))}</td>"
        "</tr>",
    ))
    packet_required_evidence = sandbox_to_pr_packet.get("required_evidence", ())
    if not isinstance(packet_required_evidence, list):
        packet_required_evidence = []
    sandbox_to_pr_packet_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('evidence_id', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('source', '')))}</td>"
        "</tr>"
        for item in packet_required_evidence
        if isinstance(item, Mapping)
    )
    if not sandbox_to_pr_packet_rows:
        sandbox_to_pr_packet_rows = '<tr><td colspan="3">No packet evidence available</td></tr>'
    packet_next_evidence = sandbox_to_pr_packet.get("next_evidence", ())
    if not isinstance(packet_next_evidence, list):
        packet_next_evidence = []
    sandbox_to_pr_next_evidence_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('label', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('action', '')))}</td>"
        f"<td>{escape(str(item.get('source', '')))}</td>"
        "</tr>"
        for item in packet_next_evidence
        if isinstance(item, Mapping)
    )
    if not sandbox_to_pr_next_evidence_rows:
        sandbox_to_pr_next_evidence_rows = '<tr><td colspan="4">No next evidence available</td></tr>'
    sandbox_receipt_attachment_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('label', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('action', '')))}</td>"
        f"<td>{escape(str(item.get('source', '')))}</td>"
        f"<td>{escape(', '.join(str(ref) for ref in item.get('evidence_refs', ())))}</td>"
        "</tr>"
        for item in sandbox_receipt_attachment_packet.get("attachments", ())
        if isinstance(sandbox_receipt_attachment_packet.get("attachments", ()), list) and isinstance(item, Mapping)
    )
    if not sandbox_receipt_attachment_rows:
        sandbox_receipt_attachment_rows = '<tr><td colspan="5">No sandbox receipt attachment rows available</td></tr>'
    local_sandbox_artifacts = local_sandbox_proof_report.get("generated_artifacts", {})
    if not isinstance(local_sandbox_artifacts, Mapping):
        local_sandbox_artifacts = {}
    local_sandbox_artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(artifact_id))}</td>"
        f"<td>{escape(str(path))}</td>"
        "</tr>"
        for artifact_id, path in local_sandbox_artifacts.items()
        if str(artifact_id).strip() and str(path).strip()
    )
    if not local_sandbox_artifact_rows:
        local_sandbox_artifact_rows = '<tr><td colspan="2">No local sandbox proof report attached</td></tr>'
    rollback_artifacts = local_rollback_summary_packet.get("artifacts", ())
    if not isinstance(rollback_artifacts, list):
        rollback_artifacts = []
    rollback_artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('artifact_id', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('rollback_command', '')))}</td>"
        f"<td>{escape(str(item.get('required_confirmation', False)).lower())}</td>"
        "</tr>"
        for item in rollback_artifacts
        if isinstance(item, Mapping)
    )
    if not rollback_artifact_rows:
        rollback_artifact_rows = '<tr><td colspan="4">No local rollback summary packet attached</td></tr>'
    rollback_approval_artifacts = local_rollback_approval_packet.get("authorized_artifacts", ())
    if not isinstance(rollback_approval_artifacts, list):
        rollback_approval_artifacts = []
    rollback_approval_artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('artifact_id', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('approval_status', 'pending')))}</td>"
        f"<td>{escape(str(item.get('execution_allowed', False)).lower())}</td>"
        f"<td>{escape(str(item.get('rollback_command', '')))}</td>"
        "</tr>"
        for item in rollback_approval_artifacts
        if isinstance(item, Mapping)
    )
    if not rollback_approval_artifact_rows:
        rollback_approval_artifact_rows = '<tr><td colspan="5">No local rollback approval packet attached</td></tr>'
    rollback_execution_artifacts = local_rollback_execution_receipt.get("artifacts", ())
    if not isinstance(rollback_execution_artifacts, list):
        rollback_execution_artifacts = []
    rollback_execution_artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('artifact_id', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('action_status', 'skipped')))}</td>"
        f"<td>{escape(str(item.get('path_within_workspace', False)).lower())}</td>"
        f"<td>{escape(str(item.get('pre_exists', False)).lower())}</td>"
        f"<td>{escape(str(item.get('post_exists', False)).lower())}</td>"
        f"<td>{escape(str(item.get('error_message', '')))}</td>"
        "</tr>"
        for item in rollback_execution_artifacts
        if isinstance(item, Mapping)
    )
    if not rollback_execution_artifact_rows:
        rollback_execution_artifact_rows = '<tr><td colspan="7">No local rollback execution receipt attached</td></tr>'
    rollback_flow_selected_ids = local_rollback_flow_command.get("selected_artifact_ids", ())
    if not isinstance(rollback_flow_selected_ids, list):
        rollback_flow_selected_ids = []
    rollback_flow_status = str(local_rollback_flow_command.get("status") or "awaiting_selection")
    rollback_flow_command = str(local_rollback_flow_command.get("command") or _LOCAL_ROLLBACK_FLOW_DRY_RUN_PLACEHOLDER)
    rollback_flow_execute_command = str(
        local_rollback_flow_command.get("execute_command")
        or f"{_LOCAL_ROLLBACK_FLOW_DRY_RUN_PLACEHOLDER} --execute"
    )
    rollback_flow_selected_text = ", ".join(str(item) for item in rollback_flow_selected_ids if str(item).strip())
    if not rollback_flow_selected_text:
        rollback_flow_selected_text = "none"
    rollback_flow_action_label = str(local_rollback_flow_command.get("action_label") or "Run local rollback dry-run")
    rollback_flow_next_action = str(
        local_rollback_flow_command.get("next_action")
        or "select at least one generated artifact before running rollback flow"
    )
    rollback_flow_summary_path = str(
        local_rollback_flow_command.get("rollback_summary_path") or _LOCAL_ROLLBACK_SUMMARY_PACKET_PATH
    )
    rollback_flow_approval_path = str(
        local_rollback_flow_command.get("approval_packet_path") or _LOCAL_ROLLBACK_APPROVAL_PACKET_PATH
    )
    rollback_flow_dry_run_receipt_path = str(
        local_rollback_flow_command.get("dry_run_receipt_path") or _LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
    )
    rollback_flow_execution_receipt_path = str(
        local_rollback_flow_command.get("execution_receipt_path") or _LOCAL_ROLLBACK_EXECUTION_RECEIPT_PATH
    )
    rollback_flow_summary_href = str(
        local_rollback_flow_command.get("rollback_summary_href")
        or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=summary"
    )
    rollback_flow_approval_href = str(
        local_rollback_flow_command.get("approval_packet_href")
        or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=approval"
    )
    rollback_flow_dry_run_receipt_href = str(
        local_rollback_flow_command.get("dry_run_receipt_href")
        or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=execution"
    )
    rollback_flow_execution_receipt_href = str(
        local_rollback_flow_command.get("execution_receipt_href")
        or f"{_LOCAL_ROLLBACK_RECEIPT_HREF_BASE}?receipt_id=execution"
    )
    rollback_flow_availability = local_rollback_flow_command.get("receipt_availability", {})
    if not isinstance(rollback_flow_availability, Mapping):
        rollback_flow_availability = {}
    rollback_flow_availability = _local_rollback_receipt_availability_projection(rollback_flow_availability)
    rollback_flow_readiness_verdict = _local_rollback_readiness_verdict(
        local_rollback_flow_command.get("readiness_verdict")
    )
    task = str(workflow_summary.get("task") or "Mullu Developer Workflow v1")
    status = str(workflow.get("status") or workflow_summary.get("status") or "")
    reason = str(workflow_summary.get("reason") or "")
    next_unlock = str(workflow.get("next_unlock") or workflow_summary.get("next_unlock") or "")
    risk = str(workflow_summary.get("risk") or "")
    action_needed = str(workflow_summary.get("action_needed") or "")
    safe_zone_text = ", ".join(safe_zones) if safe_zones else "none"
    dangerous_zone_text = ", ".join(dangerous_zones) if dangerous_zones else "none"
    workflow_run_status = str(workflow_run_summary.get("status") or "")
    workflow_current_task = str(workflow_run_summary.get("current_task_id") or "")
    workflow_task_count = int(workflow_run_summary.get("task_count", 0) or 0)
    monitor_status = str(workflow_monitor_summary.get("monitor_status") or "monitoring")
    monitor_current_task = str(workflow_monitor_summary.get("current_task_id") or workflow_current_task)
    monitor_current_task_count = int(workflow_monitor_summary.get("current_task_count") or (1 if monitor_current_task else 0))
    monitor_plan_review_count = int(workflow_monitor_summary.get("plan_review_count") or 0)
    monitor_blocked_count = int(workflow_monitor_summary.get("blocked_count") or 0)
    monitor_review_count = int(workflow_monitor_summary.get("review_count") or 0)
    monitor_workflow_status = str(workflow_monitor_summary.get("workflow_status") or workflow_run_status)
    monitor_readiness_status = str(workflow_monitor_summary.get("readiness_status") or "awaiting_receipts")
    monitor_blocker = str(workflow_monitor_summary.get("blocker") or "sandbox_receipts_incomplete")
    monitor_next_action = str(workflow_monitor_summary.get("next_action") or "inspect workflow receipts")
    monitor_execution_boundary = str(workflow_monitor_summary.get("execution_boundary") or "local_lab_only")
    monitor_external_effects_allowed = workflow_monitor_summary.get("external_effects_allowed") is True
    milestone_message = str(
        developer_workflow_milestone_summary.get("operator_message")
        or "Developer workflow milestone collect_sandbox_receipts; next action inspect workflow receipts"
    )
    milestone_status = str(
        developer_workflow_milestone_summary.get("workflow_status") or monitor_workflow_status
    )
    milestone_readiness = str(
        developer_workflow_milestone_summary.get("readiness_status") or monitor_readiness_status
    )
    milestone_task = str(
        developer_workflow_milestone_summary.get("current_task_id") or monitor_current_task
    )
    milestone_name = str(
        developer_workflow_milestone_summary.get("current_milestone") or "collect_sandbox_receipts"
    )
    milestone_blocker = str(developer_workflow_milestone_summary.get("blocker") or monitor_blocker)
    milestone_next_action = str(
        developer_workflow_milestone_summary.get("next_action") or monitor_next_action
    )
    milestone_receipt_completed = int(
        developer_workflow_milestone_summary.get("receipt_completed_count") or 0
    )
    milestone_receipt_required = int(
        developer_workflow_milestone_summary.get("receipt_required_count") or 0
    )
    milestone_approval = str(
        developer_workflow_milestone_summary.get("operator_approval_status") or "pending"
    )
    milestone_pr_candidate = str(
        developer_workflow_milestone_summary.get("pr_candidate_status") or "pending"
    )
    milestone_boundary = str(
        developer_workflow_milestone_summary.get("execution_boundary") or "local_lab_only"
    )
    milestone_external_effects = developer_workflow_milestone_summary.get("external_effects_allowed") is True
    dashboard_summary_message = (
        f"Dashboard summary: {milestone_name}; next action {milestone_next_action}"
    )
    dashboard_summary_receipts = f"{milestone_receipt_completed}/{milestone_receipt_required}"
    dashboard_summary_pending_unlocks = control_system_pending_unlock_count
    dashboard_summary_safe_count = control_system_safe_count
    dashboard_summary_dangerous_count = control_system_dangerous_count
    dashboard_summary_next_unlock = control_system_next_unlock
    dashboard_summary_action = control_system_action or milestone_next_action
    dashboard_summary_boundary = "local_lab_only"
    dashboard_summary_external_effects = False
    checklist_done = int(workflow_run_summary.get("receipt_checklist_completed_required_count", 0) or 0)
    checklist_required = int(workflow_run_summary.get("receipt_checklist_required_count", 0) or 0)
    checklist_pending = int(workflow_run_summary.get("receipt_checklist_pending_required_count", 0) or 0)
    sandbox_bundle_status = str(workflow_run_summary.get("sandbox_receipt_bundle_status") or "not_attached")
    sandbox_bundle_completed = int(workflow_run_summary.get("sandbox_receipt_bundle_completed_count", 0) or 0)
    rollback_default_count = int(rollback_summary.get("rollback_default_count", 0) or 0)
    rollback_required_count = int(rollback_summary.get("rollback_required_count", 0) or 0)
    rollback_receipt_status = str(workflow_run_summary.get("rollback_receipt_status") or "not_recorded")
    rollback_receipt_count = int(workflow_run_summary.get("rollback_receipt_count", 0) or 0)
    sandbox_to_pr_status = str(sandbox_to_pr_readiness.get("readiness_status") or "unknown")
    sandbox_to_pr_next_action = str(sandbox_to_pr_readiness.get("next_action") or "inspect workflow receipts")
    sandbox_to_pr_packet_status = str(sandbox_to_pr_packet.get("status") or sandbox_to_pr_status)
    sandbox_to_pr_packet_blocker = str(sandbox_to_pr_packet.get("blocker") or "unknown")
    sandbox_to_pr_focus_label = str(sandbox_to_pr_focus.get("label") or "No pending sandbox-to-PR evidence")
    sandbox_to_pr_focus_status = str(sandbox_to_pr_focus.get("status") or "unknown")
    sandbox_to_pr_focus_action = str(sandbox_to_pr_focus.get("action") or sandbox_to_pr_next_action)
    sandbox_to_pr_focus_source = str(sandbox_to_pr_focus.get("source") or "none")
    action_card_title = str(operator_action_card.get("title") or "Next developer workflow action")
    action_card_status = str(operator_action_card.get("status") or monitor_readiness_status)
    action_card_reason = str(operator_action_card.get("reason") or monitor_blocker)
    action_card_primary_action = str(operator_action_card.get("primary_action") or monitor_next_action)
    action_card_primary_href = str(
        operator_action_card.get("primary_href")
        or "/operator/control-tower/status-receipt?focus_id=sandbox_patch_receipt"
    )
    action_card_focus_label = str(operator_action_card.get("focus_label") or sandbox_to_pr_focus_label)
    action_card_focus_status = str(operator_action_card.get("focus_status") or sandbox_to_pr_focus_status)
    action_card_task_id = str(operator_action_card.get("task_id") or monitor_current_task)
    action_card_risk = str(operator_action_card.get("risk") or "low, local lab only")
    action_card_boundary = str(operator_action_card.get("execution_boundary") or "local_lab_only")
    action_card_approval_required = operator_action_card.get("approval_required") is True
    action_card_external_effects_allowed = operator_action_card.get("external_effects_allowed") is True
    next_action_required_evidence = next_action_summary.get("required_evidence", ())
    if not isinstance(next_action_required_evidence, list):
        next_action_required_evidence = []
    next_action_required_evidence_text = ", ".join(
        str(item) for item in next_action_required_evidence if str(item).strip()
    )
    if not next_action_required_evidence_text:
        next_action_required_evidence_text = "none"
    next_action_status = str(next_action_summary.get("status") or action_card_status)
    next_action_reason = str(next_action_summary.get("reason") or action_card_reason)
    next_action_primary = str(next_action_summary.get("primary_action") or action_card_primary_action)
    next_action_href = str(next_action_summary.get("primary_href") or action_card_primary_href)
    next_action_focus = str(next_action_summary.get("focus_id") or action_card_focus_label)
    next_action_focus_status = str(next_action_summary.get("focus_status") or action_card_focus_status)
    next_action_focus_source = str(next_action_summary.get("focus_source") or sandbox_to_pr_focus_source)
    next_action_evidence_count = int(next_action_summary.get("required_evidence_count") or 0)
    next_action_approval_required = next_action_summary.get("approval_required") is True
    next_action_risk = str(next_action_summary.get("risk") or "low, local lab only")
    next_action_message = str(
        next_action_summary.get("operator_message")
        or f"Next action {next_action_primary}; focus {next_action_focus}"
    )
    next_action_boundary = str(next_action_summary.get("execution_boundary") or "local_lab_only")
    next_action_external_effects = next_action_summary.get("external_effects_allowed") is True
    approval_readiness_required = approval_readiness_summary.get("approval_required") is True
    approval_readiness_status = str(approval_readiness_summary.get("operator_approval_status") or "pending")
    approval_readiness_missing = approval_readiness_summary.get("approval_missing") is True
    approval_readiness_blocker = str(
        approval_readiness_summary.get("current_blocker") or sandbox_to_pr_packet_blocker
    )
    approval_readiness_boundary = str(
        approval_readiness_summary.get("approval_boundary") or "before_pr_or_real_world_effect"
    )
    approval_readiness_next_action = str(
        approval_readiness_summary.get("next_approval_action")
        or "complete sandbox receipts before requesting approval"
    )
    approval_readiness_href = str(
        approval_readiness_summary.get("approval_target_href")
        or action_card_primary_href
    )
    approval_readiness_pr_status = str(approval_readiness_summary.get("pr_candidate_status") or "pending")
    approval_readiness_ready_for_pr = approval_readiness_summary.get("ready_for_pr_candidate_preparation") is True
    approval_readiness_external_pr_allowed = approval_readiness_summary.get("external_pr_execution_allowed") is True
    approval_readiness_message = str(
        approval_readiness_summary.get("operator_message")
        or f"Approval pending; {approval_readiness_blocker} remains current blocker"
    )
    approval_readiness_execution_boundary = str(
        approval_readiness_summary.get("execution_boundary") or "local_lab_only"
    )
    approval_readiness_external_effects = approval_readiness_summary.get("external_effects_allowed") is True
    operator_decision_message = str(
        operator_decision_summary.get("operator_message")
        or "Decision collect_sandbox_receipts can continue in local lab; approval pending before PR or real-world effect"
    )
    operator_decision_status = str(operator_decision_summary.get("decision_status") or next_action_status)
    operator_decision_kind = str(operator_decision_summary.get("decision_kind") or "evidence_collection")
    operator_decision_milestone = str(
        operator_decision_summary.get("current_milestone") or milestone_name
    )
    operator_decision_blocker = str(
        operator_decision_summary.get("current_blocker") or approval_readiness_blocker
    )
    operator_decision_action = str(
        operator_decision_summary.get("recommended_action") or next_action_primary
    )
    operator_decision_href = str(operator_decision_summary.get("action_href") or next_action_href)
    operator_decision_evidence = str(
        operator_decision_summary.get("next_evidence_id")
        or evidence_progress_summary.get("next_evidence_id")
        or "sandbox_patch_receipt"
    )
    operator_decision_review_now = operator_decision_summary.get("operator_review_required_now") is True
    operator_decision_review_before_external = (
        operator_decision_summary.get("operator_review_required_before_external_effect") is True
    )
    operator_decision_approval_status = str(
        operator_decision_summary.get("approval_status") or approval_readiness_status
    )
    operator_decision_boundary = str(
        operator_decision_summary.get("local_continuation_boundary") or "local_lab_only"
    )
    operator_decision_external_effects = operator_decision_summary.get("external_effects_allowed") is True
    friction_reduction_message = str(
        friction_reduction_summary.get("operator_message")
        or (
            "Friction reduced to collect_sandbox_receipts; continue local evidence collection, "
            "while PR and real-world effects remain approval-bound"
        )
    )
    friction_reduction_status = str(
        friction_reduction_summary.get("reduction_status") or "local_continuation_ready"
    )
    friction_reduction_milestone = str(
        friction_reduction_summary.get("current_milestone") or operator_decision_milestone
    )
    friction_reduction_blocker = str(
        friction_reduction_summary.get("current_blocker") or operator_decision_blocker
    )
    friction_reduction_local_allowed = friction_reduction_summary.get("local_continuation_allowed") is True
    friction_reduction_pending_evidence = int(friction_reduction_summary.get("pending_evidence_count") or 0)
    friction_reduction_next_evidence = str(
        friction_reduction_summary.get("next_evidence_id") or operator_decision_evidence
    )
    friction_reduction_approval_boundary = str(
        friction_reduction_summary.get("approval_boundary") or "before_pr_or_real_world_effect"
    )
    friction_reduction_review_now = friction_reduction_summary.get("operator_review_required_now") is True
    friction_reduction_external_effects = friction_reduction_summary.get("external_effects_allowed") is True
    control_headline_task = control_system_task
    control_headline_status = control_system_status
    control_headline_state = "local_lab_ready" if friction_reduction_local_allowed else "blocked"
    control_headline_message = (
        "Control tower headline: local lab can continue; "
        f"{safe_local_queue_count} safe local candidates; "
        f"{dangerous_blocker_count} dangerous zones blocked"
    )
    control_headline_mode = control_system_mode
    control_headline_next_action = operator_decision_action
    control_headline_next_evidence = friction_reduction_next_evidence
    control_headline_approval_boundary = friction_reduction_approval_boundary
    control_headline_external_effects = False
    local_lab_readiness_pending_evidence = int(evidence_progress_summary.get("pending_count") or 0)
    local_lab_readiness_status = "awaiting_evidence" if local_lab_readiness_pending_evidence else "ready_to_prepare"
    local_lab_readiness_lab_allowed = lab_real_world_lab_allowed
    local_lab_readiness_local_allowed = friction_reduction_local_allowed
    local_lab_readiness_safe_count = safe_local_queue_count
    local_lab_readiness_next_evidence = str(
        evidence_progress_summary.get("next_evidence_id") or "sandbox_patch_receipt"
    )
    local_lab_readiness_rollback_available = int(
        local_rollback_flow_readiness_summary.get("receipt_available_count") or 0
    )
    local_lab_readiness_rollback_required = int(
        local_rollback_flow_readiness_summary.get("receipt_required_count") or 0
    )
    local_lab_readiness_rollback_ready = (
        local_lab_readiness_rollback_required > 0
        and local_lab_readiness_rollback_available >= local_lab_readiness_rollback_required
    )
    local_lab_readiness_next_action = operator_decision_action
    local_lab_readiness_message = (
        "Local lab readiness awaiting evidence; "
        f"{local_lab_readiness_pending_evidence} evidence receipts pending; "
        f"rollback receipts {local_lab_readiness_rollback_available}/{local_lab_readiness_rollback_required}"
    )
    local_lab_readiness_external_effects = False
    local_resume_plan_status = (
        "ready_for_local_continuation" if local_lab_readiness_local_allowed else "blocked_pending_approval"
    )
    local_resume_plan_continue_allowed = local_lab_readiness_local_allowed
    local_resume_plan_mode = control_system_mode
    local_resume_plan_milestone = milestone_name
    local_resume_plan_blocker = milestone_blocker
    local_resume_plan_next_action = operator_decision_action
    local_resume_plan_next_evidence = local_lab_readiness_next_evidence
    local_resume_plan_safe_count = local_lab_readiness_safe_count
    local_resume_plan_pending_evidence = local_lab_readiness_pending_evidence
    local_resume_plan_rollback_ready = local_lab_readiness_rollback_ready
    local_resume_plan_approval_now = operator_decision_review_now
    local_resume_plan_approval_boundary = friction_reduction_approval_boundary
    local_resume_plan_boundary = "local_lab_only"
    local_resume_plan_external_effects = False
    local_resume_plan_message = (
        f"Resume plan: continue local lab in {local_resume_plan_mode} mode; "
        f"next evidence {local_resume_plan_next_evidence}; "
        f"{local_resume_plan_pending_evidence} evidence receipts pending"
    )
    sandbox_attachment_status = str(
        sandbox_receipt_attachment_packet.get("packet_status") or "awaiting_attachments"
    )
    sandbox_attachment_completed = int(sandbox_receipt_attachment_packet.get("completed_count", 0) or 0)
    sandbox_attachment_required = int(sandbox_receipt_attachment_packet.get("required_count", 0) or 0)
    sandbox_next_attachment = sandbox_receipt_attachment_packet.get("next_attachment", {})
    if not isinstance(sandbox_next_attachment, Mapping):
        sandbox_next_attachment = {}
    sandbox_next_attachment_label = str(sandbox_next_attachment.get("label") or "No sandbox receipt attachment")
    sandbox_next_attachment_action = str(sandbox_next_attachment.get("action") or sandbox_to_pr_next_action)
    local_proof_status = str(local_sandbox_proof_report.get("status") or "not_attached")
    local_proof_ok = local_sandbox_proof_report.get("ok") is True
    local_proof_pr_status = str(local_sandbox_proof_report.get("pr_readiness_status") or "unknown")
    local_proof_completed = int(local_sandbox_proof_report.get("completed_count", 0) or 0)
    local_proof_required = int(local_sandbox_proof_report.get("required_count", 0) or 0)
    rollback_packet_status = str(local_rollback_summary_packet.get("packet_status") or "rollback_unavailable")
    rollback_artifact_count = int(local_rollback_summary_packet.get("generated_artifact_count", 0) or 0)
    rollback_execution = local_rollback_summary_packet.get("rollback_execution_performed") is True
    rollback_approval_status = str(local_rollback_approval_packet.get("approval_status") or "pending")
    rollback_approval_packet_status = str(
        local_rollback_approval_packet.get("packet_status") or "awaiting_operator_approval"
    )
    rollback_delete_allowed = local_rollback_approval_packet.get("delete_execution_allowed") is True
    rollback_selected_count = int(local_rollback_approval_packet.get("selected_artifact_count", 0) or 0)
    rollback_execution_status = str(
        local_rollback_execution_receipt.get("execution_status") or "blocked_no_approval"
    )
    rollback_execution_mode = str(local_rollback_execution_receipt.get("execution_mode") or "dry_run")
    rollback_executed_count = int(local_rollback_execution_receipt.get("executed_artifact_count", 0) or 0)
    rollback_failed_count = int(local_rollback_execution_receipt.get("failed_artifact_count", 0) or 0)
    pr_readiness_status = str(pr_readiness_bundle.get("readiness_status") or "awaiting_sandbox_receipts")
    pr_readiness_first_blocker = str(pr_readiness_bundle.get("first_blocker") or "unknown")
    pr_readiness_summary = str(pr_readiness_bundle.get("operator_summary") or "")
    pr_readiness_ready = pr_readiness_bundle.get("ready_for_external_pr_execution") is True
    pr_readiness_next_evidence = pr_readiness_bundle.get("next_evidence", ())
    if not isinstance(pr_readiness_next_evidence, list):
        pr_readiness_next_evidence = []
    pr_readiness_artifacts = pr_readiness_bundle.get("artifacts", {})
    if not isinstance(pr_readiness_artifacts, Mapping):
        pr_readiness_artifacts = {}
    evidence_progress_message = str(
        evidence_progress_summary.get("operator_message")
        or "0/0 local evidence receipts complete; next sandbox_patch_receipt"
    )
    evidence_progress_status = str(evidence_progress_summary.get("status") or "awaiting_evidence")
    evidence_progress_completed = int(evidence_progress_summary.get("completed_count") or 0)
    evidence_progress_required = int(evidence_progress_summary.get("required_count") or 0)
    evidence_progress_pending = int(evidence_progress_summary.get("pending_count") or 0)
    evidence_progress_next_id = str(evidence_progress_summary.get("next_evidence_id") or "sandbox_patch_receipt")
    evidence_progress_next_action = str(
        evidence_progress_summary.get("next_action") or "inspect workflow receipts"
    )
    evidence_progress_blocker = str(evidence_progress_summary.get("blocker") or "sandbox_receipts_incomplete")
    evidence_progress_sandbox = int(evidence_progress_summary.get("sandbox_receipt_completed_count") or 0)
    evidence_progress_sandbox_required = int(evidence_progress_summary.get("sandbox_receipt_required_count") or 0)
    evidence_progress_bundle = int(evidence_progress_summary.get("sandbox_bundle_completed_count") or 0)
    evidence_progress_bundle_required = int(evidence_progress_summary.get("sandbox_bundle_required_count") or 0)
    evidence_progress_rollback = int(evidence_progress_summary.get("rollback_receipt_available_count") or 0)
    evidence_progress_rollback_required = int(evidence_progress_summary.get("rollback_receipt_required_count") or 0)
    evidence_progress_pr_next = int(evidence_progress_summary.get("pr_next_evidence_count") or 0)
    evidence_progress_boundary = str(evidence_progress_summary.get("execution_boundary") or "local_lab_only")
    evidence_progress_external_effects = evidence_progress_summary.get("external_effects_allowed") is True
    workflow_completion_status = (
        "ready_for_external_pr_approval"
        if pr_readiness_ready
        else (
            "ready_for_operator_approval"
            if sandbox_to_pr_packet_blocker == "operator_approval_missing"
            else "awaiting_evidence"
        )
    )
    workflow_completion_progress = (
        int((evidence_progress_completed / evidence_progress_required) * 100)
        if evidence_progress_required > 0
        else 0
    )
    workflow_completion_condition = (
        "complete local evidence receipts before approval"
        if evidence_progress_pending > 0
        else "request operator approval before PR preparation"
    )
    workflow_completion_message = (
        f"Developer Workflow completion {evidence_progress_completed}/{evidence_progress_required} "
        f"evidence receipts; next closure condition {workflow_completion_condition}"
    )
    workflow_completion_terminal_ready = False
    workflow_completion_pr_allowed = False
    workflow_completion_boundary = "local_lab_only"
    workflow_completion_external_effects = False
    terminal_closure_status = (
        "ready_for_terminal_review" if evidence_progress_pending == 0 else "AwaitingEvidence"
    )
    terminal_closure_ready = False
    terminal_closure_message = (
        f"Terminal closure AwaitingEvidence; {evidence_progress_pending} evidence receipts pending"
    )
    terminal_closure_rollback_ready = (
        local_lab_readiness_rollback_required > 0
        and local_lab_readiness_rollback_available >= local_lab_readiness_rollback_required
    )
    terminal_closure_pr_allowed = False
    terminal_closure_branch_push_allowed = False
    terminal_closure_boundary = "local_lab_only"
    terminal_closure_external_effects = False
    resume_checkpoint_status = (
        "ready_for_local_resume" if friction_reduction_local_allowed else "blocked_pending_approval"
    )
    resume_checkpoint_message = (
        f"Resume checkpoint ready for local lab; next evidence {evidence_progress_next_id}; "
        f"{evidence_progress_pending} evidence receipts pending"
    )
    resume_checkpoint_boundary = "local_lab_only"
    resume_checkpoint_external_effects = False
    sandbox_milestone_status = "ready_for_review" if evidence_progress_pending == 0 else "awaiting_receipts"
    sandbox_milestone_message = (
        f"Sandbox milestone awaiting receipts; next evidence {evidence_progress_next_id}; "
        f"{evidence_progress_pending} evidence receipts pending"
    )
    sandbox_milestone_required_receipts = (
        "sandbox_patch_receipt, sandbox_test_receipt, sandbox_diff_receipt, dry_run_receipt, "
        "rollback_plan_receipt, terminal_review_receipt, operator_approval_packet_receipt"
    )
    sandbox_milestone_write_authority = False
    sandbox_milestone_pr_allowed = False
    sandbox_milestone_boundary = "local_lab_only"
    sandbox_milestone_external_effects = False
    sandbox_checklist_status = "complete" if evidence_progress_pending == 0 else "incomplete"
    sandbox_checklist_sequence = sandbox_milestone_required_receipts
    sandbox_checklist_terminal_review = evidence_progress_pending == 0
    sandbox_checklist_write_authority = False
    sandbox_checklist_external_effects = False
    sandbox_checklist_message = (
        f"Sandbox checklist incomplete; next receipt {evidence_progress_next_id}; "
        f"{evidence_progress_pending} receipts pending"
    )
    sandbox_patch_required_parts = "before_state, after_state, diff, command, rollback_command, evidence_ref"
    sandbox_patch_status = str(
        sandbox_receipt_attachment_readiness_summary.get("next_status") or "awaiting_attachment"
    )
    sandbox_patch_next_action = str(
        sandbox_receipt_attachment_readiness_summary.get("next_action")
        or evidence_progress_next_action
    )
    sandbox_patch_rollback_required = True
    sandbox_patch_dry_run_required = True
    sandbox_patch_write_authority = False
    sandbox_patch_attachment_allowed = False
    sandbox_patch_boundary = "local_lab_only"
    sandbox_patch_external_effects = False
    sandbox_patch_message = (
        "Sandbox patch receipt awaiting attachment; required parts before_state, "
        "after_state, diff, command, rollback_command, evidence_ref"
    )
    sandbox_patch_command_status = "preview_only"
    sandbox_patch_command = (
        "python scripts/collect_developer_workflow_sandbox_receipt_evidence.py "
        "--receipt-id sandbox_patch_receipt "
        "--before-file .change_assurance/before.txt "
        "--after-file .change_assurance/after.txt "
        "--diff-file .change_assurance/sandbox_patch.diff "
        "--command \"apply_patch\" "
        "--rollback-command \"git apply -R .change_assurance/sandbox_patch.diff\" "
        "--evidence-ref proof://developer-workflow-v1/sandbox-patch"
    )
    sandbox_patch_command_inputs = (
        ".change_assurance/before.txt, .change_assurance/after.txt, "
        ".change_assurance/sandbox_patch.diff"
    )
    sandbox_patch_command_output = "developer_workflow_sandbox_receipt_bundle.collected.json"
    sandbox_patch_command_execution = False
    sandbox_patch_command_attachment = False
    sandbox_patch_command_message = (
        "Sandbox patch command preview ready; execution and attachment remain operator-controlled"
    )
    sandbox_patch_bundle_status = "preview_only"
    sandbox_patch_bundle_path = "developer_workflow_sandbox_receipt_bundle.collected.json"
    sandbox_patch_bundle_receipts = "sandbox_patch_receipt"
    sandbox_patch_bundle_validation = (
        "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
        "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
    )
    sandbox_patch_bundle_generation = False
    sandbox_patch_bundle_validation_performed = False
    sandbox_patch_bundle_message = (
        "Sandbox patch bundle preview ready; bundle generation and validation not executed"
    )
    sandbox_patch_validation_status = "blocked_missing_bundle"
    sandbox_patch_validation_required = (
        "sandbox_patch_receipt_bundle_generated, sandbox_patch_receipt_attached"
    )
    sandbox_patch_validation_missing = 2
    sandbox_patch_validation_terminal_review = False
    sandbox_patch_validation_message = (
        "Sandbox patch validation blocked until the collected bundle exists and receipt is attached"
    )
    sandbox_patch_terminal_review_status = "blocked_until_validation"
    sandbox_patch_terminal_review_required = (
        "sandbox_patch_receipt_bundle_generated, sandbox_patch_receipt_attached, "
        "sandbox_patch_bundle_validated"
    )
    sandbox_patch_terminal_review_missing = 3
    sandbox_patch_terminal_review_performed = False
    sandbox_patch_terminal_review_approval = False
    sandbox_patch_terminal_review_pr = False
    sandbox_patch_terminal_review_message = (
        "Sandbox patch terminal review blocked until bundle generation, attachment, and validation complete"
    )
    sandbox_patch_approval_status = "blocked_until_terminal_review"
    sandbox_patch_approval_required = (
        "sandbox_patch_receipt_bundle_generated, sandbox_patch_receipt_attached, "
        "sandbox_patch_bundle_validated, sandbox_patch_terminal_review_complete"
    )
    sandbox_patch_approval_missing = 4
    sandbox_patch_approval_request_performed = False
    sandbox_patch_pr_preparation = False
    sandbox_patch_approval_message = (
        "Sandbox patch approval blocked until terminal review closes with validated evidence"
    )
    sandbox_patch_pr_preparation_status = "blocked_until_approval"
    sandbox_patch_pr_preparation_required = (
        "sandbox_patch_receipt_bundle_generated, sandbox_patch_receipt_attached, "
        "sandbox_patch_bundle_validated, sandbox_patch_terminal_review_complete, "
        "operator_approval_recorded"
    )
    sandbox_patch_pr_preparation_missing = 5
    sandbox_patch_pr_preparation_performed = False
    sandbox_patch_branch_push = False
    sandbox_patch_pr_preparation_message = (
        "PR preparation blocked until sandbox patch approval is recorded with validated evidence"
    )
    sandbox_patch_pr_creation_status = "blocked_until_pr_preparation"
    sandbox_patch_pr_creation_required = (
        "local_pr_candidate_packet_prepared, local_pr_candidate_packet_validated, "
        "external_pr_execution_approval_recorded, branch_push_authority_bound, "
        "github_pr_admission_passed"
    )
    sandbox_patch_pr_creation_missing = 5
    sandbox_patch_pr_creation_performed = False
    sandbox_patch_connector_call = False
    sandbox_patch_pr_creation_message = (
        "PR creation blocked until local PR preparation and external PR approval evidence are complete"
    )
    sandbox_patch_pr_ci_status = "blocked_until_pr_creation"
    sandbox_patch_pr_ci_required = (
        "github_pull_request_created, pr_metadata_packet_recorded, "
        "ci_gate_before_ready_for_review_witness_bound, "
        "github_check_read_authority_bound, pr_effect_reconciliation_pending"
    )
    sandbox_patch_pr_ci_missing = 5
    sandbox_patch_pr_ci_observation = False
    sandbox_patch_github_poll = False
    sandbox_patch_check_update = False
    sandbox_patch_ready_for_review = False
    sandbox_patch_pr_ci_message = (
        "PR CI readiness blocked until PR creation evidence and CI observation authority are complete"
    )
    sandbox_patch_merge_status = "blocked_until_ci_pass"
    sandbox_patch_merge_required = (
        "github_pull_request_created, ci_checks_passed, review_approval_recorded, "
        "rollback_plan_verified, merge_approval_recorded"
    )
    sandbox_patch_merge_missing = 5
    sandbox_patch_merge_performed = False
    sandbox_patch_merge_allowed = False
    sandbox_patch_branch_write = False
    sandbox_patch_github_call = False
    sandbox_patch_merge_message = (
        "Merge readiness blocked until CI pass, review approval, rollback, and merge approval evidence are complete"
    )
    sandbox_patch_release_handoff_status = "blocked_until_terminal_closure"
    sandbox_patch_release_handoff_required = (
        "merge_execution_receipt_recorded, terminal_closure_certificate_minted, "
        "effect_reconciliation_witness_bound, rollback_retention_verified, "
        "release_notes_prepared"
    )
    sandbox_patch_release_handoff_missing = 5
    sandbox_patch_release_handoff_performed = False
    sandbox_patch_release_publication = False
    sandbox_patch_deployment = False
    sandbox_patch_public_claim = False
    sandbox_patch_release_handoff_message = (
        "Release handoff blocked until terminal closure, reconciliation, rollback, and release-note evidence are complete"
    )
    sandbox_patch_deployment_publication_status = "blocked_until_release_handoff"
    sandbox_patch_deployment_publication_required = (
        "release_handoff_packet_prepared, deployment_publication_closure_plan_verified, "
        "production_evidence_witness_bound, dns_target_binding_verified, "
        "operator_deployment_approval_recorded"
    )
    sandbox_patch_deployment_publication_missing = 5
    sandbox_patch_deployment_publication_performed = False
    sandbox_patch_dns_change = False
    sandbox_patch_production_claim = False
    sandbox_patch_public_endpoint = False
    sandbox_patch_deployment_publication_message = (
        "Deployment publication blocked until release handoff, production evidence, DNS binding, and deployment approval evidence are complete"
    )
    sandbox_patch_production_monitoring_status = "blocked_until_publication"
    sandbox_patch_production_monitoring_required = (
        "deployment_publication_witness_recorded, public_health_witness_bound, "
        "runtime_conformance_certificate_available, telemetry_monitoring_plan_verified, "
        "incident_rollback_recovery_plan_verified"
    )
    sandbox_patch_production_monitoring_missing = 5
    sandbox_patch_monitoring_activation = False
    sandbox_patch_monitor_activation = False
    sandbox_patch_alert_routing = False
    sandbox_patch_production_monitoring_message = (
        "Production monitoring blocked until deployment publication, health, runtime conformance, telemetry, and incident recovery evidence are complete"
    )
    sandbox_patch_incident_response_status = "blocked_until_monitoring"
    sandbox_patch_incident_response_required = (
        "production_monitoring_witness_recorded, incident_response_runbook_verified, "
        "rollback_execution_receipt_template_bound, containment_evidence_contract_bound, "
        "operator_incident_authority_recorded"
    )
    sandbox_patch_incident_response_missing = 5
    sandbox_patch_incident_response_performed = False
    sandbox_patch_containment = False
    sandbox_patch_rollback_execution = False
    sandbox_patch_paging = False
    sandbox_patch_incident_response_message = (
        "Incident response blocked until monitoring, runbook, rollback, containment, and operator authority evidence are complete"
    )
    sandbox_patch_recovery_closure_status = "blocked_until_incident_response"
    sandbox_patch_recovery_closure_required = (
        "incident_containment_evidence_recorded, rollback_or_replay_receipt_recorded, "
        "post_incident_verification_passed, operator_recovery_closure_approval_recorded, "
        "terminal_recovery_closure_packet_prepared"
    )
    sandbox_patch_recovery_closure_missing = 5
    sandbox_patch_recovery_closure_performed = False
    sandbox_patch_closure_certification = False
    sandbox_patch_replay_promotion = False
    sandbox_patch_post_incident_publication = False
    sandbox_patch_recovery_closure_message = (
        "Recovery closure blocked until containment, rollback or replay, verification, approval, and terminal recovery packet evidence are complete"
    )
    sandbox_patch_trust_ledger_status = "blocked_until_recovery_closure"
    sandbox_patch_trust_ledger_required = (
        "terminal_recovery_closure_packet_prepared, trust_ledger_bundle_export_prepared, "
        "evidence_artifact_hashes_recorded, operator_trust_ledger_anchor_approval_recorded, "
        "remote_submission_preflight_passed"
    )
    sandbox_patch_trust_ledger_missing = 5
    sandbox_patch_trust_ledger_anchor_performed = False
    sandbox_patch_remote_submission = False
    sandbox_patch_verification_publication = False
    sandbox_patch_trust_ledger_message = (
        "Trust ledger anchoring blocked until recovery closure, export, hash, approval, and remote submission preflight evidence are complete"
    )
    sandbox_patch_terminal_audit_export_status = "blocked_until_trust_ledger_anchor"
    sandbox_patch_terminal_audit_export_required = (
        "trust_ledger_anchor_receipt_recorded, trust_ledger_anchor_verification_passed, "
        "audit_bundle_integrity_report_recorded, operator_audit_export_approval_recorded, "
        "export_retention_boundary_verified"
    )
    sandbox_patch_terminal_audit_export_missing = 5
    sandbox_patch_terminal_audit_export_performed = False
    sandbox_patch_archive_submission = False
    sandbox_patch_external_publication = False
    sandbox_patch_terminal_audit_export_message = (
        "Terminal audit export blocked until trust ledger anchor, verification, integrity, approval, and retention evidence are complete"
    )
    sandbox_patch_foundation_closure_status = "blocked_until_terminal_audit_export"
    sandbox_patch_foundation_closure_required = (
        "terminal_audit_export_package_prepared, operator_final_closure_approval_recorded, "
        "all_no_effect_denials_preserved, open_gap_register_reviewed, "
        "next_iteration_handoff_recorded"
    )
    sandbox_patch_foundation_closure_missing = 5
    sandbox_patch_foundation_closure_certified = False
    sandbox_patch_promotion_allowed = False
    sandbox_patch_handoff_publication = False
    sandbox_patch_foundation_closure_message = (
        "Foundation closure blocked until terminal audit export, final approval, denial preservation, gap review, and next-iteration handoff evidence are complete"
    )
    sandbox_patch_iteration_resume_status = "blocked_until_foundation_closure"
    sandbox_patch_iteration_resume_required = (
        "foundation_closure_certificate_recorded, next_iteration_scope_declared, "
        "next_iteration_risk_boundary_reviewed, next_iteration_evidence_queue_seeded, "
        "operator_resume_intent_recorded"
    )
    sandbox_patch_iteration_resume_missing = 5
    sandbox_patch_next_iteration_started = False
    sandbox_patch_automatic_resume = False
    sandbox_patch_authority_carryover = False
    sandbox_patch_iteration_resume_message = (
        "Iteration resume blocked until foundation closure, next scope, risk boundary, evidence queue, and operator resume intent evidence are complete"
    )
    sandbox_patch_next_scope_admission_status = "blocked_until_iteration_resume"
    sandbox_patch_next_scope_admission_required = (
        "next_iteration_intake_packet_prepared, next_scope_boundaries_declared, "
        "next_scope_acceptance_criteria_recorded, next_scope_risk_review_recorded, "
        "next_scope_rollback_expectations_recorded"
    )
    sandbox_patch_next_scope_admission_missing = 5
    sandbox_patch_scope_admitted = False
    sandbox_patch_scope_execution_allowed = False
    sandbox_patch_scope_authority_promotion = False
    sandbox_patch_next_scope_admission_message = (
        "Next scope admission blocked until intake, boundaries, acceptance criteria, risk review, and rollback expectation evidence are complete"
    )
    operator_handoff_status = (
        "ready_for_local_resume" if friction_reduction_local_allowed else "blocked_pending_approval"
    )
    operator_handoff_forbidden = (
        "external_pr_creation, branch_push, merge, deployment, connector_write, real_world_effect"
    )
    operator_handoff_message = (
        f"Handoff ready for local resume; milestone {milestone_name}; "
        f"next evidence {evidence_progress_next_id}"
    )
    operator_handoff_boundary = "local_lab_only"
    operator_handoff_external_effects = False
    operator_review_status = "ready_for_review" if evidence_progress_pending == 0 else "awaiting_evidence"
    operator_review_ready = evidence_progress_pending == 0
    operator_review_blocker = milestone_blocker
    operator_review_next_action = (
        "review local diff and approval packet"
        if operator_review_ready
        else "complete local evidence receipts before review"
    )
    operator_review_message = (
        f"Review readiness awaiting evidence; {evidence_progress_completed}/"
        f"{evidence_progress_required} evidence receipts complete"
    )
    operator_review_pr_allowed = False
    operator_review_boundary = "local_lab_only"
    operator_review_external_effects = False
    operator_review_packet_status = "ready_for_review" if operator_review_ready else "awaiting_evidence"
    operator_review_packet_action = (
        "review local diff and approval packet"
        if operator_review_ready
        else "complete local evidence receipts before review packet"
    )
    operator_review_packet_message = (
        f"Review packet awaiting evidence; {evidence_progress_pending} evidence receipts pending"
    )
    operator_review_packet_boundary = "local_lab_only"
    operator_review_packet_external_effects = False
    operator_blocker_status = "blocked" if evidence_progress_pending > 0 else "clear"
    operator_blocker_class = "local_evidence" if evidence_progress_pending > 0 else "approval_boundary"
    operator_blocker_clearing_action = evidence_progress_next_action or "complete local evidence receipts before review"
    operator_blocker_message = (
        f"Blocker {milestone_blocker} is {operator_blocker_class}; "
        f"next evidence {evidence_progress_next_id}"
    )
    operator_blocker_boundary = "local_lab_only"
    operator_blocker_external_effects = False
    operator_packet_status = "awaiting_packets"
    operator_packet_completed = 0
    operator_packet_required = 5
    operator_packet_next = evidence_progress_next_id
    operator_packet_action = evidence_progress_next_action
    operator_packet_message = (
        f"Packet summary awaiting {operator_packet_next}; "
        f"{evidence_progress_pending} evidence receipts pending"
    )
    operator_packet_boundary = "local_lab_only"
    operator_packet_external_effects = False
    operator_authority_status = "local_lab_only"
    operator_authority_local_prepare = friction_reduction_local_allowed
    operator_authority_review_allowed = evidence_progress_pending == 0
    operator_authority_approval_now = operator_decision_review_now
    operator_authority_message = (
        "Authority local_lab_only; local preparation allowed; "
        "PR creation, branch push, connector writes, and real-world effects denied"
    )
    operator_authority_boundary = "local_lab_only"
    operator_authority_external_effects = False
    operator_risk_status = "low_local_lab"
    operator_risk_level = "low"
    operator_risk_driver = milestone_blocker
    operator_risk_scope = "local_lab_only"
    operator_risk_safe_count = safe_local_queue_count
    operator_risk_dangerous_count = dangerous_blocker_count
    operator_risk_pending_evidence = evidence_progress_pending
    operator_risk_rollback_ready = local_lab_readiness_rollback_ready
    operator_risk_message = (
        "Risk is low because execution is local-lab only; "
        f"{operator_risk_dangerous_count} dangerous zones remain blocked"
    )
    operator_risk_external_effects = False
    operator_approval_packet_status = "ready_for_approval" if evidence_progress_pending == 0 else "awaiting_evidence"
    operator_approval_packet_message = (
        f"Approval packet awaiting evidence; {evidence_progress_pending} evidence receipts pending"
    )
    operator_approval_packet_boundary = "local_lab_only"
    operator_approval_packet_external_effects = False
    operator_evidence_gap_status = "closed" if evidence_progress_pending == 0 else "evidence_incomplete"
    operator_evidence_gap_class = "local_receipts"
    operator_evidence_gap_approval_blocked = evidence_progress_pending > 0
    operator_evidence_gap_message = (
        f"Evidence gap: {evidence_progress_pending} of {evidence_progress_required} receipts still pending"
    )
    operator_evidence_gap_boundary = "local_lab_only"
    operator_evidence_gap_external_effects = False
    operator_rollback_gap_status = (
        "ready"
        if (
            local_lab_readiness_rollback_required > 0
            and local_lab_readiness_rollback_available >= local_lab_readiness_rollback_required
        )
        else "rollback_receipts_incomplete"
    )
    operator_rollback_gap_message = (
        f"Rollback gap: {local_lab_readiness_rollback_available}/"
        f"{local_lab_readiness_rollback_required} rollback receipts available"
    )
    operator_rollback_gap_ready = (
        local_lab_readiness_rollback_required > 0
        and local_lab_readiness_rollback_available >= local_lab_readiness_rollback_required
    )
    operator_rollback_gap_boundary = "local_lab_only"
    operator_rollback_gap_external_effects = False
    operator_pr_gap_status = pr_readiness_status
    operator_pr_gap_message = f"PR gap: {pr_readiness_status}; first blocker {pr_readiness_first_blocker}"
    operator_pr_gap_creation_allowed = False
    operator_pr_gap_branch_push_allowed = False
    operator_pr_gap_execution_performed = False
    operator_pr_gap_boundary = "local_lab_only"
    operator_pr_gap_external_effects = False
    pr_readiness_artifact_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(artifact_id))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('ready', False)).lower())}</td>"
        "</tr>"
        for artifact_id, item in pr_readiness_artifacts.items()
        if isinstance(item, Mapping)
    )
    if not pr_readiness_artifact_rows:
        pr_readiness_artifact_rows = '<tr><td colspan="3">No PR readiness artifacts available</td></tr>'
    operator_receipt_outcome = str(developer_workflow_operator_receipt.get("solver_outcome") or "AwaitingEvidence")
    operator_receipt_status = str(
        developer_workflow_operator_receipt.get("readiness_status") or "awaiting_sandbox_receipts"
    )
    operator_receipt_execution = False
    operator_receipt_preview = developer_workflow_operator_receipt.get("command_preview_rendered") is True
    operator_receipt_hash = str(developer_workflow_operator_receipt.get("receipt_hash") or "")
    fast_summary = mode_summary.get("fast", {}) if isinstance(mode_summary.get("fast", {}), Mapping) else {}
    balanced_summary = mode_summary.get("balanced", {}) if isinstance(mode_summary.get("balanced", {}), Mapping) else {}
    strict_summary = mode_summary.get("strict", {}) if isinstance(mode_summary.get("strict", {}), Mapping) else {}
    fast_allowed = int(fast_summary.get("allowed_count", 0) or 0)
    balanced_approval = int(balanced_summary.get("approval_required_count", 0) or 0)
    strict_approval = int(strict_summary.get("approval_required_count", 0) or 0)
    friction_mode_message = str(
        friction_mode_summary.get("operator_message")
        or f"fast mode recommended for local lab; fast allows {fast_allowed} capabilities; balanced holds {balanced_approval} approvals"
    )
    friction_mode_default = str(friction_mode_summary.get("default_mode") or "balanced")
    friction_mode_recommended = str(friction_mode_summary.get("foundation_recommended_mode") or "fast")
    friction_strict_allowed = int(friction_mode_summary.get("strict_allowed_count") or 0)
    friction_strict_approval = int(friction_mode_summary.get("strict_approval_required_count") or strict_approval)
    friction_strict_blocked = int(friction_mode_summary.get("strict_blocked_count") or 0)
    friction_balanced_allowed = int(friction_mode_summary.get("balanced_allowed_count") or 0)
    friction_balanced_approval = int(friction_mode_summary.get("balanced_approval_required_count") or balanced_approval)
    friction_balanced_blocked = int(friction_mode_summary.get("balanced_blocked_count") or 0)
    friction_fast_allowed = int(friction_mode_summary.get("fast_allowed_count") or fast_allowed)
    friction_fast_approval = int(friction_mode_summary.get("fast_approval_required_count") or 0)
    friction_fast_blocked = int(friction_mode_summary.get("fast_blocked_count") or 0)
    friction_mode_boundary = str(friction_mode_summary.get("execution_boundary") or "local_lab_only")
    friction_mode_external_effects = friction_mode_summary.get("external_effects_allowed") is True
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
      <a href="/operator/control-tower/status-receipt">status receipt</a>
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
    <h2>Control Tower Headline</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(control_headline_message)}</span>
      <span class="field"><strong>Task</strong>{escape(control_headline_task)}</span>
      <span class="field"><strong>Status</strong>{escape(control_headline_status)}</span>
      <span class="field"><strong>Headline</strong>{escape(control_headline_state)}</span>
      <span class="field"><strong>Milestone</strong>{escape(friction_reduction_milestone)}</span>
      <span class="field"><strong>Blocker</strong>{escape(friction_reduction_blocker)}</span>
      <span class="field"><strong>Mode</strong>{escape(control_headline_mode)}</span>
      <span class="field"><strong>Safe local candidates</strong>{safe_local_queue_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{dangerous_blocker_count}</span>
      <span class="field"><strong>Local continuation</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Next action</strong>{escape(control_headline_next_action)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(control_headline_next_evidence)}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(control_headline_approval_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(control_headline_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Local Lab Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(local_lab_readiness_message)}</span>
      <span class="field"><strong>Status</strong>{escape(local_lab_readiness_status)}</span>
      <span class="field"><strong>Lab mode allowed</strong>{escape(str(local_lab_readiness_lab_allowed).lower())}</span>
      <span class="field"><strong>Local continuation</strong>{escape(str(local_lab_readiness_local_allowed).lower())}</span>
      <span class="field"><strong>Safe candidates</strong>{local_lab_readiness_safe_count}</span>
      <span class="field"><strong>Pending evidence</strong>{local_lab_readiness_pending_evidence}</span>
      <span class="field"><strong>Next evidence</strong>{escape(local_lab_readiness_next_evidence)}</span>
      <span class="field"><strong>Rollback receipts</strong>{local_lab_readiness_rollback_available}/{local_lab_readiness_rollback_required}</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(local_lab_readiness_rollback_ready).lower())}</span>
      <span class="field"><strong>Next action</strong>{escape(local_lab_readiness_next_action)}</span>
      <span class="field"><strong>Boundary</strong>local_lab_only</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(local_lab_readiness_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Local Resume Plan</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(local_resume_plan_message)}</span>
      <span class="field"><strong>Status</strong>{escape(local_resume_plan_status)}</span>
      <span class="field"><strong>Continue allowed</strong>{escape(str(local_resume_plan_continue_allowed).lower())}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(local_resume_plan_mode)}</span>
      <span class="field"><strong>Milestone</strong>{escape(local_resume_plan_milestone)}</span>
      <span class="field"><strong>Blocker</strong>{escape(local_resume_plan_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(local_resume_plan_next_action)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(local_resume_plan_next_evidence)}</span>
      <span class="field"><strong>Safe candidates</strong>{local_resume_plan_safe_count}</span>
      <span class="field"><strong>Pending evidence</strong>{local_resume_plan_pending_evidence}</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(local_resume_plan_rollback_ready).lower())}</span>
      <span class="field"><strong>Approval required now</strong>{escape(str(local_resume_plan_approval_now).lower())}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(local_resume_plan_approval_boundary)}</span>
      <span class="field"><strong>Boundary</strong>{escape(local_resume_plan_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(local_resume_plan_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Workflow Monitor Summary</h2>
    <div class="task">
      <span class="field"><strong>Monitor status</strong>{escape(monitor_status)}</span>
      <span class="field"><strong>Current task</strong>{escape(monitor_current_task)}</span>
      <span class="field"><strong>Current task count</strong>{monitor_current_task_count}</span>
      <span class="field"><strong>Plan review count</strong>{monitor_plan_review_count}</span>
      <span class="field"><strong>Blocked monitor rows</strong>{monitor_blocked_count}</span>
      <span class="field"><strong>Review monitor rows</strong>{monitor_review_count}</span>
      <span class="field"><strong>Workflow status</strong>{escape(monitor_workflow_status)}</span>
      <span class="field"><strong>Readiness</strong>{escape(monitor_readiness_status)}</span>
      <span class="field"><strong>Blocker</strong>{escape(monitor_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(monitor_next_action)}</span>
      <span class="field"><strong>Execution boundary</strong>{escape(monitor_execution_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(monitor_external_effects_allowed).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Action Card</h2>
    <div class="task">
      <span class="field"><strong>Title</strong>{escape(action_card_title)}</span>
      <span class="field"><strong>Status</strong>{escape(action_card_status)}</span>
      <span class="field"><strong>Reason</strong>{escape(action_card_reason)}</span>
      <span class="field"><strong>Primary action</strong>{escape(action_card_primary_action)}</span>
      <span class="field"><strong>Action target</strong><a href="{escape(action_card_primary_href)}">{escape(action_card_primary_href)}</a></span>
      <span class="field"><strong>Focus</strong>{escape(action_card_focus_label)}; {escape(action_card_focus_status)}</span>
      <span class="field"><strong>Task</strong>{escape(action_card_task_id)}</span>
      <span class="field"><strong>Risk</strong>{escape(action_card_risk)}</span>
      <span class="field"><strong>Boundary</strong>{escape(action_card_boundary)}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(action_card_approval_required).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(action_card_external_effects_allowed).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Next Action Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(next_action_message)}</span>
      <span class="field"><strong>Status</strong>{escape(next_action_status)}</span>
      <span class="field"><strong>Reason</strong>{escape(next_action_reason)}</span>
      <span class="field"><strong>Primary action</strong>{escape(next_action_primary)}</span>
      <span class="field"><strong>Action target</strong><a href="{escape(next_action_href)}">{escape(next_action_href)}</a></span>
      <span class="field"><strong>Focus</strong>{escape(next_action_focus)}</span>
      <span class="field"><strong>Focus status</strong>{escape(next_action_focus_status)}</span>
      <span class="field"><strong>Focus source</strong>{escape(next_action_focus_source)}</span>
      <span class="field"><strong>Evidence needed</strong>{escape(next_action_required_evidence_text)}</span>
      <span class="field"><strong>Evidence count</strong>{next_action_evidence_count}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(next_action_approval_required).lower())}</span>
      <span class="field"><strong>Risk</strong>{escape(next_action_risk)}</span>
      <span class="field"><strong>Boundary</strong>{escape(next_action_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(next_action_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Approval Readiness Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(approval_readiness_message)}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(approval_readiness_required).lower())}</span>
      <span class="field"><strong>Approval status</strong>{escape(approval_readiness_status)}</span>
      <span class="field"><strong>Approval missing</strong>{escape(str(approval_readiness_missing).lower())}</span>
      <span class="field"><strong>Current blocker</strong>{escape(approval_readiness_blocker)}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(approval_readiness_boundary)}</span>
      <span class="field"><strong>Next approval action</strong>{escape(approval_readiness_next_action)}</span>
      <span class="field"><strong>Approval target</strong><a href="{escape(approval_readiness_href)}">{escape(approval_readiness_href)}</a></span>
      <span class="field"><strong>PR candidate</strong>{escape(approval_readiness_pr_status)}</span>
      <span class="field"><strong>Ready for PR preparation</strong>{escape(str(approval_readiness_ready_for_pr).lower())}</span>
      <span class="field"><strong>External PR execution allowed</strong>{escape(str(approval_readiness_external_pr_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(approval_readiness_execution_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(approval_readiness_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Decision Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_decision_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_decision_status)}</span>
      <span class="field"><strong>Decision kind</strong>{escape(operator_decision_kind)}</span>
      <span class="field"><strong>Milestone</strong>{escape(operator_decision_milestone)}</span>
      <span class="field"><strong>Blocker</strong>{escape(operator_decision_blocker)}</span>
      <span class="field"><strong>Recommended action</strong>{escape(operator_decision_action)}</span>
      <span class="field"><strong>Action target</strong><a href="{escape(operator_decision_href)}">{escape(operator_decision_href)}</a></span>
      <span class="field"><strong>Next evidence</strong>{escape(operator_decision_evidence)}</span>
      <span class="field"><strong>Review required now</strong>{escape(str(operator_decision_review_now).lower())}</span>
      <span class="field"><strong>Review before external effect</strong>{escape(str(operator_decision_review_before_external).lower())}</span>
      <span class="field"><strong>Approval status</strong>{escape(operator_decision_approval_status)}</span>
      <span class="field"><strong>Local boundary</strong>{escape(operator_decision_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_decision_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Developer Workflow Milestone</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(milestone_message)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Workflow status</strong>{escape(milestone_status)}</span>
      <span class="field"><strong>Readiness</strong>{escape(milestone_readiness)}</span>
      <span class="field"><strong>Task</strong>{escape(milestone_task)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(milestone_next_action)}</span>
      <span class="field"><strong>Receipts</strong>{milestone_receipt_completed}/{milestone_receipt_required}</span>
      <span class="field"><strong>Approval</strong>{escape(milestone_approval)}</span>
      <span class="field"><strong>PR candidate</strong>{escape(milestone_pr_candidate)}</span>
      <span class="field"><strong>Boundary</strong>{escape(milestone_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(milestone_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Developer Workflow Completion</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(workflow_completion_message)}</span>
      <span class="field"><strong>Status</strong>{escape(workflow_completion_status)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Progress</strong>{workflow_completion_progress}%</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next closure</strong>{escape(workflow_completion_condition)}</span>
      <span class="field"><strong>Terminal closure ready</strong>{escape(str(workflow_completion_terminal_ready).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(workflow_completion_pr_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(workflow_completion_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(workflow_completion_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Terminal Closure</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(terminal_closure_message)}</span>
      <span class="field"><strong>Status</strong>{escape(terminal_closure_status)}</span>
      <span class="field"><strong>Closure ready</strong>{escape(str(terminal_closure_ready).lower())}</span>
      <span class="field"><strong>Workflow status</strong>{escape(monitor_workflow_status)}</span>
      <span class="field"><strong>Completion status</strong>{escape(workflow_completion_status)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Review ready</strong>{escape(str(evidence_progress_pending == 0).lower())}</span>
      <span class="field"><strong>Approval status</strong>{escape(operator_decision_approval_status)}</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(terminal_closure_rollback_ready).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(terminal_closure_pr_allowed).lower())}</span>
      <span class="field"><strong>Branch push allowed</strong>{escape(str(terminal_closure_branch_push_allowed).lower())}</span>
      <span class="field"><strong>Next closure</strong>{escape(workflow_completion_condition)}</span>
      <span class="field"><strong>Boundary</strong>{escape(terminal_closure_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(terminal_closure_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Resume Checkpoint</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(resume_checkpoint_message)}</span>
      <span class="field"><strong>Status</strong>{escape(resume_checkpoint_status)}</span>
      <span class="field"><strong>Resume allowed</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Terminal status</strong>{escape(terminal_closure_status)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(control_system_mode)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(milestone_next_action)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(terminal_closure_rollback_ready).lower())}</span>
      <span class="field"><strong>Approval required now</strong>{escape(str(operator_decision_review_now).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(resume_checkpoint_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(resume_checkpoint_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Milestone</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_milestone_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_milestone_status)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next action</strong>{escape(evidence_progress_next_action)}</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Required receipts</strong>{escape(sandbox_milestone_required_receipts)}</span>
      <span class="field"><strong>Write authority granted</strong>{escape(str(sandbox_milestone_write_authority).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(sandbox_milestone_pr_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(sandbox_milestone_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_milestone_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Receipt Checklist</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_checklist_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_checklist_status)}</span>
      <span class="field"><strong>Next receipt</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next action</strong>{escape(evidence_progress_next_action)}</span>
      <span class="field"><strong>Receipts</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending receipts</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Sequence</strong>{escape(sandbox_checklist_sequence)}</span>
      <span class="field"><strong>Terminal review allowed</strong>{escape(str(sandbox_checklist_terminal_review).lower())}</span>
      <span class="field"><strong>Write authority granted</strong>{escape(str(sandbox_checklist_write_authority).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_checklist_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Receipt</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_message)}</span>
      <span class="field"><strong>Receipt</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_status)}</span>
      <span class="field"><strong>Required parts</strong>{escape(sandbox_patch_required_parts)}</span>
      <span class="field"><strong>Next action</strong>{escape(sandbox_patch_next_action)}</span>
      <span class="field"><strong>Rollback required</strong>{escape(str(sandbox_patch_rollback_required).lower())}</span>
      <span class="field"><strong>Dry run required</strong>{escape(str(sandbox_patch_dry_run_required).lower())}</span>
      <span class="field"><strong>Write authority granted</strong>{escape(str(sandbox_patch_write_authority).lower())}</span>
      <span class="field"><strong>Attachment allowed</strong>{escape(str(sandbox_patch_attachment_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(sandbox_patch_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Command</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_command_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_command_status)}</span>
      <span class="field"><strong>Receipt</strong>sandbox_patch_receipt</span>
      <span class="field"><strong>Command</strong>{escape(sandbox_patch_command)}</span>
      <span class="field"><strong>Expected inputs</strong>{escape(sandbox_patch_command_inputs)}</span>
      <span class="field"><strong>Expected output</strong>{escape(sandbox_patch_command_output)}</span>
      <span class="field"><strong>Execution performed</strong>{escape(str(sandbox_patch_command_execution).lower())}</span>
      <span class="field"><strong>Attachment performed</strong>{escape(str(sandbox_patch_command_attachment).lower())}</span>
      <span class="field"><strong>Write authority granted</strong>{escape(str(sandbox_patch_write_authority).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Bundle Preview</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_bundle_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_bundle_status)}</span>
      <span class="field"><strong>Bundle path</strong>{escape(sandbox_patch_bundle_path)}</span>
      <span class="field"><strong>Included receipts</strong>{escape(sandbox_patch_bundle_receipts)}</span>
      <span class="field"><strong>Validation command</strong>{escape(sandbox_patch_bundle_validation)}</span>
      <span class="field"><strong>Bundle generation performed</strong>{escape(str(sandbox_patch_bundle_generation).lower())}</span>
      <span class="field"><strong>Validation performed</strong>{escape(str(sandbox_patch_bundle_validation_performed).lower())}</span>
      <span class="field"><strong>Attachment performed</strong>{escape(str(sandbox_patch_command_attachment).lower())}</span>
      <span class="field"><strong>Write authority granted</strong>{escape(str(sandbox_patch_write_authority).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Validation Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_validation_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_validation_status)}</span>
      <span class="field"><strong>Bundle path</strong>{escape(sandbox_patch_bundle_path)}</span>
      <span class="field"><strong>Validator command</strong>{escape(sandbox_patch_bundle_validation)}</span>
      <span class="field"><strong>Required before validation</strong>{escape(sandbox_patch_validation_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_validation_missing}</span>
      <span class="field"><strong>Validation performed</strong>{escape(str(sandbox_patch_bundle_validation_performed).lower())}</span>
      <span class="field"><strong>Terminal review allowed</strong>{escape(str(sandbox_patch_validation_terminal_review).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Terminal Review</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_terminal_review_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_terminal_review_status)}</span>
      <span class="field"><strong>Review target</strong>sandbox_patch_receipt</span>
      <span class="field"><strong>Required before review</strong>{escape(sandbox_patch_terminal_review_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_terminal_review_missing}</span>
      <span class="field"><strong>Review command</strong>{escape(sandbox_patch_bundle_validation)}</span>
      <span class="field"><strong>Review performed</strong>{escape(str(sandbox_patch_terminal_review_performed).lower())}</span>
      <span class="field"><strong>Approval request allowed</strong>{escape(str(sandbox_patch_terminal_review_approval).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(sandbox_patch_terminal_review_pr).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Approval Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_approval_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_approval_status)}</span>
      <span class="field"><strong>Approval target</strong>sandbox_patch_receipt</span>
      <span class="field"><strong>Required before approval</strong>{escape(sandbox_patch_approval_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_approval_missing}</span>
      <span class="field"><strong>Approval request allowed</strong>{escape(str(sandbox_patch_terminal_review_approval).lower())}</span>
      <span class="field"><strong>Approval request performed</strong>{escape(str(sandbox_patch_approval_request_performed).lower())}</span>
      <span class="field"><strong>PR preparation allowed</strong>{escape(str(sandbox_patch_pr_preparation).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(sandbox_patch_terminal_review_pr).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch PR Preparation Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_pr_preparation_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_pr_preparation_status)}</span>
      <span class="field"><strong>Preparation target</strong>local_pr_candidate_packet</span>
      <span class="field"><strong>Required before preparation</strong>{escape(sandbox_patch_pr_preparation_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_pr_preparation_missing}</span>
      <span class="field"><strong>Preparation performed</strong>{escape(str(sandbox_patch_pr_preparation_performed).lower())}</span>
      <span class="field"><strong>PR preparation allowed</strong>{escape(str(sandbox_patch_pr_preparation).lower())}</span>
      <span class="field"><strong>Branch push allowed</strong>{escape(str(sandbox_patch_branch_push).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(sandbox_patch_terminal_review_pr).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch PR Creation Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_pr_creation_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_pr_creation_status)}</span>
      <span class="field"><strong>Creation target</strong>github_pull_request</span>
      <span class="field"><strong>Required before creation</strong>{escape(sandbox_patch_pr_creation_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_pr_creation_missing}</span>
      <span class="field"><strong>Creation performed</strong>{escape(str(sandbox_patch_pr_creation_performed).lower())}</span>
      <span class="field"><strong>Branch push allowed</strong>{escape(str(sandbox_patch_branch_push).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(sandbox_patch_terminal_review_pr).lower())}</span>
      <span class="field"><strong>Connector call allowed</strong>{escape(str(sandbox_patch_connector_call).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch PR CI Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_pr_ci_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_pr_ci_status)}</span>
      <span class="field"><strong>CI target</strong>github_pr_ci_checks</span>
      <span class="field"><strong>Required before CI</strong>{escape(sandbox_patch_pr_ci_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_pr_ci_missing}</span>
      <span class="field"><strong>CI observation performed</strong>{escape(str(sandbox_patch_pr_ci_observation).lower())}</span>
      <span class="field"><strong>GitHub poll allowed</strong>{escape(str(sandbox_patch_github_poll).lower())}</span>
      <span class="field"><strong>Check update allowed</strong>{escape(str(sandbox_patch_check_update).lower())}</span>
      <span class="field"><strong>Ready for review allowed</strong>{escape(str(sandbox_patch_ready_for_review).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Merge Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_merge_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_merge_status)}</span>
      <span class="field"><strong>Merge target</strong>protected_branch_merge</span>
      <span class="field"><strong>Required before merge</strong>{escape(sandbox_patch_merge_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_merge_missing}</span>
      <span class="field"><strong>Merge performed</strong>{escape(str(sandbox_patch_merge_performed).lower())}</span>
      <span class="field"><strong>Merge allowed</strong>{escape(str(sandbox_patch_merge_allowed).lower())}</span>
      <span class="field"><strong>Branch write allowed</strong>{escape(str(sandbox_patch_branch_write).lower())}</span>
      <span class="field"><strong>GitHub call allowed</strong>{escape(str(sandbox_patch_github_call).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Release Handoff Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_release_handoff_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_release_handoff_status)}</span>
      <span class="field"><strong>Handoff target</strong>release_handoff_packet</span>
      <span class="field"><strong>Required before handoff</strong>{escape(sandbox_patch_release_handoff_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_release_handoff_missing}</span>
      <span class="field"><strong>Handoff performed</strong>{escape(str(sandbox_patch_release_handoff_performed).lower())}</span>
      <span class="field"><strong>Release publication allowed</strong>{escape(str(sandbox_patch_release_publication).lower())}</span>
      <span class="field"><strong>Deployment allowed</strong>{escape(str(sandbox_patch_deployment).lower())}</span>
      <span class="field"><strong>Public claim allowed</strong>{escape(str(sandbox_patch_public_claim).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Deployment Publication Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_deployment_publication_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_deployment_publication_status)}</span>
      <span class="field"><strong>Publication target</strong>deployment_publication_closure_plan</span>
      <span class="field"><strong>Required before publication</strong>{escape(sandbox_patch_deployment_publication_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_deployment_publication_missing}</span>
      <span class="field"><strong>Publication performed</strong>{escape(str(sandbox_patch_deployment_publication_performed).lower())}</span>
      <span class="field"><strong>Deployment allowed</strong>{escape(str(sandbox_patch_deployment).lower())}</span>
      <span class="field"><strong>DNS change allowed</strong>{escape(str(sandbox_patch_dns_change).lower())}</span>
      <span class="field"><strong>Production claim allowed</strong>{escape(str(sandbox_patch_production_claim).lower())}</span>
      <span class="field"><strong>Public endpoint allowed</strong>{escape(str(sandbox_patch_public_endpoint).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Production Monitoring Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_production_monitoring_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_production_monitoring_status)}</span>
      <span class="field"><strong>Monitoring target</strong>production_monitoring_witness</span>
      <span class="field"><strong>Required before monitoring</strong>{escape(sandbox_patch_production_monitoring_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_production_monitoring_missing}</span>
      <span class="field"><strong>Monitoring activation performed</strong>{escape(str(sandbox_patch_monitoring_activation).lower())}</span>
      <span class="field"><strong>Monitor activation allowed</strong>{escape(str(sandbox_patch_monitor_activation).lower())}</span>
      <span class="field"><strong>Alert routing allowed</strong>{escape(str(sandbox_patch_alert_routing).lower())}</span>
      <span class="field"><strong>Production claim allowed</strong>{escape(str(sandbox_patch_production_claim).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Incident Response Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_incident_response_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_incident_response_status)}</span>
      <span class="field"><strong>Incident target</strong>incident_response_runbook</span>
      <span class="field"><strong>Required before incident response</strong>{escape(sandbox_patch_incident_response_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_incident_response_missing}</span>
      <span class="field"><strong>Incident response performed</strong>{escape(str(sandbox_patch_incident_response_performed).lower())}</span>
      <span class="field"><strong>Containment allowed</strong>{escape(str(sandbox_patch_containment).lower())}</span>
      <span class="field"><strong>Rollback execution allowed</strong>{escape(str(sandbox_patch_rollback_execution).lower())}</span>
      <span class="field"><strong>Paging allowed</strong>{escape(str(sandbox_patch_paging).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Recovery Closure Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_recovery_closure_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_recovery_closure_status)}</span>
      <span class="field"><strong>Recovery target</strong>recovery_closure_packet</span>
      <span class="field"><strong>Required before recovery closure</strong>{escape(sandbox_patch_recovery_closure_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_recovery_closure_missing}</span>
      <span class="field"><strong>Recovery closure performed</strong>{escape(str(sandbox_patch_recovery_closure_performed).lower())}</span>
      <span class="field"><strong>Closure certification allowed</strong>{escape(str(sandbox_patch_closure_certification).lower())}</span>
      <span class="field"><strong>Replay promotion allowed</strong>{escape(str(sandbox_patch_replay_promotion).lower())}</span>
      <span class="field"><strong>Post-incident publication allowed</strong>{escape(str(sandbox_patch_post_incident_publication).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Trust Ledger Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_trust_ledger_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_trust_ledger_status)}</span>
      <span class="field"><strong>Ledger target</strong>trust_ledger_anchor_packet</span>
      <span class="field"><strong>Required before trust ledger anchor</strong>{escape(sandbox_patch_trust_ledger_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_trust_ledger_missing}</span>
      <span class="field"><strong>Ledger anchor performed</strong>{escape(str(sandbox_patch_trust_ledger_anchor_performed).lower())}</span>
      <span class="field"><strong>Remote submission allowed</strong>{escape(str(sandbox_patch_remote_submission).lower())}</span>
      <span class="field"><strong>Verification publication allowed</strong>{escape(str(sandbox_patch_verification_publication).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Terminal Audit Export Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_terminal_audit_export_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_terminal_audit_export_status)}</span>
      <span class="field"><strong>Audit export target</strong>terminal_audit_export_package</span>
      <span class="field"><strong>Required before terminal audit export</strong>{escape(sandbox_patch_terminal_audit_export_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_terminal_audit_export_missing}</span>
      <span class="field"><strong>Audit export performed</strong>{escape(str(sandbox_patch_terminal_audit_export_performed).lower())}</span>
      <span class="field"><strong>Archive submission allowed</strong>{escape(str(sandbox_patch_archive_submission).lower())}</span>
      <span class="field"><strong>External publication allowed</strong>{escape(str(sandbox_patch_external_publication).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Foundation Closure Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_foundation_closure_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_foundation_closure_status)}</span>
      <span class="field"><strong>Foundation closure target</strong>foundation_closure_certificate</span>
      <span class="field"><strong>Required before foundation closure</strong>{escape(sandbox_patch_foundation_closure_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_foundation_closure_missing}</span>
      <span class="field"><strong>Foundation closure certified</strong>{escape(str(sandbox_patch_foundation_closure_certified).lower())}</span>
      <span class="field"><strong>Promotion allowed</strong>{escape(str(sandbox_patch_promotion_allowed).lower())}</span>
      <span class="field"><strong>Handoff publication allowed</strong>{escape(str(sandbox_patch_handoff_publication).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Iteration Resume Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_iteration_resume_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_iteration_resume_status)}</span>
      <span class="field"><strong>Iteration resume target</strong>next_iteration_intake_packet</span>
      <span class="field"><strong>Required before iteration resume</strong>{escape(sandbox_patch_iteration_resume_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_iteration_resume_missing}</span>
      <span class="field"><strong>Next iteration started</strong>{escape(str(sandbox_patch_next_iteration_started).lower())}</span>
      <span class="field"><strong>Automatic resume allowed</strong>{escape(str(sandbox_patch_automatic_resume).lower())}</span>
      <span class="field"><strong>Authority carryover allowed</strong>{escape(str(sandbox_patch_authority_carryover).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Sandbox Patch Next Scope Admission Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(sandbox_patch_next_scope_admission_message)}</span>
      <span class="field"><strong>Status</strong>{escape(sandbox_patch_next_scope_admission_status)}</span>
      <span class="field"><strong>Next scope target</strong>next_scope_admission_packet</span>
      <span class="field"><strong>Required before next scope admission</strong>{escape(sandbox_patch_next_scope_admission_required)}</span>
      <span class="field"><strong>Missing prerequisites</strong>{sandbox_patch_next_scope_admission_missing}</span>
      <span class="field"><strong>Scope admitted</strong>{escape(str(sandbox_patch_scope_admitted).lower())}</span>
      <span class="field"><strong>Execution allowed</strong>{escape(str(sandbox_patch_scope_execution_allowed).lower())}</span>
      <span class="field"><strong>Authority promotion allowed</strong>{escape(str(sandbox_patch_scope_authority_promotion).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(sandbox_patch_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Handoff Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_handoff_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_handoff_status)}</span>
      <span class="field"><strong>Task</strong>{escape(control_system_task)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(milestone_next_action)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(control_system_mode)}</span>
      <span class="field"><strong>Local resume allowed</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Forbidden effects</strong>{escape(operator_handoff_forbidden)}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_handoff_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_handoff_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Review Readiness</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_review_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_review_status)}</span>
      <span class="field"><strong>Review ready</strong>{escape(str(operator_review_ready).lower())}</span>
      <span class="field"><strong>Blocker</strong>{escape(operator_review_blocker)}</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next review action</strong>{escape(operator_review_next_action)}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(operator_review_pr_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_review_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_review_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Review Packet</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_review_packet_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_review_packet_status)}</span>
      <span class="field"><strong>Review ready</strong>{escape(str(operator_review_ready).lower())}</span>
      <span class="field"><strong>Blocker</strong>{escape(operator_review_blocker)}</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next packet action</strong>{escape(operator_review_packet_action)}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>Approval required now</strong>{escape(str(operator_decision_review_now).lower())}</span>
      <span class="field"><strong>PR creation allowed</strong>false</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_review_packet_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_review_packet_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Blocker Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_blocker_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_blocker_status)}</span>
      <span class="field"><strong>Active blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Blocker class</strong>{escape(operator_blocker_class)}</span>
      <span class="field"><strong>Clearing action</strong>{escape(operator_blocker_clearing_action)}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Approval required now</strong>{escape(str(operator_decision_review_now).lower())}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>Local resume allowed</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_blocker_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_blocker_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Packet Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_packet_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_packet_status)}</span>
      <span class="field"><strong>Sandbox receipts</strong>{escape(sandbox_bundle_status)}</span>
      <span class="field"><strong>Attachments</strong>{escape(sandbox_attachment_status)}</span>
      <span class="field"><strong>Local proof</strong>{escape(local_proof_status)}</span>
      <span class="field"><strong>Rollback receipts</strong>{escape(rollback_packet_status)}</span>
      <span class="field"><strong>PR readiness</strong>{escape(pr_readiness_status)}</span>
      <span class="field"><strong>Completed packets</strong>{operator_packet_completed}/{operator_packet_required}</span>
      <span class="field"><strong>Next packet</strong>{escape(operator_packet_next)}</span>
      <span class="field"><strong>Next packet action</strong>{escape(operator_packet_action)}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_packet_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_packet_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Authority Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_authority_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_authority_status)}</span>
      <span class="field"><strong>Local prepare allowed</strong>{escape(str(operator_authority_local_prepare).lower())}</span>
      <span class="field"><strong>Review allowed</strong>{escape(str(operator_authority_review_allowed).lower())}</span>
      <span class="field"><strong>Approval required now</strong>{escape(str(operator_authority_approval_now).lower())}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>PR creation allowed</strong>false</span>
      <span class="field"><strong>Branch push allowed</strong>false</span>
      <span class="field"><strong>Connector write allowed</strong>false</span>
      <span class="field"><strong>Real-world effects allowed</strong>false</span>
      <span class="field"><strong>Forbidden effects</strong>4</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_authority_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_authority_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Risk Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_risk_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_risk_status)}</span>
      <span class="field"><strong>Risk level</strong>{escape(operator_risk_level)}</span>
      <span class="field"><strong>Risk driver</strong>{escape(operator_risk_driver)}</span>
      <span class="field"><strong>Risk scope</strong>{escape(operator_risk_scope)}</span>
      <span class="field"><strong>Safe candidates</strong>{operator_risk_safe_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{operator_risk_dangerous_count}</span>
      <span class="field"><strong>Pending evidence</strong>{operator_risk_pending_evidence}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(operator_risk_rollback_ready).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_risk_scope)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_risk_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Approval Packet</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_approval_packet_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_approval_packet_status)}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(approval_readiness_required).lower())}</span>
      <span class="field"><strong>Approval status</strong>{escape(approval_readiness_status)}</span>
      <span class="field"><strong>Approval missing</strong>{escape(str(approval_readiness_missing).lower())}</span>
      <span class="field"><strong>Current blocker</strong>{escape(approval_readiness_blocker)}</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next approval action</strong>{escape(approval_readiness_next_action)}</span>
      <span class="field"><strong>Approval target</strong>{escape(approval_readiness_href)}</span>
      <span class="field"><strong>Ready for PR preparation</strong>{escape(str(approval_readiness_ready_for_pr).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_approval_packet_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_approval_packet_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Evidence Gap</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_evidence_gap_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_evidence_gap_status)}</span>
      <span class="field"><strong>Gap class</strong>{escape(operator_evidence_gap_class)}</span>
      <span class="field"><strong>Evidence</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending evidence</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next gap action</strong>{escape(evidence_progress_next_action)}</span>
      <span class="field"><strong>Approval blocked</strong>{escape(str(operator_evidence_gap_approval_blocked).lower())}</span>
      <span class="field"><strong>Local continuation allowed</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_evidence_gap_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_evidence_gap_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Rollback Gap</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_rollback_gap_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_rollback_gap_status)}</span>
      <span class="field"><strong>Readiness verdict</strong>{escape(rollback_flow_readiness_verdict)}</span>
      <span class="field"><strong>Command status</strong>{escape(rollback_flow_status)}</span>
      <span class="field"><strong>Selected artifacts</strong>{rollback_selected_count}</span>
      <span class="field"><strong>Rollback receipts</strong>{local_lab_readiness_rollback_available}/{local_lab_readiness_rollback_required}</span>
      <span class="field"><strong>Next rollback action</strong>{escape(rollback_flow_next_action)}</span>
      <span class="field"><strong>Dry-run required</strong>true</span>
      <span class="field"><strong>Execute flag required</strong>true</span>
      <span class="field"><strong>Rollback ready</strong>{escape(str(operator_rollback_gap_ready).lower())}</span>
      <span class="field"><strong>Approval status</strong>{escape(rollback_approval_status)}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_rollback_gap_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_rollback_gap_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator PR Gap</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(operator_pr_gap_message)}</span>
      <span class="field"><strong>Status</strong>{escape(operator_pr_gap_status)}</span>
      <span class="field"><strong>First blocker</strong>{escape(pr_readiness_first_blocker)}</span>
      <span class="field"><strong>Ready for external PR execution</strong>{escape(str(pr_readiness_ready).lower())}</span>
      <span class="field"><strong>Next evidence count</strong>{len(pr_readiness_next_evidence)}</span>
      <span class="field"><strong>Receipts</strong>{operator_packet_completed}/{operator_packet_required}</span>
      <span class="field"><strong>Preview only</strong>true</span>
      <span class="field"><strong>PR creation allowed</strong>{escape(str(operator_pr_gap_creation_allowed).lower())}</span>
      <span class="field"><strong>Branch push allowed</strong>{escape(str(operator_pr_gap_branch_push_allowed).lower())}</span>
      <span class="field"><strong>Execution performed</strong>{escape(str(operator_pr_gap_execution_performed).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(operator_pr_gap_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(operator_pr_gap_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Friction Reduction Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(friction_reduction_message)}</span>
      <span class="field"><strong>Status</strong>{escape(friction_reduction_status)}</span>
      <span class="field"><strong>Milestone</strong>{escape(friction_reduction_milestone)}</span>
      <span class="field"><strong>Blocker</strong>{escape(friction_reduction_blocker)}</span>
      <span class="field"><strong>Local continuation</strong>{escape(str(friction_reduction_local_allowed).lower())}</span>
      <span class="field"><strong>Pending evidence</strong>{friction_reduction_pending_evidence}</span>
      <span class="field"><strong>Next evidence</strong>{escape(friction_reduction_next_evidence)}</span>
      <span class="field"><strong>Approval boundary</strong>{escape(friction_reduction_approval_boundary)}</span>
      <span class="field"><strong>Review required now</strong>{escape(str(friction_reduction_review_now).lower())}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(friction_reduction_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Operator Dashboard Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(dashboard_summary_message)}</span>
      <span class="field"><strong>Task</strong>{escape(control_system_task)}</span>
      <span class="field"><strong>Status</strong>{escape(control_system_status)}</span>
      <span class="field"><strong>Milestone</strong>{escape(milestone_name)}</span>
      <span class="field"><strong>Blocker</strong>{escape(milestone_blocker)}</span>
      <span class="field"><strong>Next action</strong>{escape(milestone_next_action)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(control_system_mode)}</span>
      <span class="field"><strong>Receipts</strong>{escape(dashboard_summary_receipts)}</span>
      <span class="field"><strong>Pending unlocks</strong>{dashboard_summary_pending_unlocks}</span>
      <span class="field"><strong>Safe candidates</strong>{dashboard_summary_safe_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{dashboard_summary_dangerous_count}</span>
      <span class="field"><strong>Next unlock</strong>{escape(dashboard_summary_next_unlock)}</span>
      <span class="field"><strong>Action needed</strong>{escape(dashboard_summary_action)}</span>
      <span class="field"><strong>Risk</strong>{escape(control_system_risk)}</span>
      <span class="field"><strong>Boundary</strong>{escape(dashboard_summary_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(dashboard_summary_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Lab vs Real-world Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(lab_real_world_message)}</span>
      <span class="field"><strong>Lab mode allowed</strong>{escape(str(lab_real_world_lab_allowed).lower())}</span>
      <span class="field"><strong>Lab safe candidates</strong>{lab_real_world_safe_count}</span>
      <span class="field"><strong>Fast lab ready</strong>{lab_real_world_fast_ready}</span>
      <span class="field"><strong>Real-world effects allowed</strong>{escape(str(lab_real_world_effects_allowed).lower())}</span>
      <span class="field"><strong>Real-world write status</strong>{escape(lab_real_world_write_status)}</span>
      <span class="field"><strong>Dangerous blockers</strong>{lab_real_world_dangerous_count}</span>
      <span class="field"><strong>Approval required</strong>{lab_real_world_approval_count}</span>
      <span class="field"><strong>Lab boundary</strong>{escape(lab_real_world_lab_boundary)}</span>
      <span class="field"><strong>Real-world boundary</strong>{escape(lab_real_world_real_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(lab_real_world_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Approval Boundary Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(approval_boundary_message)}</span>
      <span class="field"><strong>Local automatic candidates</strong>{approval_boundary_local_auto}</span>
      <span class="field"><strong>Approval unlocks</strong>{approval_boundary_unlock_count}</span>
      <span class="field"><strong>Dangerous approvals</strong>{approval_boundary_dangerous_count}</span>
      <span class="field"><strong>PR approval required</strong>{escape(str(approval_boundary_pr_required).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(approval_boundary_name)}</span>
      <span class="field"><strong>Next approval capability</strong>{escape(approval_boundary_next_capability)}</span>
      <span class="field"><strong>Execution boundary</strong>{escape(approval_boundary_execution)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(approval_boundary_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Rollback Control Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(rollback_control_message)}</span>
      <span class="field"><strong>Rollback default</strong>{rollback_control_default_count}</span>
      <span class="field"><strong>Rollback required</strong>{rollback_control_required_count}</span>
      <span class="field"><strong>Capabilities</strong>{rollback_control_capability_count}</span>
      <span class="field"><strong>Default ready</strong>{escape(str(rollback_control_default_ready).lower())}</span>
      <span class="field"><strong>Sandbox-to-PR policy ready</strong>{escape(str(rollback_control_policy_ready).lower())}</span>
      <span class="field"><strong>Policy</strong>{escape(rollback_control_policy)}</span>
      <span class="field"><strong>Receipt source</strong>{escape(rollback_control_receipt_source)}</span>
      <span class="field"><strong>Boundary</strong>{escape(rollback_control_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(rollback_control_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Capability Registry Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(registry_message)}</span>
      <span class="field"><strong>Capabilities</strong>{registry_capability_count}</span>
      <span class="field"><strong>Preflight ready</strong>{registry_preflight_ready_count}</span>
      <span class="field"><strong>Blocked</strong>{registry_blocked_count}</span>
      <span class="field"><strong>Approval required</strong>{registry_approval_required_count}</span>
      <span class="field"><strong>Pending unlocks</strong>{registry_pending_unlock_count}</span>
      <span class="field"><strong>Next blocked capability</strong>{escape(registry_next_capability)}</span>
      <span class="field"><strong>Blocked reason</strong>{escape(registry_next_reason)}</span>
      <span class="field"><strong>Evidence needed</strong>{escape(registry_evidence_text)}</span>
      <span class="field"><strong>Evidence count</strong>{registry_evidence_count}</span>
      <span class="field"><strong>Boundary</strong>{escape(registry_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(registry_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Friction Mode Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(friction_mode_message)}</span>
      <span class="field"><strong>Default mode</strong>{escape(friction_mode_default)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(friction_mode_recommended)}</span>
      <span class="field"><strong>Strict</strong>{friction_strict_allowed} allowed; {friction_strict_approval} approval; {friction_strict_blocked} blocked</span>
      <span class="field"><strong>Balanced</strong>{friction_balanced_allowed} allowed; {friction_balanced_approval} approval; {friction_balanced_blocked} blocked</span>
      <span class="field"><strong>Fast</strong>{friction_fast_allowed} allowed; {friction_fast_approval} approval; {friction_fast_blocked} blocked</span>
      <span class="field"><strong>Boundary</strong>{escape(friction_mode_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(friction_mode_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Safe vs Dangerous Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(safe_vs_dangerous_message)}</span>
      <span class="field"><strong>Safe candidates</strong>{safe_vs_dangerous_safe_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{safe_vs_dangerous_blocked_count}</span>
      <span class="field"><strong>First safe zone</strong>{escape(safe_vs_dangerous_first_safe)}</span>
      <span class="field"><strong>First safe action</strong>{escape(safe_vs_dangerous_first_safe_action)}</span>
      <span class="field"><strong>First dangerous zone</strong>{escape(safe_vs_dangerous_first_dangerous)}</span>
      <span class="field"><strong>Dangerous reason</strong>{escape(safe_vs_dangerous_first_reason)}</span>
      <span class="field"><strong>Safe boundary</strong>{escape(safe_vs_dangerous_safe_boundary)}</span>
      <span class="field"><strong>Dangerous boundary</strong>{escape(safe_vs_dangerous_dangerous_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(safe_vs_dangerous_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Unlock Readiness Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(unlock_readiness_message)}</span>
      <span class="field"><strong>Pending unlocks</strong>{unlock_readiness_pending_count}</span>
      <span class="field"><strong>Safe candidates</strong>{unlock_readiness_safe_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{unlock_readiness_dangerous_count}</span>
      <span class="field"><strong>Next capability</strong>{escape(unlock_readiness_next_capability)}</span>
      <span class="field"><strong>Next unlock</strong>{escape(unlock_readiness_next_unlock)}</span>
      <span class="field"><strong>Evidence needed</strong>{escape(unlock_readiness_evidence_text)}</span>
      <span class="field"><strong>Evidence count</strong>{unlock_readiness_evidence_count}</span>
      <span class="field"><strong>Safe candidates ready</strong>{unlock_readiness_safe_ready}</span>
      <span class="field"><strong>Approval blockers</strong>{unlock_readiness_approval_blockers}</span>
      <span class="field"><strong>Boundary</strong>{escape(unlock_readiness_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(unlock_readiness_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Control System Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(control_system_message)}</span>
      <span class="field"><strong>Task</strong>{escape(control_system_task)}</span>
      <span class="field"><strong>Status</strong>{escape(control_system_status)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(control_system_mode)}</span>
      <span class="field"><strong>Lab mode allowed</strong>{escape(str(control_system_lab_allowed).lower())}</span>
      <span class="field"><strong>Capabilities</strong>{control_system_capability_count}</span>
      <span class="field"><strong>Pending unlocks</strong>{control_system_pending_unlock_count}</span>
      <span class="field"><strong>Safe candidates</strong>{control_system_safe_count}</span>
      <span class="field"><strong>Dangerous blockers</strong>{control_system_dangerous_count}</span>
      <span class="field"><strong>Next capability</strong>{escape(control_system_next_capability)}</span>
      <span class="field"><strong>Next unlock</strong>{escape(control_system_next_unlock)}</span>
      <span class="field"><strong>Evidence needed</strong>{escape(control_system_evidence_text)}</span>
      <span class="field"><strong>Evidence count</strong>{control_system_evidence_count}</span>
      <span class="field"><strong>Risk</strong>{escape(control_system_risk)}</span>
      <span class="field"><strong>Action needed</strong>{escape(control_system_action)}</span>
      <span class="field"><strong>Boundary</strong>{escape(control_system_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(control_system_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Safe Local Action Queue</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(safe_local_queue_message)}</span>
      <span class="field"><strong>Status</strong>{escape(safe_local_queue_status)}</span>
      <span class="field"><strong>Candidates</strong>{safe_local_queue_count}</span>
      <span class="field"><strong>First candidate</strong>{escape(safe_local_queue_first_id)}</span>
      <span class="field"><strong>First zone</strong>{escape(safe_local_queue_first_zone)}</span>
      <span class="field"><strong>First action</strong>{escape(safe_local_queue_first_action)}</span>
      <span class="field"><strong>Recommended mode</strong>{escape(safe_local_queue_mode)}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(safe_local_queue_approval_required).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(safe_local_queue_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(safe_local_queue_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Safe Automatic Action Candidates</h2>
    <table>
      <thead><tr><th>Zone</th><th>Title</th><th>Status</th><th>Primary action</th><th>Boundary</th><th>External effects</th></tr></thead>
      <tbody>{safe_action_candidate_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Dangerous Zone Blockers</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(dangerous_blocker_message)}</span>
      <span class="field"><strong>Status</strong>{escape(dangerous_blocker_status)}</span>
      <span class="field"><strong>Blockers</strong>{dangerous_blocker_count}</span>
      <span class="field"><strong>First blocker</strong>{escape(dangerous_blocker_first_id)}</span>
      <span class="field"><strong>First zone</strong>{escape(dangerous_blocker_first_zone)}</span>
      <span class="field"><strong>Reason</strong>{escape(dangerous_blocker_first_reason)}</span>
      <span class="field"><strong>Required evidence</strong>{escape(dangerous_blocker_evidence_text)}</span>
      <span class="field"><strong>Approval required</strong>{escape(str(dangerous_blocker_approval_required).lower())}</span>
      <span class="field"><strong>Rollback required</strong>{escape(str(dangerous_blocker_rollback_required).lower())}</span>
      <span class="field"><strong>Boundary</strong>{escape(dangerous_blocker_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(dangerous_blocker_external_effects).lower())}</span>
    </div>
    <table>
      <thead><tr><th>Zone</th><th>Title</th><th>Status</th><th>Reason</th><th>Evidence required</th><th>Risk</th><th>Boundary</th><th>Approval</th><th>External effects</th></tr></thead>
      <tbody>{dangerous_zone_blocker_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Developer Workflow</h2>
    <div class="task">
      <span class="field"><strong>Task</strong>{escape(task)}</span>
      <span class="field"><strong>Status</strong>{escape(status)}</span>
      <span class="field"><strong>Reason</strong>{escape(reason)}</span>
      <span class="field"><strong>Next unlock</strong>{escape(next_unlock)}</span>
      <span class="field"><strong>Risk</strong>{escape(risk)}</span>
      <span class="field"><strong>Action needed</strong>{escape(action_needed)}</span>
      <span class="field"><strong>Safe automatic zones</strong>{escape(safe_zone_text)}</span>
      <span class="field"><strong>Dangerous zones</strong>{escape(dangerous_zone_text)}</span>
      <span class="field"><strong>Rollback default</strong>{rollback_default_count} capabilities</span>
      <span class="field"><strong>Rollback required</strong>{rollback_required_count} capabilities</span>
      <span class="field"><strong>Rollback receipt</strong>{escape(rollback_receipt_status)} ({rollback_receipt_count})</span>
      <span class="field"><strong>Mode selector</strong>Fast allowed {fast_allowed}; balanced approvals {balanced_approval}; strict approvals {strict_approval}</span>
      <span class="field"><strong>Receipt checklist</strong>{checklist_done}/{checklist_required} required complete; {checklist_pending} pending</span>
      <span class="field"><strong>Local sandbox bundle</strong>{escape(sandbox_bundle_status)}; {sandbox_bundle_completed}/4 bundle receipts</span>
      <span class="field"><strong>Sandbox-to-PR</strong>{escape(sandbox_to_pr_status)}; next {escape(sandbox_to_pr_next_action)}</span>
      <span class="field"><strong>PR packet</strong>{escape(sandbox_to_pr_packet_status)}; blocker {escape(sandbox_to_pr_packet_blocker)}</span>
      <span class="field"><strong>Sandbox attachments</strong>{escape(sandbox_attachment_status)}; {sandbox_attachment_completed}/{sandbox_attachment_required} attached</span>
      <span class="field"><strong>Next attachment</strong>{escape(sandbox_next_attachment_label)}; {escape(sandbox_next_attachment_action)}</span>
      <span class="field"><strong>Local proof report</strong>{escape(local_proof_status)}; ok {escape(str(local_proof_ok).lower())}</span>
      <span class="field"><strong>Local proof progress</strong>{local_proof_completed}/{local_proof_required}; PR {escape(local_proof_pr_status)}</span>
      <span class="field"><strong>Rollback summary</strong>{escape(rollback_packet_status)}; {rollback_artifact_count} artifacts</span>
      <span class="field"><strong>Rollback executed</strong>{escape(str(rollback_execution).lower())}</span>
      <span class="field"><strong>Rollback approval</strong>{escape(rollback_approval_packet_status)}; {escape(rollback_approval_status)}</span>
      <span class="field"><strong>Rollback deletion allowed</strong>{escape(str(rollback_delete_allowed).lower())}; {rollback_selected_count} selected</span>
      <span class="field"><strong>Rollback flow command</strong>{escape(rollback_flow_status)}; {escape(rollback_flow_selected_text)}</span>
      <span class="field"><strong>Rollback readiness</strong>{escape(rollback_flow_readiness_verdict)}</span>
      <span class="field"><strong>Rollback next action</strong>{escape(rollback_flow_next_action)}</span>
      <span class="field"><strong>Rollback execution receipt</strong>{escape(rollback_execution_status)}; {escape(rollback_execution_mode)}</span>
      <span class="field"><strong>Rollback execution count</strong>{rollback_executed_count} executed; {rollback_failed_count} failed</span>
      <span class="field"><strong>PR readiness</strong>{escape(pr_readiness_status)}; blocker {escape(pr_readiness_first_blocker)}</span>
      <span class="field"><strong>Next evidence focus</strong>{escape(sandbox_to_pr_focus_label)}; {escape(sandbox_to_pr_focus_status)}</span>
      <span class="field"><strong>Run status</strong>{escape(workflow_run_status)}</span>
      <span class="field"><strong>Current stage</strong>{escape(workflow_current_task)}</span>
      <span class="field"><strong>Stages</strong>{workflow_task_count}</span>
      <span class="field"><strong>Run receipt</strong><a href="{escape(workflow_run_read_model_href)}">workflow JSON</a></span>
    </div>
  </section>
  <section>
    <h2>Next Unlock Queue</h2>
    <table>
      <thead><tr><th>Capability</th><th>Level</th><th>Next unlock</th><th>Evidence needed</th><th>Blocked</th></tr></thead>
      <tbody>{unlock_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Capability Passports</h2>
    <table>
      <thead><tr><th>Capability</th><th>Level</th><th>Status</th><th>Boundary</th><th>Fast mode</th><th>Next</th><th>Rollback</th></tr></thead>
      <tbody>{passport_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Mode Selector</h2>
    <table>
      <thead><tr><th>Capability</th><th>Level</th><th>Strict</th><th>Balanced</th><th>Fast</th><th>Recommended</th></tr></thead>
      <tbody>{mode_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Sandbox-to-PR Readiness</h2>
    <table>
      <thead><tr><th>Layer</th><th>Source</th><th>Status</th><th>Evidence</th></tr></thead>
      <tbody>{sandbox_to_pr_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Sandbox-to-PR Packet</h2>
    <table>
      <thead><tr><th>Evidence</th><th>Status</th><th>Source</th></tr></thead>
      <tbody>{sandbox_to_pr_packet_rows}</tbody>
    </table>
    <table>
      <thead><tr><th>Focus</th><th>Status</th><th>Action</th><th>Source</th></tr></thead>
      <tbody><tr><td>{escape(sandbox_to_pr_focus_label)}</td><td>{escape(sandbox_to_pr_focus_status)}</td><td>{escape(sandbox_to_pr_focus_action)}</td><td>{escape(sandbox_to_pr_focus_source)}</td></tr></tbody>
    </table>
    <table>
      <thead><tr><th>Next evidence</th><th>Status</th><th>Action</th><th>Source</th></tr></thead>
      <tbody>{sandbox_to_pr_next_evidence_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Sandbox Receipt Attachments</h2>
    <table>
      <thead><tr><th>Receipt</th><th>Status</th><th>Action</th><th>Source</th><th>Evidence</th></tr></thead>
      <tbody>{sandbox_receipt_attachment_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Local Sandbox Proof Report</h2>
    <table>
      <thead><tr><th>Artifact</th><th>Path</th></tr></thead>
      <tbody>{local_sandbox_artifact_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Local Rollback Summary</h2>
    <table>
      <thead><tr><th>Artifact</th><th>Path</th><th>Rollback command preview</th><th>Confirmation</th></tr></thead>
      <tbody>{rollback_artifact_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Local Rollback Approval</h2>
    <table>
      <thead><tr><th>Artifact</th><th>Path</th><th>Approval</th><th>Execution allowed</th><th>Rollback command preview</th></tr></thead>
      <tbody>{rollback_approval_artifact_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Local Rollback Flow Command</h2>
    <table>
      <thead><tr><th>Status</th><th>Action</th><th>Selected artifacts</th><th>Next action</th></tr></thead>
      <tbody><tr><td>{escape(rollback_flow_status)}</td><td>{escape(rollback_flow_action_label)}</td><td>{escape(rollback_flow_selected_text)}</td><td>{escape(rollback_flow_next_action)}</td></tr></tbody>
    </table>
    <table>
      <thead><tr><th>Readiness verdict</th><th>Dry-run required</th><th>Execution flag required</th><th>External effects</th></tr></thead>
      <tbody><tr><td>{escape(rollback_flow_readiness_verdict)}</td><td>true</td><td>true</td><td>false</td></tr></tbody>
    </table>
    <table>
      <thead><tr><th>Rollback summary</th><th>Approval packet</th><th>Dry-run receipt</th><th>Execution receipt</th></tr></thead>
      <tbody><tr><td><a href="{escape(rollback_flow_summary_href)}">{escape(rollback_flow_summary_path)}</a></td><td><a href="{escape(rollback_flow_approval_href)}">{escape(rollback_flow_approval_path)}</a></td><td><a href="{escape(rollback_flow_dry_run_receipt_href)}">{escape(rollback_flow_dry_run_receipt_path)}</a></td><td><a href="{escape(rollback_flow_execution_receipt_href)}">{escape(rollback_flow_execution_receipt_path)}</a></td></tr></tbody>
    </table>
    <table>
      <thead><tr><th>Summary availability</th><th>Approval availability</th><th>Execution availability</th><th>Available</th></tr></thead>
      <tbody><tr><td>{escape(str(rollback_flow_availability.get("summary") or "unavailable"))}</td><td>{escape(str(rollback_flow_availability.get("approval") or "unavailable"))}</td><td>{escape(str(rollback_flow_availability.get("execution") or "unavailable"))}</td><td>{int(rollback_flow_availability.get("available_count", 0) or 0)}/{int(rollback_flow_availability.get("required_count", 3) or 3)}</td></tr></tbody>
    </table>
    <table>
      <thead><tr><th>Dry-run command</th><th>Execute command</th></tr></thead>
      <tbody><tr><td><code>{escape(rollback_flow_command)}</code></td><td><code>{escape(rollback_flow_execute_command)}</code></td></tr></tbody>
    </table>
  </section>
  <section>
    <h2>Local Rollback Execution Receipt</h2>
    <table>
      <thead><tr><th>Artifact</th><th>Path</th><th>Action</th><th>Workspace</th><th>Pre-exists</th><th>Post-exists</th><th>Error</th></tr></thead>
      <tbody>{rollback_execution_artifact_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>PR Readiness Bundle</h2>
    <div class="metrics">
      <span class="metric">Status: {escape(pr_readiness_status)}</span>
      <span class="metric">First blocker: {escape(pr_readiness_first_blocker)}</span>
      <span class="metric">External execution: {escape(str(pr_readiness_ready).lower())}</span>
      <span class="metric">Next evidence: {escape(", ".join(str(item) for item in pr_readiness_next_evidence) or "none")}</span>
    </div>
    <p>{escape(pr_readiness_summary)}</p>
    <table>
      <thead><tr><th>Artifact</th><th>Status</th><th>Ready</th></tr></thead>
      <tbody>{pr_readiness_artifact_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Developer Workflow Operator Receipt</h2>
    <div class="metrics">
      <span class="metric">Outcome: {escape(operator_receipt_outcome)}</span>
      <span class="metric">Readiness: {escape(operator_receipt_status)}</span>
      <span class="metric">Command preview: {escape(str(operator_receipt_preview).lower())}</span>
      <span class="metric">Execution performed: {escape(str(operator_receipt_execution).lower())}</span>
      <span class="metric">Receipt hash: {escape(operator_receipt_hash[:16] or "unavailable")}</span>
    </div>
  </section>
  <section>
    <h2>Evidence Progress Summary</h2>
    <div class="task">
      <span class="field"><strong>Message</strong>{escape(evidence_progress_message)}</span>
      <span class="field"><strong>Status</strong>{escape(evidence_progress_status)}</span>
      <span class="field"><strong>Completed</strong>{evidence_progress_completed}/{evidence_progress_required}</span>
      <span class="field"><strong>Pending</strong>{evidence_progress_pending}</span>
      <span class="field"><strong>Next evidence</strong>{escape(evidence_progress_next_id)}</span>
      <span class="field"><strong>Next action</strong>{escape(evidence_progress_next_action)}</span>
      <span class="field"><strong>Blocker</strong>{escape(evidence_progress_blocker)}</span>
      <span class="field"><strong>Sandbox receipts</strong>{evidence_progress_sandbox}/{evidence_progress_sandbox_required}</span>
      <span class="field"><strong>Sandbox bundle</strong>{evidence_progress_bundle}/{evidence_progress_bundle_required}</span>
      <span class="field"><strong>Rollback receipts</strong>{evidence_progress_rollback}/{evidence_progress_rollback_required}</span>
      <span class="field"><strong>PR next evidence</strong>{evidence_progress_pr_next}</span>
      <span class="field"><strong>Boundary</strong>{escape(evidence_progress_boundary)}</span>
      <span class="field"><strong>External effects allowed</strong>{escape(str(evidence_progress_external_effects).lower())}</span>
    </div>
  </section>
  <section>
    <h2>Receipt Checklist</h2>
    <table>
      <thead><tr><th>Receipt</th><th>Status</th><th>Stage</th><th>Required</th><th>Evidence</th></tr></thead>
      <tbody>{checklist_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Local Sandbox Bundle Receipts</h2>
    <table>
      <thead><tr><th>Receipt</th><th>Status</th><th>Stage</th><th>Required</th><th>Evidence</th></tr></thead>
      <tbody>{sandbox_bundle_rows}</tbody>
    </table>
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
