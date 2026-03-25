"""Purpose: canonical pilot control plane contracts for deployment hardening.
Governance scope: runtime launch manifests, startup validation, operator authority,
    checkpoint verification, and runtime state export typing.
Dependencies: shared contract base helpers, supervisor contracts.
Invariants:
  - Launch manifests are immutable once created.
  - Startup validation is fail-closed: any missing subsystem or invalid policy fails.
  - Operator authority levels are enforced — not advisory.
  - Checkpoint import requires verification before acceptance.
  - Runtime state exports are deterministic snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StartupVerdict(StrEnum):
    """Outcome of startup validation."""

    PASSED = "passed"
    FAILED_MISSING_SUBSYSTEM = "failed_missing_subsystem"
    FAILED_INVALID_POLICY = "failed_invalid_policy"
    FAILED_INVALID_CONFIG = "failed_invalid_config"


class OperatorAuthority(StrEnum):
    """Authority level of an operator.

    Controls which actions the operator is permitted to perform.
    VIEWER can only read health/state; OPERATOR can pause/resume/checkpoint;
    ADMIN can start/stop/halt/set-canary/import-checkpoint.
    """

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class CheckpointImportVerdict(StrEnum):
    """Outcome of checkpoint import verification."""

    ACCEPTED = "accepted"
    REJECTED_MISSING_SCOPE = "rejected_missing_scope"
    REJECTED_INVALID_HASH = "rejected_invalid_hash"
    REJECTED_EPOCH_MISMATCH = "rejected_epoch_mismatch"
    REJECTED_MALFORMED = "rejected_malformed"


class DegradedReason(StrEnum):
    """Why the runtime is in degraded state."""

    NONE = "none"
    SUPERVISOR_HALTED = "supervisor_halted"
    HIGH_ERROR_RATE = "high_error_rate"
    BACKPRESSURE_ACTIVE = "backpressure_active"
    LIVELOCK_DETECTED = "livelock_detected"
    CHECKPOINT_STALE = "checkpoint_stale"


# ---------------------------------------------------------------------------
# Launch manifest (frozen at startup)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeLaunchManifest(ContractRecord):
    """Immutable snapshot of the runtime configuration at launch time.

    Created during startup validation and frozen — cannot be modified
    once the runtime transitions to RUNNING. Serves as the auditable
    reference for what configuration the runtime was launched with.
    """

    manifest_id: str
    policy_id: str
    epoch_id: str
    canary_mode: str
    subsystem_ids: tuple[str, ...]
    config_snapshot: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "canary_mode", require_non_empty_text(self.canary_mode, "canary_mode"))
        object.__setattr__(self, "subsystem_ids", require_non_empty_tuple(self.subsystem_ids, "subsystem_ids"))
        object.__setattr__(self, "config_snapshot", freeze_value(self.config_snapshot))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Startup validation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StartupValidationResult(ContractRecord):
    """Outcome of pre-launch validation.

    Fail-closed: the runtime MUST NOT start if verdict != PASSED.
    """

    validation_id: str
    verdict: StartupVerdict
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    detail: str
    validated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_id", require_non_empty_text(self.validation_id, "validation_id"))
        if not isinstance(self.verdict, StartupVerdict):
            raise ValueError("verdict must be a StartupVerdict value")
        object.__setattr__(self, "checks_passed", freeze_value(list(self.checks_passed)))
        object.__setattr__(self, "checks_failed", freeze_value(list(self.checks_failed)))
        object.__setattr__(self, "detail", require_non_empty_text(self.detail, "detail"))
        object.__setattr__(self, "validated_at", require_datetime_text(self.validated_at, "validated_at"))

    @property
    def is_valid(self) -> bool:
        return self.verdict == StartupVerdict.PASSED


# ---------------------------------------------------------------------------
# Checkpoint import verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheckpointImportResult(ContractRecord):
    """Outcome of verifying an imported checkpoint before acceptance.

    Checks: required scopes present, hashes non-empty, epoch compatibility.
    """

    import_id: str
    checkpoint_id: str
    verdict: CheckpointImportVerdict
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    verified_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "import_id", require_non_empty_text(self.import_id, "import_id"))
        object.__setattr__(self, "checkpoint_id", require_non_empty_text(self.checkpoint_id, "checkpoint_id"))
        if not isinstance(self.verdict, CheckpointImportVerdict):
            raise ValueError("verdict must be a CheckpointImportVerdict value")
        object.__setattr__(self, "checks_passed", freeze_value(list(self.checks_passed)))
        object.__setattr__(self, "checks_failed", freeze_value(list(self.checks_failed)))
        object.__setattr__(self, "verified_at", require_datetime_text(self.verified_at, "verified_at"))

    @property
    def accepted(self) -> bool:
        return self.verdict == CheckpointImportVerdict.ACCEPTED


# ---------------------------------------------------------------------------
# Runtime state export (for dashboards and external control)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeStateExport(ContractRecord):
    """Deterministic runtime state snapshot for external consumption.

    Surfaces everything a dashboard, operator console, or external
    controller needs to observe the runtime without direct access.
    """

    export_id: str
    status: str
    canary_mode: str
    supervisor_phase: str
    tick_number: int
    event_count: int
    open_obligations: int
    checkpoint_count: int
    journal_length: int
    consecutive_errors: int
    consecutive_idle_ticks: int
    is_healthy: bool
    is_ready: bool
    is_degraded: bool
    degraded_reasons: tuple[str, ...]
    overall_confidence: float
    last_error: str
    action_count: int
    manifest_id: str
    exported_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "export_id", require_non_empty_text(self.export_id, "export_id"))
        object.__setattr__(self, "status", require_non_empty_text(self.status, "status"))
        object.__setattr__(self, "canary_mode", require_non_empty_text(self.canary_mode, "canary_mode"))
        object.__setattr__(self, "supervisor_phase", require_non_empty_text(self.supervisor_phase, "supervisor_phase"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        object.__setattr__(self, "event_count", require_non_negative_int(self.event_count, "event_count"))
        object.__setattr__(self, "open_obligations", require_non_negative_int(self.open_obligations, "open_obligations"))
        object.__setattr__(self, "checkpoint_count", require_non_negative_int(self.checkpoint_count, "checkpoint_count"))
        object.__setattr__(self, "journal_length", require_non_negative_int(self.journal_length, "journal_length"))
        object.__setattr__(self, "consecutive_errors", require_non_negative_int(self.consecutive_errors, "consecutive_errors"))
        object.__setattr__(self, "consecutive_idle_ticks", require_non_negative_int(self.consecutive_idle_ticks, "consecutive_idle_ticks"))
        object.__setattr__(self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"))
        object.__setattr__(self, "degraded_reasons", freeze_value(list(self.degraded_reasons)))
        object.__setattr__(self, "last_error", require_non_empty_text(self.last_error, "last_error"))
        object.__setattr__(self, "action_count", require_non_negative_int(self.action_count, "action_count"))
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "exported_at", require_datetime_text(self.exported_at, "exported_at"))


# ---------------------------------------------------------------------------
# Sealed launch package contracts (Phase 38)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BuildFingerprint(ContractRecord):
    """Immutable build identification for the runtime binary.

    Captures version, commit hash, build timestamp, and Python/Rust
    versions to enable precise reproducibility and incident tracing.
    """

    fingerprint_id: str
    version: str
    commit_hash: str
    build_timestamp: str
    python_version: str
    rust_version: str
    platform: str

    def __post_init__(self) -> None:
        for f in ("fingerprint_id", "version", "commit_hash", "python_version",
                   "rust_version", "platform"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "build_timestamp", require_datetime_text(self.build_timestamp, "build_timestamp"))


@dataclass(frozen=True, slots=True)
class PolicyBundleManifest(ContractRecord):
    """Immutable record of the governance policy bundle in force at launch.

    References the active bundle by ID, version, and hash so that
    post-incident audits can reconstruct exactly which rules governed.
    """

    manifest_id: str
    bundle_id: str
    bundle_name: str
    bundle_version: str
    rule_count: int
    bundle_hash: str
    loaded_at: str

    def __post_init__(self) -> None:
        for f in ("manifest_id", "bundle_id", "bundle_name", "bundle_version", "bundle_hash"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "rule_count", require_non_negative_int(self.rule_count, "rule_count"))
        object.__setattr__(self, "loaded_at", require_datetime_text(self.loaded_at, "loaded_at"))


@dataclass(frozen=True, slots=True)
class ProviderCapabilityManifest(ContractRecord):
    """Snapshot of all registered providers and their capabilities at launch.

    Records which providers were available, their health status,
    and which connector types they support.
    """

    manifest_id: str
    provider_ids: tuple[str, ...]
    connector_ids: tuple[str, ...]
    provider_count: int
    connector_count: int
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "provider_ids", freeze_value(list(self.provider_ids)))
        object.__setattr__(self, "connector_ids", freeze_value(list(self.connector_ids)))
        object.__setattr__(self, "provider_count", require_non_negative_int(self.provider_count, "provider_count"))
        object.__setattr__(self, "connector_count", require_non_negative_int(self.connector_count, "connector_count"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))


@dataclass(frozen=True, slots=True)
class CheckpointCompatibilityManifest(ContractRecord):
    """Records checkpoint format version and subsystem compatibility.

    Used to reject checkpoint imports from incompatible runtime versions.
    """

    manifest_id: str
    checkpoint_format_version: str
    supported_scopes: tuple[str, ...]
    epoch_id: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        object.__setattr__(self, "checkpoint_format_version", require_non_empty_text(self.checkpoint_format_version, "checkpoint_format_version"))
        object.__setattr__(self, "supported_scopes", require_non_empty_tuple(self.supported_scopes, "supported_scopes"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class StartupValidationReport(ContractRecord):
    """Comprehensive startup validation report aggregating all checks.

    This is the full audit trail of what was validated before the
    runtime was permitted to start.
    """

    report_id: str
    validation_result: StartupValidationResult
    build_fingerprint: BuildFingerprint
    policy_bundle_manifest: PolicyBundleManifest | None
    provider_manifest: ProviderCapabilityManifest | None
    checkpoint_compatibility: CheckpointCompatibilityManifest
    subsystem_count: int
    all_passed: bool
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        if not isinstance(self.validation_result, StartupValidationResult):
            raise ValueError("validation_result must be a StartupValidationResult")
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint must be a BuildFingerprint")
        if self.policy_bundle_manifest is not None and not isinstance(self.policy_bundle_manifest, PolicyBundleManifest):
            raise ValueError("policy_bundle_manifest must be a PolicyBundleManifest or None")
        if self.provider_manifest is not None and not isinstance(self.provider_manifest, ProviderCapabilityManifest):
            raise ValueError("provider_manifest must be a ProviderCapabilityManifest or None")
        if not isinstance(self.checkpoint_compatibility, CheckpointCompatibilityManifest):
            raise ValueError("checkpoint_compatibility must be a CheckpointCompatibilityManifest")
        object.__setattr__(self, "subsystem_count", require_non_negative_int(self.subsystem_count, "subsystem_count"))
        if not isinstance(self.all_passed, bool):
            raise ValueError("all_passed must be a boolean")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class SealedLaunchPackage(ContractRecord):
    """The complete, immutable launch package that seals the runtime.

    The runtime MUST NOT start without producing a SealedLaunchPackage.
    Once sealed, the package is frozen and auditable for the runtime's
    entire lifetime.
    """

    package_id: str
    launch_manifest: RuntimeLaunchManifest
    build_fingerprint: BuildFingerprint
    policy_bundle_manifest: PolicyBundleManifest | None
    provider_manifest: ProviderCapabilityManifest | None
    checkpoint_compatibility: CheckpointCompatibilityManifest
    startup_report: StartupValidationReport
    sealed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", require_non_empty_text(self.package_id, "package_id"))
        if not isinstance(self.launch_manifest, RuntimeLaunchManifest):
            raise ValueError("launch_manifest must be a RuntimeLaunchManifest")
        if not isinstance(self.build_fingerprint, BuildFingerprint):
            raise ValueError("build_fingerprint must be a BuildFingerprint")
        if self.policy_bundle_manifest is not None and not isinstance(self.policy_bundle_manifest, PolicyBundleManifest):
            raise ValueError("policy_bundle_manifest must be a PolicyBundleManifest or None")
        if self.provider_manifest is not None and not isinstance(self.provider_manifest, ProviderCapabilityManifest):
            raise ValueError("provider_manifest must be a ProviderCapabilityManifest or None")
        if not isinstance(self.checkpoint_compatibility, CheckpointCompatibilityManifest):
            raise ValueError("checkpoint_compatibility must be a CheckpointCompatibilityManifest")
        if not isinstance(self.startup_report, StartupValidationReport):
            raise ValueError("startup_report must be a StartupValidationReport")
        object.__setattr__(self, "sealed_at", require_datetime_text(self.sealed_at, "sealed_at"))

    @property
    def is_valid(self) -> bool:
        return self.startup_report.all_passed


# ---------------------------------------------------------------------------
# Operator authority mapping
# ---------------------------------------------------------------------------


# Actions each authority level is permitted to perform
AUTHORITY_ACTIONS: Mapping[OperatorAuthority, frozenset[str]] = {
    OperatorAuthority.VIEWER: frozenset({
        "health",
        "export_state",
        "list_actions",
    }),
    OperatorAuthority.OPERATOR: frozenset({
        "health",
        "export_state",
        "list_actions",
        "pause",
        "resume",
        "checkpoint",
        "tick",
    }),
    OperatorAuthority.ADMIN: frozenset({
        "health",
        "export_state",
        "list_actions",
        "pause",
        "resume",
        "checkpoint",
        "tick",
        "start",
        "stop",
        "mark_error",
        "set_canary_mode",
        "import_checkpoint",
        "restore",
    }),
}
