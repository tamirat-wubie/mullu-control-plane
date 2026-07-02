<!--
Purpose: Versioned witness for quiet GitHub repository metadata.
Governance scope: repository description, topics, latest release, and required
  repository-status documents.
Dependencies: STATUS.md, DEPLOYMENT_STATUS.md, docs/52_mullu_governance_protocol.md,
  scripts/validate_public_repository_surface.py.
Invariants: Metadata claims are explicit, machine-checkable, and bounded to the
  tamirat-wubie/mullu-control-plane repository.
-->

# GitHub Surface Witness

**Repository:** `tamirat-wubie/mullu-control-plane`
**Public surface mode:** `quiet`
**Expected description:** `(none)`
**Expected latest release:** `v3.13.3`

## Required Topics

No repository topics are required while quiet mode is active.

## Required Proprietary Documents

| Document | Purpose |
|---|---|
| `STATUS.md` | Branch, release, CI, governance, and known reflection gaps |
| `DEPLOYMENT_STATUS.md` | Deployment-health witness state and closure path |
| `docs/00_platform_overview.md` | Product/repository/company topology, current single-repository posture, and future split triggers |
| `docs/PRODUCT_BOUNDARY.md` | Product naming, company boundary, control-plane identity, launch constraint, and rename-not-split-trigger rule |
| `docs/52_mullu_governance_protocol.md` | Public protocol schema index and closed runtime boundary |
| `docs/CURRENT_READINESS_SNAPSHOT.md` | Compact public claim boundary for repository, release, deployment, pilot, and launch posture |
| `docs/EVIDENCE_CLASSIFICATION.md` | Evidence-class rules that prevent fixtures and examples from supporting production claims |
| `docs/PILOT_PRODUCT_PACKET.md` | Private-pilot market packet with allowed claims, blocked claims, demo spine, and acceptance criteria |

## Product Surface Packet

The current product-facing packet is intentionally claim-bounded:

| Artifact | Claim boundary |
|---|---|
| `docs/CURRENT_READINESS_SNAPSHOT.md` | Names current posture without claiming public production health |
| `docs/EVIDENCE_CLASSIFICATION.md` | Distinguishes fixture, local, CI, staging, pilot, production, external, and historical evidence |
| `examples/evidence_classification_manifest.json` | Classifies high-risk public evidence examples as fixtures or bounded witnesses |
| `docs/PILOT_PRODUCT_PACKET.md` | Positions Mullu Govern as private-pilot governed symbolic intelligence execution, not public SaaS |
| `docs/RECEIPT_VIEWER_V1_SPEC.md` | Defines the first buyer/operator proof surface and receipt tiers |
| `docs/CAPABILITY_RUNTIME_GATE_SPEC.md` | Converts capability maturity into a runtime admission policy target |
| `docs/TEMPORAL_SCHEDULER_V2_PLAN.md` | Moves temporal work toward missed-action, evidence-freshness, recurrence, and lease safety |

## Proof Chain

| Check | Command |
|---|---|
| Proprietary repository surface | `python scripts/validate_public_repository_surface.py` |
| Protocol manifest | `python scripts/validate_protocol_manifest.py` |
| Governed runtime promotion | `python scripts/validate_governed_runtime_promotion.py --strict` |
| Release gate anchoring | `python scripts/validate_release_status.py --strict` |
