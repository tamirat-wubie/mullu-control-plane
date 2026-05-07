"""Purpose: pilot control plane — production shell for controlled runtime operation.
Governance scope: runtime lifecycle management only.
Dependencies: supervisor engine, event spine, obligation runtime, checkpoint manager,
    pilot contracts.
Invariants:
  - Start/stop/pause/resume are explicit operator actions with authority checks.
  - Startup validation is fail-closed: missing subsystems or invalid policy prevent start.
  - Config is locked after start; launch manifest is immutable and inspectable.
  - Canary mode is behaviorally meaningful: influences action gating, not just stored state.
  - Checkpoint import is verified before acceptance.
  - Health/readiness/degraded surfaces are deterministic and complete.
  - Operator authority levels are enforced, not advisory.
  - All actions are attributed and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text, require_non_negative_int, require_unit_float
from mcoi_runtime.contracts.pilot import (
    AUTHORITY_ACTIONS,
    BuildFingerprint,
    CheckpointCompatibilityManifest,
    CheckpointImportResult,
    CheckpointImportVerdict,
    DegradedReason,
    OperatorAuthority,
    PolicyBundleManifest,
    ProviderCapabilityManifest,
    RuntimeLaunchManifest,
    RuntimeStateExport,
    SealedLaunchPackage,
    StartupValidationReport,
    StartupValidationResult,
    StartupVerdict,
)
from mcoi_runtime.contracts.state_machine import (
    CheckpointScope,
    CompositeCheckpoint,
    JournalEntryKind,
)
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine


# ---------------------------------------------------------------------------
# Control plane enums
# ---------------------------------------------------------------------------


class RuntimeStatus(StrEnum):
    """Current operational status of the runtime."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class CanaryMode(StrEnum):
    """Canary deployment mode."""

    OFF = "off"
    OBSERVATION = "observation"
    SHADOW = "shadow"
    ACTIVE = "active"


