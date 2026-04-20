"""Bootstrap helpers for the governed server.

Purpose: isolate small server bootstrap utilities from the main FastAPI module.
Governance scope: [OCE, CDCV, UWMA]
Dependencies: environment mapping, bounded bootstrap warning helper, optional field encryption module.
Invariants: UTC clock output remains ISO formatted, field-encryption startup posture remains bounded and deterministic.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable


def utc_clock() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def init_field_encryption_from_env(
    *,
    env: Mapping[str, str],
    bounded_bootstrap_warning: Callable[[str, Exception], str],
    key_provider_factory: Callable[[], Any] | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    """Build optional field encryption and expose explicit startup posture."""
    state = {
        "configured": bool(env.get("MULLU_ENCRYPTION_KEY", "")),
        "enabled": False,
        "aes_available": False,
        "warning": "",
    }
    if not state["configured"]:
        return None, state

    from mcoi_runtime.core.field_encryption import EnvKeyProvider, FieldEncryptor

    try:
        provider = key_provider_factory() if key_provider_factory is not None else EnvKeyProvider()
        if not provider.available:
            state["warning"] = "field encryption configured but no key available"
            return None, state
        encryptor = FieldEncryptor(provider)
        state["enabled"] = True
        state["aes_available"] = encryptor.aes_available
        return encryptor, state
    except Exception as exc:
        state["warning"] = bounded_bootstrap_warning("field encryption", exc)
        return None, state


def validate_field_encryption_posture(
    *,
    env: str,
    db_backend: str,
    field_encryption_bootstrap: Mapping[str, Any],
) -> None:
    """Reject production PostgreSQL startup when field encryption is not enabled."""
    if env == "production" and db_backend == "postgresql":
        if not bool(field_encryption_bootstrap.get("enabled", False)):
            raise RuntimeError(
                "Production PostgreSQL deployments require field encryption to be enabled."
            )
