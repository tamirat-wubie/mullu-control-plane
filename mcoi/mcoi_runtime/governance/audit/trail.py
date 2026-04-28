"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.audit_trail`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.audit_trail`` path or the new ``governance.audit.trail`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.audit_trail import (  # noqa: F401
    AuditCheckpoint,
    AuditEntry,
    AuditStore,
    AuditTrail,
    ExternalVerifyResult,
    GENESIS_HASH,
    LEDGER_SCHEMA_VERSION_MAX,
    LEDGER_V1_CONTENT_FIELDS,
    verify_chain_from_entries,
)

__all__ = (
    "AuditCheckpoint",
    "AuditEntry",
    "AuditStore",
    "AuditTrail",
    "ExternalVerifyResult",
    "GENESIS_HASH",
    "LEDGER_SCHEMA_VERSION_MAX",
    "LEDGER_V1_CONTENT_FIELDS",
    "verify_chain_from_entries",
)
