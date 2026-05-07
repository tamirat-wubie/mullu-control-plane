"""Request-time enforcement — the governance guard chain.

Modules:
  - ``chain`` — :class:`GovernanceGuardChain` and the standard
    guard factories (api_key, jwt, tenant, rbac, temporal,
    rate_limit, budget, tenant_gating)
  - ``rate_limit`` — token-bucket rate limiter (atomic SQL)
  - ``budget`` — per-tenant cost/call budget (atomic SQL)
  - ``tenant_gating`` — per-tenant active/suspended/disabled
  - ``access`` — RBAC engine (identities, roles, permissions,
    delegations, event spine)
  - ``content_safety`` — prompt injection + output safety
    filters

All persistent writes follow the atomic SQL doctrine
(invariant 1 in the architecture reference).
"""
