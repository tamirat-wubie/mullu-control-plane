"""Purpose: canonical environment fingerprint contract mapping.
Governance scope: shared environment surface adoption.
Dependencies: environment fingerprint schema and observer boundary docs.
Invariants: environment capture remains explicit and deterministic in shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


@dataclass(frozen=True, slots=True)
class PlatformDescriptor(ContractRecord):
    os: str | None = None
    architecture: str | None = None
    distribution: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("os", "architecture", "distribution"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor(ContractRecord):
    name: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("name", "version"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))


@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint(ContractRecord):
    fingerprint_id: str
    captured_at: str
    digest: str
    platform: PlatformDescriptor | None = None
    runtime: RuntimeDescriptor | None = None
    tooling: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint_id", require_non_empty_text(self.fingerprint_id, "fingerprint_id"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        object.__setattr__(self, "digest", require_non_empty_text(self.digest, "digest"))
        object.__setattr__(self, "tooling", freeze_value(self.tooling))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
