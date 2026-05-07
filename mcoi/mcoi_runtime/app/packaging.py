"""Purpose: deployment packaging — environment validation and release manifest.
Governance scope: packaging, validation, and deployment readiness only.
Dependencies: deployment profiles, app config.
Invariants:
  - Environment validation fails closed on missing requirements.
  - Profile validation happens before startup, not during.
  - Package info is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.app.deployment_profiles import get_profile, BUILTIN_PROFILES
from mcoi_runtime.contracts.autonomy import AutonomyMode


PLATFORM_NAME = "Mullu Platform MCOI Runtime"
PLATFORM_VERSION = "0.1.0"


def _bounded_validation_error(summary: str, exc: Exception) -> str:
    """Return a stable validation failure without raw backend detail."""
    return f"{summary} ({type(exc).__name__})"


class ValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class EnvironmentValidation:
    status: ValidationStatus
    checks: tuple[ValidationCheck, ...]
    profile_id: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status is ValidationStatus.VALID


@dataclass(frozen=True, slots=True)
class PackageInfo:
    name: str
    version: str
    profile_count: int
    test_count: int
    doc_count: int


def validate_profile(profile_id: str) -> EnvironmentValidation:
    """Validate that a deployment profile is well-formed and usable."""
    checks: list[ValidationCheck] = []

    # Check profile exists
    profile = get_profile(profile_id)
    if profile is None:
        checks.append(ValidationCheck("profile_exists", False, f"profile '{profile_id}' not found"))
        return EnvironmentValidation(status=ValidationStatus.INVALID, checks=tuple(checks), profile_id=profile_id)
    checks.append(ValidationCheck("profile_exists", True, f"profile '{profile_id}' found"))

    # Check autonomy mode is valid
    try:
        AutonomyMode(profile.autonomy_mode)
        checks.append(ValidationCheck("autonomy_mode_valid", True, f"mode '{profile.autonomy_mode}' is valid"))
    except ValueError:
        checks.append(ValidationCheck("autonomy_mode_valid", False, f"invalid mode: {profile.autonomy_mode}"))

    # Check executor routes non-empty
    if profile.enabled_executor_routes:
        checks.append(ValidationCheck("executor_routes", True, f"{len(profile.enabled_executor_routes)} routes configured"))
    else:
        checks.append(ValidationCheck("executor_routes", False, "no executor routes configured"))

    # Check observer routes non-empty
    if profile.enabled_observer_routes:
        checks.append(ValidationCheck("observer_routes", True, f"{len(profile.enabled_observer_routes)} observers configured"))
    else:
        checks.append(ValidationCheck("observer_routes", False, "no observer routes configured"))

    # Check retention
    if profile.max_retention_days > 0:
        checks.append(ValidationCheck("retention_policy", True, f"{profile.max_retention_days} day retention"))
    else:
        checks.append(ValidationCheck("retention_policy", False, "retention days must be positive"))

    all_passed = all(c.passed for c in checks)
    return EnvironmentValidation(
        status=ValidationStatus.VALID if all_passed else ValidationStatus.INVALID,
        checks=tuple(checks),
        profile_id=profile_id,
    )


def validate_environment() -> EnvironmentValidation:
    """Validate the runtime environment is ready."""
    checks: list[ValidationCheck] = []

    # Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 12):
        checks.append(ValidationCheck("python_version", True, f"Python {py_version}"))
    else:
        checks.append(ValidationCheck("python_version", False, f"Python {py_version} < 3.12"))

    # Check that profiles load
    try:
        profile_count = len(BUILTIN_PROFILES)
        checks.append(ValidationCheck("profiles_loaded", True, f"{profile_count} profiles available"))
    except Exception as exc:
        checks.append(ValidationCheck("profiles_loaded", False, _bounded_validation_error("profile load error", exc)))

    # Check imports
    try:
        from mcoi_runtime.app.bootstrap import bootstrap_runtime
        checks.append(ValidationCheck("bootstrap_importable", True, "bootstrap module loads"))
    except Exception as exc:
        checks.append(ValidationCheck("bootstrap_importable", False, _bounded_validation_error("import error", exc)))

    all_passed = all(c.passed for c in checks)
    return EnvironmentValidation(
        status=ValidationStatus.VALID if all_passed else ValidationStatus.INVALID,
        checks=tuple(checks),
    )


def get_package_info() -> PackageInfo:
    """Return platform package information."""
    return PackageInfo(
        name=PLATFORM_NAME,
        version=PLATFORM_VERSION,
        profile_count=len(BUILTIN_PROFILES),
        test_count=774,  # Updated with each phase
        doc_count=20,
    )
