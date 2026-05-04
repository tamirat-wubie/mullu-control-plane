<!--
Purpose: Versioned witness for GitHub repository metadata.
Governance scope: public repository description, topics, latest release, and
  required public-status documents.
Dependencies: STATUS.md, DEPLOYMENT_STATUS.md, docs/52_mullu_governance_protocol.md,
  scripts/validate_public_repository_surface.py.
Invariants: Metadata claims are explicit, machine-checkable, and bounded to the
  tamirat-wubie/mullu-control-plane repository.
-->

# GitHub Surface Witness

**Repository:** `tamirat-wubie/mullu-control-plane`
**Expected description:** `Governed symbolic intelligence control plane - multi-tenant LLM orchestration with budget enforcement, audit trails, and policy-driven governance`
**Expected latest release:** `v3.13.0`

## Required Topics

| Topic |
|---|
| `audit-trail` |
| `budget-enforcement` |
| `fastapi` |
| `governance` |
| `llm` |
| `multi-tenant` |
| `orchestration` |
| `python` |
| `rust` |
| `symbolic-intelligence` |

## Required Public Documents

| Document | Purpose |
|---|---|
| `STATUS.md` | Branch, release, CI, governance, and known reflection gaps |
| `DEPLOYMENT_STATUS.md` | Deployment-health witness state and closure path |
| `docs/52_mullu_governance_protocol.md` | Public protocol schema index and closed runtime boundary |

## Proof Chain

| Check | Command |
|---|---|
| Public repository surface | `python scripts/validate_public_repository_surface.py` |
| Protocol manifest | `python scripts/validate_protocol_manifest.py` |
| Governed runtime promotion | `python scripts/validate_governed_runtime_promotion.py --strict` |
| Release gate anchoring | `python scripts/validate_release_status.py --strict` |

