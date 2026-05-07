"""Mullu governance surface — the audit-grade enforcement and audit layer.

This package is the canonical location for every module that enforces,
audits, or carries policy at request time. After the F7 reorganization
(v4.38 -> v4.39 -> v4.41 -> v4.42) the audit surface lives here and
nowhere else — operators and contributors point at one directory to
find every governance module.

Layout:

    auth/         — JWT/OIDC validation, API-key minting + verification
    guards/       — request-time enforcement: rate limit, budget,
                    tenant gating, RBAC, content safety, guard chain
    audit/        — append-only hash-chain trail, checkpoint anchor,
                    JSONL exporter, decision log
    network/      — outbound network policy: SSRF, webhook delivery
    policy/       — policy engines: enforcement, simulation,
                    versioning, provider-specific, shell, sandbox
    metrics       — governance metrics aggregation (Prometheus)

Five architectural invariants apply across the package. See
``docs/GOVERNANCE_ARCHITECTURE.md`` for the contract:

  1. Atomic SQL doctrine — every persistent write is a single
     atomic UPDATE with WHERE-clause gating; the DB is the source
     of truth, not an in-memory cache.
  2. Identity preservation — symbols imported across the package
     boundary are the same Python objects; ``isinstance`` works.
  3. Fail-closed defaults — every auth-affecting flag defaults to
     the strict posture; opt-out is explicit.
  4. Bounded error messages — request-visible errors don't leak
     user input or backend implementation details.
  5. Connection-pool-safe storage — stores expose optional
     ``try_*`` primitives that the manager dispatches to via MRO
     check; opt-in atomic semantics for pooled deployments.

If you're contributing a new governance module, read
``docs/GOVERNANCE_ARCHITECTURE.md`` first. The package layout is
stable post-F7; reorganizing it requires a published plan with a
deprecation period.
"""
