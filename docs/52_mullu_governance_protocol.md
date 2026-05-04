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
8. Effect assurance records are public contracts when they certify planned, observed, and reconciled reality changes.
9. Deployment witness artifacts are public contracts when they support published gateway health claims.
10. Capability adapter closure plans are public contracts when they translate adapter blockers into operator actions, verification commands, and receipt validators.
11. General-agent promotion closure plans are public contracts when they coordinate operator approval and production-promotion work.
12. General-agent promotion handoff packets are public contracts when they bind runbooks, checklists, closure plans, validation reports, blockers, and terminal proof commands.
13. General-agent promotion environment bindings are public contracts when they define the presence-only inputs required for operator handoff preflight.
14. General-agent promotion environment binding receipts are public contracts when they record presence-only binding evidence without serializing values.
15. Governed runtime promotion validators are public contracts when they provide domain-neutral terminal commands over compatibility-bound promotion evidence.
16. Terminal closure certificates are public contracts when they certify final command disposition.

## Verification

Run:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 32 schemas
```

STATUS:
  Completeness: 100%
  Invariants verified: open schema index, closed runtime boundary, schema urn matching, URI scheme declaration, compatibility rules, deployment handoff receipt contract, deployment witness artifact contract, effect assurance record contract, capability adapter closure plan contract, promotion closure plan contract, promotion environment binding contract, promotion environment binding receipt contract, promotion handoff packet contract, governed runtime promotion validator contract, terminal closure certificate contract
  Open issues: none
  Next action: publish the manifest from `docs.mullusi.com` with versioned release notes
