"""
TenantQuota dataclass — extracted from registry_store.py at v4.14.0+ to
break the registry_store ↔ persistence circular import that the static
import analyzer detects.

Both modules need TenantQuota: registry_store stores it on TenantState,
persistence serializes/deserializes it. Hosting it in a third neutral
module removes the cycle without changing runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TenantQuota:
    """Per-tenant resource limits.

    - ``max_constructs`` (v4.9.0) caps the lifetime construct registry size.
      None means unlimited.
    - ``max_writes_per_window`` (v4.10.0) caps writes within a sliding time
      window. None means unlimited.
    - ``window_seconds`` is the sliding window size for the rate cap.
      Default 3600 (1 hour).

    Both checks are independent; a tenant could be at construct cap but
    still under rate cap (or vice versa), and only the violated check
    triggers 429.
    """

    max_constructs: int | None = None
    max_writes_per_window: int | None = None
    window_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_constructs is not None and self.max_constructs < 0:
            raise ValueError("max_constructs must be non-negative")
        if (
            self.max_writes_per_window is not None
            and self.max_writes_per_window < 0
        ):
            raise ValueError("max_writes_per_window must be non-negative")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
