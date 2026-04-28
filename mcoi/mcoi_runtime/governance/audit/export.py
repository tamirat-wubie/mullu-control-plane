"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.audit_export`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.audit_export`` path or the new ``governance.audit.export`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.audit_export import (  # noqa: F401
    AuditExportResult,
    AuditExporter,
    ExportMetadata,
)

__all__ = (
    "AuditExportResult",
    "AuditExporter",
    "ExportMetadata",
)
