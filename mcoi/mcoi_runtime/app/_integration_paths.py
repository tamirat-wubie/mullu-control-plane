"""Shared helpers for env-driven integration modules.

Purpose: provide a single auditable contract for hosted-store path validation
environment-flag parsing, and optional route-prefix validation across the
``app/*_integration.py`` family.
Governance scope: precondition-contract single source of truth for hosted
persistence paths, feature-flag truthy parsing, and hosted route prefixes.
Dependencies: standard library only.
Invariants: validator preconditions and env-flag truthy set match the prior
per-module implementations exactly; route prefixes are absolute, non-root API
paths with no whitespace or empty path segments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal


_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})


def env_flag(value: str | None) -> bool:
    """Return whether an environment flag value is enabled."""

    return str(value or "").strip().lower() in _TRUTHY_VALUES


def validate_route_prefix(
    value: str | None,
    *,
    default: str,
    env_name: str,
) -> str:
    """Return a bounded FastAPI route prefix from environment input."""

    prefix = str(default if value is None else value).strip().rstrip("/") or default
    if not prefix.startswith("/"):
        raise RuntimeError(f"{env_name} must start with '/'")
    if prefix == "/":
        raise RuntimeError(f"{env_name} must not be the root path")
    if any(character.isspace() for character in prefix):
        raise RuntimeError(f"{env_name} must not contain whitespace")
    if "//" in prefix:
        raise RuntimeError(f"{env_name} must not contain empty path segments")
    return prefix


def validate_hosted_store_path(
    path_value: str | Path,
    *,
    env_name: str,
    kind: Literal["file", "directory"] = "file",
    required_suffix: str | None = None,
) -> Path:
    """Validate a hosted-store path with the shared precondition contract.

    ``kind="file"`` rejects directory targets and (when ``required_suffix`` is
    set) suffix mismatches. ``kind="directory"`` rejects regular-file targets
    and ignores ``required_suffix``. In both shapes the parent directory must
    already exist and the writable target (path if existing, otherwise the
    parent) must be writable by the process.
    """

    if required_suffix is not None and not required_suffix.startswith("."):
        raise ValueError("required_suffix must start with '.' (e.g. '.json')")

    path = Path(path_value).expanduser()
    descriptor = "file path" if kind == "file" else "directory path"
    if not path.is_absolute():
        raise RuntimeError(f"{env_name} must be an absolute {descriptor}")

    if kind == "file":
        if path.exists() and path.is_dir():
            target_label = (
                f"{required_suffix.upper().lstrip('.')} file"
                if required_suffix
                else "regular file"
            )
            raise RuntimeError(
                f"{env_name} must point to a {target_label}, not a directory"
            )
        if required_suffix is not None and path.suffix.lower() != required_suffix.lower():
            raise RuntimeError(
                f"{env_name} must use a {required_suffix} file extension"
            )
    else:
        if path.exists() and path.is_file():
            raise RuntimeError(
                f"{env_name} must point to a directory, not a regular file"
            )

    parent = path.parent
    if not parent.exists():
        raise RuntimeError(f"{env_name} parent directory must already exist")
    if not parent.is_dir():
        raise RuntimeError(f"{env_name} parent must be a directory")

    if kind == "file" and path.exists() and not path.is_file():
        raise RuntimeError(f"{env_name} must point to a regular file")
    if kind == "directory" and path.exists() and not path.is_dir():
        raise RuntimeError(f"{env_name} must point to a directory")

    writable_target = path if path.exists() else parent
    if not os.access(writable_target, os.W_OK):
        raise RuntimeError(
            f"{env_name} must be writable by the control-plane process"
        )
    return path
