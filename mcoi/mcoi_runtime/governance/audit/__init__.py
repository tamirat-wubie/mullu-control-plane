"""Audit logging surface — append-only hash chain + verifiers.

Modules:
  - ``trail`` — :class:`AuditTrail`, :class:`AuditEntry`,
    :class:`AuditStore`, hash-chain verification
  - ``anchor`` — checkpoint anchor for prune-resilient
    chain verification (audit F3, v4.28)
  - ``export`` — JSONL exporter; preserves chain integrity
    across export boundaries
  - ``decision_log`` — per-request governance decision log
    (which guards passed/failed, blocking guard, reason)

Append + verify are byte-deterministic; the same chain on
two replicas verifies identically. Atomic append is a
first-class store primitive (audit F4, v4.31).
"""