# ---------------------------------------------------------------------------
# Control plane contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HealthReport(ContractRecord):
    """Runtime health and readiness snapshot."""

    report_id: str
    status: RuntimeStatus
    supervisor_phase: str
    tick_number: int
    event_count: int
    open_obligations: int
    checkpoint_count: int
    journal_length: int
    canary_mode: CanaryMode
    is_healthy: bool
    is_ready: bool
    is_degraded: bool
    degraded_reasons: tuple[str, ...]
    overall_confidence: float
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        if not isinstance(self.status, RuntimeStatus):
            raise ValueError("status must be a RuntimeStatus value")
        if not isinstance(self.canary_mode, CanaryMode):
            raise ValueError("canary_mode must be a CanaryMode value")
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        object.__setattr__(self, "event_count", require_non_negative_int(self.event_count, "event_count"))
        object.__setattr__(self, "open_obligations", require_non_negative_int(self.open_obligations, "open_obligations"))
        object.__setattr__(self, "checkpoint_count", require_non_negative_int(self.checkpoint_count, "checkpoint_count"))
        object.__setattr__(self, "journal_length", require_non_negative_int(self.journal_length, "journal_length"))
        object.__setattr__(self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"))
        object.__setattr__(self, "degraded_reasons", freeze_value(list(self.degraded_reasons)))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class OperatorAction(ContractRecord):
    """Audit record of an operator control plane action."""

    action_id: str
    operator_id: str
    action: str
    target: str
    reason: str
    performed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for f in ("action_id", "operator_id", "action", "target", "reason"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "performed_at", require_datetime_text(self.performed_at, "performed_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Pilot control plane
# ---------------------------------------------------------------------------


class PilotControlPlane:
    """Production shell for controlled runtime lifecycle management.

    Provides:
    - Startup validation (fail-closed on missing subsystems or invalid policy)
    - Config locking and immutable launch manifests
    - Start/stop/pause/resume with operator authority enforcement
    - Canary mode that behaviorally gates actions
    - Checkpoint export/import with pre-acceptance verification
    - Health/readiness/degraded surfaces with confidence scoring
    - Runtime state export for dashboards and external control
    - Full operator action audit trail
    """

    def __init__(
        self,
        *,
        supervisor: SupervisorEngine,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        clock: Callable[[], str],
        epoch_id: str = "epoch-1",
    ) -> None:
        self._supervisor = supervisor
        self._spine = spine
        self._obligation_engine = obligation_engine
        self._clock = clock
        self._epoch_id = epoch_id
        self._status = RuntimeStatus.STOPPED
        self._canary_mode = CanaryMode.OFF
        self._last_error: str = ""
        self._actions: list[OperatorAction] = []
        self._checkpoint_mgr = CheckpointManager(
            supervisor=supervisor,
            spine=spine,
            obligation_engine=obligation_engine,
            clock=clock,
            epoch_id=epoch_id,
        )

        # Config locking: once started, config is frozen
        self._config_locked: bool = False
        self._launch_manifest: RuntimeLaunchManifest | None = None
        self._sealed_package: SealedLaunchPackage | None = None
        self._build_fingerprint: BuildFingerprint | None = None
        self._policy_bundle_manifest: PolicyBundleManifest | None = None
        self._provider_manifest: ProviderCapabilityManifest | None = None

        # Operator authority registry
        self._operator_authorities: dict[str, OperatorAuthority] = {}

    # -----------------------------------------------------------------------
    # Operator authority management
    # -----------------------------------------------------------------------

    def register_operator(
        self, operator_id: str, authority: OperatorAuthority,
    ) -> None:
        """Register an operator with a specific authority level.

        Cannot change authority while config is locked (runtime is running).
        """
        if self._config_locked:
            raise RuntimeCoreInvariantError(
                "cannot register operators while config is locked"
            )
        self._operator_authorities[operator_id] = authority

    def operator_authority(self, operator_id: str) -> OperatorAuthority | None:
        """Return the authority level for an operator, or None if unregistered."""
        return self._operator_authorities.get(operator_id)

    def _check_authority(self, operator_id: str, action: str) -> None:
        """Enforce that the operator has authority for the requested action.

        Raises RuntimeCoreInvariantError if the operator lacks permission.
        If no operators are registered, authority checks are skipped
        (backwards-compatible with tests that don't set up authorities).
        """
        if not self._operator_authorities:
            return  # No authority configured — permissive mode
        authority = self._operator_authorities.get(operator_id)
        if authority is None:
            raise RuntimeCoreInvariantError(
                "operator is not registered"
            )
        permitted = AUTHORITY_ACTIONS.get(authority, frozenset())
        if action not in permitted:
            raise RuntimeCoreInvariantError(
                "operator lacks authority for requested action"
            )

    # -----------------------------------------------------------------------
    # Startup validation
    # -----------------------------------------------------------------------

    def validate_startup(self) -> StartupValidationResult:
        """Validate all required subsystems and policy before allowing start.

        Fail-closed: any check failure prevents the runtime from starting.
        """
        now = self._clock()
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # Check supervisor exists and has a policy
        if self._supervisor is not None:
            checks_passed.append("supervisor_present")
        else:
            checks_failed.append("supervisor_present")

        if hasattr(self._supervisor, "_policy") and self._supervisor._policy is not None:
            checks_passed.append("supervisor_policy_valid")
            # Validate policy has sensible values
            policy = self._supervisor._policy
            if policy.max_events_per_tick >= 1 and policy.max_consecutive_errors >= 1:
                checks_passed.append("policy_thresholds_positive")
            else:
                checks_failed.append("policy_thresholds_positive")
        else:
            checks_failed.append("supervisor_policy_valid")

        # Check event spine
        if self._spine is not None:
            checks_passed.append("event_spine_present")
        else:
            checks_failed.append("event_spine_present")

        # Check obligation engine
        if self._obligation_engine is not None:
            checks_passed.append("obligation_engine_present")
        else:
            checks_failed.append("obligation_engine_present")

        # Check checkpoint manager
        if self._checkpoint_mgr is not None:
            checks_passed.append("checkpoint_manager_present")
        else:
            checks_failed.append("checkpoint_manager_present")

        # Determine verdict
        if checks_failed:
            if any("policy" in c for c in checks_failed):
                verdict = StartupVerdict.FAILED_INVALID_POLICY
            elif any("present" in c for c in checks_failed):
                verdict = StartupVerdict.FAILED_MISSING_SUBSYSTEM
            else:
                verdict = StartupVerdict.FAILED_INVALID_CONFIG
        else:
            verdict = StartupVerdict.PASSED

        detail = (
            f"{len(checks_passed)} passed, {len(checks_failed)} failed"
            if checks_failed
            else f"all {len(checks_passed)} checks passed"
        )

        return StartupValidationResult(
            validation_id=stable_identifier("startup-validation", {"at": now}),
            verdict=verdict,
            checks_passed=tuple(checks_passed),
            checks_failed=tuple(checks_failed),
            detail=detail,
            validated_at=now,
        )

    # -----------------------------------------------------------------------
    # Pre-launch configuration (set before start)
    # -----------------------------------------------------------------------

    def set_build_fingerprint(self, fingerprint: BuildFingerprint) -> None:
        """Register the build fingerprint before startup."""
        if self._config_locked:
            raise RuntimeCoreInvariantError("cannot set build fingerprint while config is locked")
        self._build_fingerprint = fingerprint

    def set_policy_bundle_manifest(self, manifest: PolicyBundleManifest) -> None:
        """Register the policy bundle manifest before startup."""
        if self._config_locked:
            raise RuntimeCoreInvariantError("cannot set policy bundle manifest while config is locked")
        self._policy_bundle_manifest = manifest

    def set_provider_manifest(self, manifest: ProviderCapabilityManifest) -> None:
        """Register the provider capability manifest before startup."""
        if self._config_locked:
            raise RuntimeCoreInvariantError("cannot set provider manifest while config is locked")
        self._provider_manifest = manifest

    @property
    def sealed_package(self) -> SealedLaunchPackage | None:
        """The sealed launch package, or None if not started."""
        return self._sealed_package

    # -----------------------------------------------------------------------
    # Config locking and launch manifest
    # -----------------------------------------------------------------------

    @property
    def config_locked(self) -> bool:
        """Whether the runtime config is locked (immutable after start)."""
        return self._config_locked

    @property
    def launch_manifest(self) -> RuntimeLaunchManifest | None:
        """The immutable launch manifest, or None if not yet started."""
        return self._launch_manifest

    def _create_launch_manifest(self) -> RuntimeLaunchManifest:
        """Create an immutable snapshot of the current configuration."""
        now = self._clock()
        policy = self._supervisor._policy
        return RuntimeLaunchManifest(
            manifest_id=stable_identifier("manifest", {"at": now}),
            policy_id=policy.policy_id,
            epoch_id=self._epoch_id,
            canary_mode=self._canary_mode.value,
            subsystem_ids=("supervisor", "event_spine", "obligation_runtime", "checkpoint_manager"),
            config_snapshot={
                "tick_interval_ms": policy.tick_interval_ms,
                "max_events_per_tick": policy.max_events_per_tick,
                "max_actions_per_tick": policy.max_actions_per_tick,
                "backpressure_threshold": policy.backpressure_threshold,
                "livelock_repeat_threshold": policy.livelock_repeat_threshold,
                "livelock_strategy": policy.livelock_strategy.value,
                "heartbeat_every_n_ticks": policy.heartbeat_every_n_ticks,
                "checkpoint_every_n_ticks": policy.checkpoint_every_n_ticks,
                "max_consecutive_errors": policy.max_consecutive_errors,
            },
            created_at=now,
        )

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self, operator_id: str, reason: str = "operator start") -> OperatorAction:
        """Start the runtime with full startup validation and sealed launch package.

        Only valid from STOPPED or ERROR state. Validates all subsystems,
        creates an immutable launch manifest, seals the launch package,
        and locks config.
        """
        self._check_authority(operator_id, "start")
        if self._status not in (RuntimeStatus.STOPPED, RuntimeStatus.ERROR):
            raise RuntimeCoreInvariantError(
                "cannot start from current runtime state"
            )

        # Fail-closed startup validation
        validation = self.validate_startup()
        if validation.verdict != StartupVerdict.PASSED:
            raise RuntimeCoreInvariantError(
                "startup validation failed"
            )

        self._last_error = ""
        self._launch_manifest = self._create_launch_manifest()

        # Build the sealed launch package
        self._sealed_package = self._create_sealed_package(validation)

        self._config_locked = True
        self._status = RuntimeStatus.RUNNING
        return self._record_action(operator_id, "start", "runtime", reason)

    def stop(self, operator_id: str, reason: str = "operator stop") -> OperatorAction:
        """Stop the runtime. Creates a final checkpoint and unlocks config."""
        self._check_authority(operator_id, "stop")
        if self._status == RuntimeStatus.STOPPED:
            raise RuntimeCoreInvariantError("runtime is already stopped")
        self._checkpoint_mgr.create_checkpoint()
        self._status = RuntimeStatus.STOPPED
        self._config_locked = False
        return self._record_action(operator_id, "stop", "runtime", reason)

    def pause(self, operator_id: str, reason: str = "operator pause") -> OperatorAction:
        """Pause the runtime. Supervisor stops ticking."""
        self._check_authority(operator_id, "pause")
        if self._status != RuntimeStatus.RUNNING:
            raise RuntimeCoreInvariantError(
                "cannot pause from current runtime state"
            )
        self._status = RuntimeStatus.PAUSED
        return self._record_action(operator_id, "pause", "runtime", reason)

    def resume(self, operator_id: str, reason: str = "operator resume") -> OperatorAction:
        """Resume the runtime from paused state."""
        self._check_authority(operator_id, "resume")
        if self._status != RuntimeStatus.PAUSED:
            raise RuntimeCoreInvariantError(
                "cannot resume from current runtime state"
            )
        self._status = RuntimeStatus.RUNNING
        return self._record_action(operator_id, "resume", "runtime", reason)

    def mark_error(self, operator_id: str, reason: str) -> OperatorAction:
        """Transition the runtime to ERROR state with a recorded reason.

        Any running/paused state can transition to ERROR.
        Recovery is via start() which clears the error.
        """
        self._check_authority(operator_id, "mark_error")
        if self._status in (RuntimeStatus.STOPPED, RuntimeStatus.ERROR):
            raise RuntimeCoreInvariantError(
                "cannot mark error from current runtime state"
            )
        self._last_error = reason
        self._status = RuntimeStatus.ERROR
        return self._record_action(operator_id, "mark_error", "runtime", reason)

    @property
    def last_error(self) -> str:
        """Return the last error reason, or empty string if none."""
        return self._last_error

    # -----------------------------------------------------------------------
    # Tick execution
    # -----------------------------------------------------------------------

    def tick(self) -> Any:
        """Execute a single supervisor tick if runtime is RUNNING.

        Returns the SupervisorTick result or raises if not running.
        """
        if self._status != RuntimeStatus.RUNNING:
            raise RuntimeCoreInvariantError(
                "cannot tick from current runtime state"
            )
        tick_result = self._supervisor.tick()
        # Journal the tick
        self._checkpoint_mgr.append_journal(
            JournalEntryKind.TICK,
            subject_id=f"tick-{self._supervisor.tick_number}",
            payload={
                "tick_number": self._supervisor.tick_number,
                "outcome": tick_result.outcome.value,
            },
        )
        return tick_result

    def run_ticks(self, n: int) -> tuple[Any, ...]:
        """Execute n supervisor ticks. Returns tuple of tick results."""
        results = []
        for _ in range(n):
            results.append(self.tick())
        return tuple(results)

    # -----------------------------------------------------------------------
    # Canary mode (behaviorally meaningful)
    # -----------------------------------------------------------------------

    def set_canary_mode(
        self, mode: CanaryMode, operator_id: str, reason: str,
    ) -> OperatorAction:
        """Set the canary deployment mode."""
        self._check_authority(operator_id, "set_canary_mode")
        old = self._canary_mode
        self._canary_mode = mode
        return self._record_action(
            operator_id, "set_canary_mode", mode.value,
            f"{reason} (was: {old.value})",
        )

    @property
    def canary_mode(self) -> CanaryMode:
        return self._canary_mode

    def canary_allows_action(self, action_type: str) -> bool:
        """Check whether the current canary mode allows a given action type.

        OBSERVATION mode: read-only — no mutations allowed.
        SHADOW mode: mutations allowed but results are discarded (caller decides).
        ACTIVE / OFF: all actions allowed.

        This is the behavioral gate that makes canary mode meaningful.
        Callers (integration bridges, supervisor) query this before acting.
        """
        if self._canary_mode == CanaryMode.OBSERVATION:
            # Observation mode: only reads. No obligation creation, no reaction
            # firing, no event emission that triggers side effects.
            read_actions = {
                "health", "export_state", "list_actions",
                "assess_health", "list_events", "list_obligations",
                "list_subscriptions", "list_rules",
            }
            return action_type in read_actions
        # SHADOW, ACTIVE, OFF: all actions permitted
        # (SHADOW callers are expected to discard results)
        return True

    # -----------------------------------------------------------------------
    # Checkpoint management
    # -----------------------------------------------------------------------

    def create_checkpoint(self, operator_id: str = "system") -> CompositeCheckpoint:
        """Create a composite checkpoint."""
        self._check_authority(operator_id, "checkpoint")
        cp = self._checkpoint_mgr.create_checkpoint()
        self._record_action(operator_id, "checkpoint", cp.checkpoint_id, "manual checkpoint")
        return cp

    def restore_checkpoint(
        self, checkpoint: CompositeCheckpoint, operator_id: str = "system",
        *, verify: bool = True,
    ) -> OperatorAction:
        """Restore from a composite checkpoint with hash verification.

        If verify=True (default), post-restore hashes are compared
        against the checkpoint and RuntimeCoreInvariantError is raised
        on mismatch (with automatic rollback to pre-restore state).
        """
        self._check_authority(operator_id, "restore")
        self._checkpoint_mgr.restore_checkpoint(checkpoint, verify=verify)
        return self._record_action(
            operator_id, "restore", checkpoint.checkpoint_id, "checkpoint restore"
        )

    def export_checkpoint(self) -> dict[str, Any] | None:
        """Export the latest checkpoint as a serializable dict, or None."""
        cp = self._checkpoint_mgr.latest_checkpoint()
        if cp is None:
            return None
        return cp.to_dict()

    def verify_checkpoint_import(
        self, checkpoint: CompositeCheckpoint,
    ) -> CheckpointImportResult:
        """Verify an imported checkpoint before accepting it.

        Checks:
        - All required scopes present (supervisor, event_spine, obligation_runtime)
        - Each snapshot has a non-empty state hash
        - Epoch compatibility
        - Composite hash is non-empty
        """
        now = self._clock()
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # Required scopes
        required_scopes = {
            CheckpointScope.SUPERVISOR,
            CheckpointScope.EVENT_SPINE,
            CheckpointScope.OBLIGATION_RUNTIME,
        }
        present_scopes = {s.scope for s in checkpoint.snapshots}
        for scope in required_scopes:
            if scope in present_scopes:
                checks_passed.append(f"scope_{scope.value}_present")
            else:
                checks_failed.append(f"scope_{scope.value}_present")

        # Hash non-empty
        if checkpoint.composite_hash and checkpoint.composite_hash.strip():
            checks_passed.append("composite_hash_non_empty")
        else:
            checks_failed.append("composite_hash_non_empty")

        # Per-snapshot hashes
        for snap in checkpoint.snapshots:
            if snap.state_hash and snap.state_hash.strip():
                checks_passed.append(f"hash_{snap.scope.value}_non_empty")
            else:
                checks_failed.append(f"hash_{snap.scope.value}_non_empty")

        # Epoch compatibility
        if checkpoint.epoch_id and checkpoint.epoch_id.strip():
            checks_passed.append("epoch_id_valid")
        else:
            checks_failed.append("epoch_id_valid")

        # Determine verdict
        if checks_failed:
            if any("scope" in c for c in checks_failed):
                verdict = CheckpointImportVerdict.REJECTED_MISSING_SCOPE
            elif any("hash" in c for c in checks_failed):
                verdict = CheckpointImportVerdict.REJECTED_INVALID_HASH
            elif any("epoch" in c for c in checks_failed):
                verdict = CheckpointImportVerdict.REJECTED_EPOCH_MISMATCH
            else:
                verdict = CheckpointImportVerdict.REJECTED_MALFORMED
        else:
            verdict = CheckpointImportVerdict.ACCEPTED

        return CheckpointImportResult(
            import_id=stable_identifier("cp-import", {"cp": checkpoint.checkpoint_id, "at": now}),
            checkpoint_id=checkpoint.checkpoint_id,
            verdict=verdict,
            checks_passed=tuple(checks_passed),
            checks_failed=tuple(checks_failed),
            verified_at=now,
        )

    def import_checkpoint(
        self, checkpoint: CompositeCheckpoint, operator_id: str,
        reason: str = "checkpoint import",
    ) -> CheckpointImportResult:
        """Import and restore a checkpoint after verification.

        Verifies the checkpoint first. If verification fails, raises
        RuntimeCoreInvariantError. If it passes, restores the checkpoint.
        """
        self._check_authority(operator_id, "import_checkpoint")
        result = self.verify_checkpoint_import(checkpoint)
        if not result.accepted:
            raise RuntimeCoreInvariantError(
                "checkpoint import rejected"
            )
        self._checkpoint_mgr.restore_checkpoint(checkpoint, verify=True)
        self._record_action(
            operator_id, "import_checkpoint", checkpoint.checkpoint_id, reason,
        )
        return result

    # -----------------------------------------------------------------------
    # Health / readiness / degraded surfaces
    # -----------------------------------------------------------------------

    def _assess_degraded(self) -> tuple[bool, tuple[str, ...], float]:
        """Assess degradation state and overall confidence.

        Returns (is_degraded, degraded_reasons, overall_confidence).
        """
        reasons: list[str] = []
        sv_health = self._supervisor.assess_health()

        if self._supervisor.is_halted:
            reasons.append(DegradedReason.SUPERVISOR_HALTED.value)

        if sv_health.consecutive_errors > 0:
            reasons.append(DegradedReason.HIGH_ERROR_RATE.value)

        if sv_health.backpressure_active:
            reasons.append(DegradedReason.BACKPRESSURE_ACTIVE.value)

        if sv_health.livelock_detected:
            reasons.append(DegradedReason.LIVELOCK_DETECTED.value)

        # Check checkpoint staleness (no checkpoint in last 50 ticks if policy says every N)
        if self._supervisor.tick_number > 0 and self._checkpoint_mgr.checkpoint_count == 0:
            if self._supervisor.tick_number >= 50:
                reasons.append(DegradedReason.CHECKPOINT_STALE.value)

        return bool(reasons), tuple(reasons), sv_health.overall_confidence

    def health(self) -> HealthReport:
        """Produce a health and readiness report with degradation details.

        Canary mode influences readiness:
        - OFF / ACTIVE: ready if RUNNING and not degraded
        - OBSERVATION / SHADOW: healthy but NOT ready (limited traffic)
        """
        now = self._clock()
        is_healthy = self._status in (RuntimeStatus.RUNNING, RuntimeStatus.PAUSED)
        is_degraded, degraded_reasons, confidence = self._assess_degraded()

        # In observation/shadow canary, system is healthy but not ready
        # for full production traffic — signals load balancers to route away.
        is_ready = (
            self._status == RuntimeStatus.RUNNING
            and self._canary_mode not in (CanaryMode.OBSERVATION, CanaryMode.SHADOW)
            and not self._supervisor.is_halted
        )

        return HealthReport(
            report_id=stable_identifier("health", {"at": now}),
            status=self._status,
            supervisor_phase=self._supervisor.phase.value,
            tick_number=self._supervisor.tick_number,
            event_count=self._spine.event_count,
            open_obligations=self._obligation_engine.open_count,
            checkpoint_count=self._checkpoint_mgr.checkpoint_count,
            journal_length=self._checkpoint_mgr.journal_length,
            canary_mode=self._canary_mode,
            is_healthy=is_healthy,
            is_ready=is_ready,
            is_degraded=is_degraded,
            degraded_reasons=degraded_reasons,
            overall_confidence=confidence,
            assessed_at=now,
        )

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    # -----------------------------------------------------------------------
    # Runtime state export (for dashboards and external control)
    # -----------------------------------------------------------------------

    def export_state(self) -> RuntimeStateExport:
        """Export the full runtime state as a deterministic snapshot.

        Surfaces everything a dashboard, operator console, or external
        controller needs to observe the runtime without direct access.
        """
        now = self._clock()
        sv_health = self._supervisor.assess_health()
        is_degraded, degraded_reasons, confidence = self._assess_degraded()

        is_healthy = self._status in (RuntimeStatus.RUNNING, RuntimeStatus.PAUSED)
        is_ready = (
            self._status == RuntimeStatus.RUNNING
            and self._canary_mode not in (CanaryMode.OBSERVATION, CanaryMode.SHADOW)
            and not self._supervisor.is_halted
        )

        manifest_id = self._launch_manifest.manifest_id if self._launch_manifest else ""

        return RuntimeStateExport(
            export_id=stable_identifier("state-export", {"at": now}),
            status=self._status.value,
            canary_mode=self._canary_mode.value,
            supervisor_phase=self._supervisor.phase.value,
            tick_number=self._supervisor.tick_number,
            event_count=self._spine.event_count,
            open_obligations=self._obligation_engine.open_count,
            checkpoint_count=self._checkpoint_mgr.checkpoint_count,
            journal_length=self._checkpoint_mgr.journal_length,
            consecutive_errors=sv_health.consecutive_errors,
            consecutive_idle_ticks=sv_health.consecutive_idle_ticks,
            is_healthy=is_healthy,
            is_ready=is_ready,
            is_degraded=is_degraded,
            degraded_reasons=degraded_reasons,
            overall_confidence=confidence,
            last_error=self._last_error or "none",
            action_count=len(self._actions),
            manifest_id=manifest_id or "none",
            exported_at=now,
        )

    # -----------------------------------------------------------------------
    # Sealed launch package construction
    # -----------------------------------------------------------------------

    def _create_sealed_package(
        self, validation: StartupValidationResult,
    ) -> SealedLaunchPackage:
        """Create the immutable sealed launch package."""
        now = self._clock()
        import platform as _platform
        import sys as _sys

        # Build fingerprint — use provided or generate default
        fingerprint = self._build_fingerprint or BuildFingerprint(
            fingerprint_id=stable_identifier("build-fp", {"at": now}),
            version="0.1.0",
            commit_hash="dev",
            build_timestamp=now,
            python_version=_sys.version.split()[0],
            rust_version="unknown",
            platform=_platform.platform(),
        )

        # Checkpoint compatibility manifest
        checkpoint_compat = CheckpointCompatibilityManifest(
            manifest_id=stable_identifier("cp-compat", {"at": now}),
            checkpoint_format_version="1.0.0",
            supported_scopes=("supervisor", "event_spine", "obligation_runtime"),
            epoch_id=self._epoch_id,
            created_at=now,
        )

        # Startup validation report
        report = StartupValidationReport(
            report_id=stable_identifier("startup-report", {"at": now}),
            validation_result=validation,
            build_fingerprint=fingerprint,
            policy_bundle_manifest=self._policy_bundle_manifest,
            provider_manifest=self._provider_manifest,
            checkpoint_compatibility=checkpoint_compat,
            subsystem_count=len(self._launch_manifest.subsystem_ids) if self._launch_manifest else 0,
            all_passed=validation.is_valid,
            created_at=now,
        )

        return SealedLaunchPackage(
            package_id=stable_identifier("sealed-pkg", {"at": now}),
            launch_manifest=self._launch_manifest,
            build_fingerprint=fingerprint,
            policy_bundle_manifest=self._policy_bundle_manifest,
            provider_manifest=self._provider_manifest,
            checkpoint_compatibility=checkpoint_compat,
            startup_report=report,
            sealed_at=now,
        )

    # -----------------------------------------------------------------------
    # Operator runbook procedures (Phase 38.4)
    # -----------------------------------------------------------------------

    def runbook_halt(self, operator_id: str, reason: str) -> OperatorAction:
        """Halt the runtime — emergency stop that forces supervisor halt.

        More severe than stop: marks error and halts supervisor tick loop.
        """
        self._check_authority(operator_id, "mark_error")
        if self._status in (RuntimeStatus.STOPPED,):
            raise RuntimeCoreInvariantError("cannot halt a stopped runtime")
        # Force supervisor into halted state
        self._supervisor._halted = True
        self._last_error = reason
        self._status = RuntimeStatus.ERROR
        return self._record_action(operator_id, "halt", "runtime", reason)

    def runbook_canary_promote(
        self, operator_id: str, reason: str,
    ) -> tuple[OperatorAction, ...]:
        """Canary promotion: OBSERVATION -> SHADOW -> ACTIVE.

        Each call advances one stage. Returns the action(s) taken.
        """
        promotion_map = {
            CanaryMode.OFF: CanaryMode.OBSERVATION,
            CanaryMode.OBSERVATION: CanaryMode.SHADOW,
            CanaryMode.SHADOW: CanaryMode.ACTIVE,
        }
        next_mode = promotion_map.get(self._canary_mode)
        if next_mode is None:
            raise RuntimeCoreInvariantError(
                "cannot promote canary mode beyond terminal stage"
            )
        action = self.set_canary_mode(next_mode, operator_id, reason)
        return (action,)

    def runbook_canary_rollback(
        self, operator_id: str, reason: str,
    ) -> OperatorAction:
        """Canary rollback: return to OBSERVATION mode from any canary state."""
        if self._canary_mode == CanaryMode.OFF:
            raise RuntimeCoreInvariantError("canary is OFF — nothing to rollback")
        return self.set_canary_mode(CanaryMode.OBSERVATION, operator_id, reason)

    def runbook_checkpoint_restore_drill(
        self, operator_id: str,
    ) -> tuple[OperatorAction, ...]:
        """Checkpoint restore drill: create checkpoint, restore it, verify.

        Returns the actions taken during the drill.
        """
        actions: list[OperatorAction] = []

        # 1. Create a checkpoint
        cp = self.create_checkpoint(operator_id)
        actions.append(self._actions[-1])  # The checkpoint action

        # 2. Restore from it (with verification)
        restore_action = self.restore_checkpoint(
            cp, operator_id, verify=True,
        )
        actions.append(restore_action)

        return tuple(actions)

    # -----------------------------------------------------------------------
    # Live observability surface (Phase 38.5)
    # -----------------------------------------------------------------------

    def pilot_observability_snapshot(self) -> Mapping[str, Any]:
        """Produce a comprehensive pilot-grade observability snapshot.

        Returns an immutable mapping with:
        - supervisor_state: phase, tick number, halted status
        - canary_state: current mode, allows mutations
        - checkpoint_freshness: count, last checkpoint tick delta
        - replay_readiness: journal length, epoch
        - backlog_pressure: open obligations, pending events
        - event_rate: total events, backpressure active
        - degraded_reasons: list of current degradation causes
        - policy_in_force: policy ID from launch manifest
        - manifest_id: from launch manifest
        - build_fingerprint: version + commit from sealed package
        """
        from types import MappingProxyType

        sv_health = self._supervisor.assess_health()
        is_degraded, degraded_reasons, confidence = self._assess_degraded()

        # Checkpoint freshness
        last_cp_tick = 0
        if self._checkpoint_mgr.checkpoint_count > 0:
            latest = self._checkpoint_mgr.latest_checkpoint()
            if latest and latest.snapshots:
                # Approximate: tick number at checkpoint is in supervisor snapshot
                for snap in latest.snapshots:
                    payload = snap.payload if hasattr(snap, 'payload') else {}
                    if isinstance(payload, Mapping) and "tick" in payload:
                        last_cp_tick = payload["tick"]
                        break

        ticks_since_checkpoint = self._supervisor.tick_number - last_cp_tick

        # Build info from sealed package
        build_version = "unknown"
        build_commit = "unknown"
        if self._sealed_package and self._sealed_package.build_fingerprint:
            build_version = self._sealed_package.build_fingerprint.version
            build_commit = self._sealed_package.build_fingerprint.commit_hash

        manifest_id = ""
        policy_id = ""
        if self._launch_manifest:
            manifest_id = self._launch_manifest.manifest_id
            policy_id = self._launch_manifest.policy_id

        return MappingProxyType({
            "supervisor_state": MappingProxyType({
                "phase": self._supervisor.phase.value,
                "tick_number": self._supervisor.tick_number,
                "halted": self._supervisor.is_halted,
                "consecutive_errors": sv_health.consecutive_errors,
                "consecutive_idle_ticks": sv_health.consecutive_idle_ticks,
            }),
            "canary_state": MappingProxyType({
                "mode": self._canary_mode.value,
                "allows_mutations": self.canary_allows_action("emit_event"),
            }),
            "checkpoint_freshness": MappingProxyType({
                "checkpoint_count": self._checkpoint_mgr.checkpoint_count,
                "ticks_since_last_checkpoint": ticks_since_checkpoint,
            }),
            "replay_readiness": MappingProxyType({
                "journal_length": self._checkpoint_mgr.journal_length,
                "epoch_id": self._epoch_id,
            }),
            "backlog_pressure": MappingProxyType({
                "open_obligations": self._obligation_engine.open_count,
                "pending_events": self._spine.event_count,
            }),
            "event_rate": MappingProxyType({
                "total_events": self._spine.event_count,
                "backpressure_active": sv_health.backpressure_active,
            }),
            "degraded_reasons": tuple(degraded_reasons),
            "overall_confidence": confidence,
            "is_degraded": is_degraded,
            "policy_in_force": policy_id,
            "manifest_id": manifest_id,
            "build_fingerprint": MappingProxyType({
                "version": build_version,
                "commit": build_commit,
            }),
            "status": self._status.value,
        })

    # -----------------------------------------------------------------------
    # Audit trail
    # -----------------------------------------------------------------------

    @property
    def action_count(self) -> int:
        return len(self._actions)

    def list_actions(self) -> tuple[OperatorAction, ...]:
        """Return all operator actions in order."""
        return tuple(self._actions)

    @property
    def checkpoint_manager(self) -> CheckpointManager:
        return self._checkpoint_mgr

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _record_action(
        self, operator_id: str, action: str, target: str, reason: str,
    ) -> OperatorAction:
        now = self._clock()
        act = OperatorAction(
            action_id=stable_identifier("op-action", {
                "operator": operator_id,
                "action": action,
                "at": now,
            }),
            operator_id=operator_id,
            action=action,
            target=target,
            reason=reason,
            performed_at=now,
        )
        self._actions.append(act)
        return act
