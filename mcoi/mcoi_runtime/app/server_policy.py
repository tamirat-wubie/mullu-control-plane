"""Purpose: bounded startup policy helpers for the governed HTTP server.

Governance scope: environment posture, startup validation, and bounded warning
formatting only.
Dependencies: standard library types only.
Invariants:
  - Boolean env flag parsing stays bounded and deterministic.
  - Pilot and production startup rejects forbidden memory persistence.
  - Pilot and production startup rejects empty governed CORS origins.
  - Warning text remains bounded and does not reflect caller-supplied names.
"""

from __future__ import annotations


def _env_flag(name: str, env: dict[str, str] | None = None) -> bool | None:
    """Resolve a boolean environment flag from a string mapping."""
    source = env or {}
    raw = source.get(name)
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("value must be a boolean flag")


def _bounded_bootstrap_warning(component: str, exc: Exception) -> str:
    """Return a bounded startup warning without leaking backend detail."""
    return f"{component} bootstrap failed ({type(exc).__name__})"


def _bounded_lifecycle_warning(component: str, exc: Exception) -> str:
    """Return a bounded lifecycle warning without leaking backend detail."""
    return f"{component} failed ({type(exc).__name__})"


def _append_bounded_warning(warnings: list[str], component: str, exc: Exception) -> None:
    """Record a bounded warning once per component/error class pair."""
    warning = _bounded_lifecycle_warning(component, exc)
    if warning not in warnings:
        warnings.append(warning)


def _validate_db_backend_for_env(db_backend: str, env: str) -> str | None:
    """Validate the persistence backend against environment posture."""
    if db_backend == "memory" and env in ("pilot", "production"):
        raise RuntimeError(
            f"MULLU_DB_BACKEND=memory is not allowed in {env} environment. "
            "Set MULLU_DB_BACKEND=postgresql to ensure governance state survives restarts."
        )
    if db_backend == "memory" and env not in ("local_dev", "test", ""):
        return (
            "MULLU_DB_BACKEND=memory in non-dev environment. "
            "All state will be lost on restart. Set MULLU_DB_BACKEND=postgresql for production."
        )
    return None


def _resolve_cors_origins(raw_value: str | None, env: str) -> list[str]:
    """Resolve the configured CORS origins for the current environment."""
    default = (
        "http://localhost:3000,http://localhost:8080"
        if env in ("local_dev", "test")
        else ""
    )
    configured = raw_value if raw_value is not None else default
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _validate_cors_origins_for_env(origins: list[str], env: str) -> str | None:
    """Validate CORS posture against environment expectations."""
    if origins:
        return None
    if env in ("pilot", "production"):
        raise RuntimeError(
            "MULLU_CORS_ORIGINS must be set in pilot or production environment. "
            "Set explicit origins (for example https://app.mullu.io) for governed CORS."
        )
    if env not in ("local_dev", "test", ""):
        return (
            "MULLU_CORS_ORIGINS is empty in non-dev environment. "
            "Set explicit origins (for example https://app.mullu.io) for production CORS."
        )
    return None
