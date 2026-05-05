# Mullu Governance Protocol

Purpose: define the public Mullu Governance Protocol open schema surface and closed reference runtime boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: `schemas/mullu_governance_protocol.manifest.json`, `scripts/validate_protocol_manifest.py`, shared JSON schemas.
Invariants: schemas and wire contracts are public; runtime implementation remains the Mullusi reference implementation.

## Boundary

| Surface | Status | Rule |
|---|---|---|
| `schemas/*.schema.json` | open | Public wire contracts that other vendors may implement |
| `schemas/mullu_governance_protocol.manifest.json` | open | Canonical MGP schema index and compatibility boundary |
| `lineage://`, `proof://`, `mgp://` | open | Stable URI schemes for lineage, proof, and protocol artifacts |
| `mcoi/mcoi_runtime/core` | closed | Reference runtime internals, not protocol contracts |
| `mcoi/mcoi_runtime/app` | closed | HTTP assembly and deployment runtime, not protocol contracts |
| `gateway` | closed | Mullusi reference gateway implementation |
| `scripts` | closed | Operator tooling and validation implementation |

## Protocol Rules

### Governed Runtime Promotion

1. Public contracts live in `schemas/`.
2. Runtime-local Python, FastAPI, gateway, and script modules are not protocol contracts.
3. Every public schema must use JSON Schema draft 2020-12 and a `urn:mullusi:schema:*` id.
4. Additive changes must use existing compatibility hatches such as `metadata` or `extensions` where available.
5. Breaking field meaning changes require a coordinated major protocol version.
6. External implementations may implement the schema and URI surface, but Mullusi remains the reference runtime.
7. Deployment handoff receipts are public contracts when they cross operator, CI, or release-promotion boundaries.
8. Deployment orchestration receipt validation reports are public contracts when they certify orchestration handoff evidence for CI and operator promotion.
9. Gateway publication readiness reports are public contracts when they gate deployment publication from repository variables, secret names, workflow state, DNS, and the next operator command.
10. Gateway publication receipt validation reports are public contracts when they certify ready-only, blocked, dispatched, and success-gated publication outcomes.
11. Deployment publication closure validation reports are public contracts when they certify deployment status and witness alignment before publication claims.
12. Capability candidate packages are public contracts when they bind generated capability proposals to schemas, adapters, policy rules, evals, mock providers, sandbox tests, receipts, rollback paths, and promotion blocks.
13. Capability maturity assessments are public contracts when they derive C0-C7 readiness from evidence and block production or autonomy overclaims.
14. World-state projections are public contracts when they expose sourced operational reality for planning and execution gates.
15. Goal compilation reports are public contracts when they bind objectives to plan DAGs, evidence obligations, rollback obligations, approvals, and certificates.
16. Simulation receipts are public contracts when they certify dry-run controls, failure modes, and compensation paths before risky execution.
17. Policy proof reports are public contracts when they certify bounded invariant checks and counterexamples without weakening policy.
18. Effect assurance records are public contracts when they certify planned, observed, and reconciled reality changes.
19. Deployment witness artifacts are public contracts when they support published gateway health claims.
20. Capability adapter closure plans are public contracts when they translate adapter blockers into operator actions, verification commands, and receipt validators.
21. General-agent promotion closure plans are public contracts when they coordinate operator approval and production-promotion work.
22. General-agent promotion handoff packets are public contracts when they bind runbooks, checklists, closure plans, validation reports, blockers, and terminal proof commands.
23. General-agent promotion environment bindings are public contracts when they define the presence-only inputs required for operator handoff preflight.
24. General-agent promotion environment binding receipts are public contracts when they record presence-only binding evidence without serializing values.
25. Governed runtime promotion validators are public contracts when they provide domain-neutral terminal commands over compatibility-bound promotion evidence.
26. Terminal closure certificates are public contracts when they certify final command disposition.
27. Reflex deployment witness envelopes are public contracts when they export replayable promotion evidence for offline validation.
28. Reflex deployment witness validator receipts are public contracts when they certify CI replay evidence without exposing raw JUnit paths.

## Verification

Run:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 45 schemas
```

STATUS:
  Completeness: 100%
  Invariants verified: open schema index, closed runtime boundary, schema urn matching, URI scheme declaration, compatibility rules, deployment handoff receipt contract, deployment orchestration validation contract, gateway publication readiness contract, gateway publication receipt validation contract, deployment publication closure validation contract, capability candidate contract, capability maturity assessment contract, world-state contract, goal compilation contract, simulation receipt contract, policy proof report contract, deployment witness artifact contract, effect assurance record contract, capability adapter closure plan contract, promotion closure plan contract, promotion environment binding contract, promotion environment binding receipt contract, promotion handoff packet contract, governed runtime promotion validator contract, terminal closure certificate contract, reflex deployment witness envelope contract, reflex validator receipt contract
  Open issues: none
  Next action: publish the manifest from `docs.mullusi.com` with versioned release notes
