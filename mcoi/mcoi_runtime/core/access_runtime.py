"""Purpose: compatibility import for the governed access runtime engine.
Governance scope: RBAC access runtime module path stability.
Dependencies: mcoi_runtime.governance.guards.access.
Invariants:
  - The access runtime implementation remains single-sourced in the governance guard.
  - Legacy core imports resolve without duplicating authorization logic.
  - No policy state is mutated at import time.
"""

from __future__ import annotations

from mcoi_runtime.governance.guards.access import AccessRuntimeEngine

__all__ = ("AccessRuntimeEngine",)
