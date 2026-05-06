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
13. Capability maturity assessments are public contracts when they derive C0-C7 production and autonomy readiness from explicit evidence and block overclaims.
14. Policy proof reports are public contracts when they certify bounded invariant checks, proved properties, and counterexample paths without weakening policy.
15. Memory lattice admission claims are public contracts when they distinguish working, episodic, semantic, and procedural memory admission.
16. Trust ledger bundles are public contracts when they bind terminal closure, deployment, commit, audit root, evidence refs, and signatures.
17. Trust ledger anchor receipts are public contracts when they bind signed bundles to external anchor targets without replacing terminal closure.
18. Agent identities are public contracts when they bind owner, tenant, role, allowed and forbidden capabilities, budget, memory scope, approval scope, delegation scope, evidence history, and reputation.
19. Claim verification reports are public contracts when they bind claim type, source evidence, support edges, contradiction edges, freshness windows, domain risk, and planning/execution admission.
20. Collaboration cases are public contracts when they bind requester separation, approval controls, decider authority, evidence hashing, and non-terminal case closure.
21. Connector self-healing receipts are public contracts when they classify provider failures, bound recovery actions, preserve failure receipts, and require verification before renewed connector use.
22. Domain operating packs are public contracts when they package governed schemas, policies, workflows, connectors, evals, risk rules, evidence exports, and dashboard views behind activation-blocked certification.
23. Multimodal operation receipts are public contracts when they gate modality-bound worker dispatch with source-preserving evidence.
24. Temporal operation receipts are public contracts when they certify runtime-owned time checks for schedules, expiry, approval validity, evidence freshness, budget windows, causal prerequisites, and monotonic duration witnesses.
25. Temporal memory receipts are public contracts when they certify memory age, evidence freshness, validity windows, confidence decay, tenant-owner scope, allowed use, and supersession before memory can guide action.
26. Temporal evidence freshness receipts are public contracts when they certify evidence age, freshness, source kind, max-age policy, tenant scope, allowed use, and non-terminal freshness checks before evidence can support action.
27. Temporal reapproval receipts are public contracts when they re-check high-risk or critical approval validity, approver role coverage, scope, revocation, expiry, approval age, and source schedule binding at execution time before dispatch.
28. Temporal dispatch window receipts are public contracts when they certify tenant timezone, allowed dispatch windows, blackout windows, holidays, source schedule and reapproval binding, evidence refs, and non-terminal dispatch admission before worker execution.
29. Temporal memory refresh receipts are public contracts when they certify memory refresh status, refreshed-at time, source evidence refs, tenant scope, allowed use, and non-terminal refresh checks before refreshed memory can guide action.
30. Temporal scheduler receipts are public contracts when they certify lease acquisition, retry windows, missed-run handling, idempotency, recurrence declarations, and high-risk temporal rechecks before scheduled dispatch.
31. Temporal SLA receipts are public contracts when they certify business calendars, business-time response and resolution deadlines, warning escalation, breach detection, tenant scope, evidence refs, and dispatch windows before escalation or action.
32. Capability upgrade plans are public contracts when they turn health signals into activation-blocked upgrade proposals with eval, sandbox, ChangeCommand, ChangeCertificate, canary, terminal-closure, and learning-admission gates.
33. Autonomous test-generation plans are public contracts when they convert certified failure traces into activation-blocked replay, policy, tenant, approval, budget, and sandbox test proposals.
34. World-state projections are public contracts when they expose sourced operational reality for planning and execution gates.
35. Goal compilation reports are public contracts when they bind objectives to plan DAGs, evidence obligations, rollback obligations, approvals, and certificates.
36. Workflow mining reports are public contracts when they convert repeated human traces into blocked, review-required workflow drafts.
37. Simulation receipts are public contracts when they certify dry-run controls, failure modes, and compensation paths before risky execution.
38. Effect assurance records are public contracts when they certify planned, observed, and reconciled reality changes.
39. Deployment witness artifacts are public contracts when they support published gateway health claims.
40. Capability adapter closure plans are public contracts when they translate adapter blockers into operator actions, verification commands, and receipt validators.
41. General-agent promotion closure plans are public contracts when they coordinate operator approval and production-promotion work.
42. General-agent promotion handoff packets are public contracts when they bind runbooks, checklists, closure plans, validation reports, blockers, and terminal proof commands.
43. General-agent promotion environment bindings are public contracts when they define the presence-only inputs required for operator handoff preflight.
44. General-agent promotion environment binding receipts are public contracts when they record presence-only binding evidence without serializing values.
45. Governed runtime promotion validators are public contracts when they provide domain-neutral terminal commands over compatibility-bound promotion evidence.
46. Terminal closure certificates are public contracts when they certify final command disposition.
47. Reflex deployment witness envelopes are public contracts when they export replayable promotion evidence for offline validation.
48. Reflex deployment witness validator receipts are public contracts when they certify CI replay evidence without exposing raw JUnit paths.
49. Finance approval packet proofs are public contracts when they bind packet state, policy decisions, evidence references, approval/effect references, closure certificates, and audit roots for finance review or closure.
50. Finance approval live handoff artifacts are public contracts when they bind connector evidence, readiness gates, promotion boundaries, chain validation, and redacted operator summaries before live finance claims.
51. Production evidence witnesses are public contracts when they bind deployed version, commit, environment, live/sandbox capability evidence, conformance, audit, proof-store checks, and HMAC signature into one runtime claim.
52. Capability evidence endpoint responses are public contracts when they expose live, pilot, sandbox, tested, and described-only capability maturity without promotion overclaim.
53. Audit verification endpoint responses are public contracts when they expose latest anchor verification state, checked entries, and unanchored event counts.
54. Proof verification endpoint responses are public contracts when they bind conformance signature, production evidence signature, and audit-anchor verification into one closure projection.
55. Gateway observability snapshots are public contracts when they expose bounded run metrics, cost projections, latency, escalation, denial, receipt, and missing-signal state.
56. Operator control tower snapshots are public contracts when they aggregate governed read models into read-only operator panels without exposing raw tool surfaces or mutable execution handles.
57. Low-code builder catalogs are public contracts when they expose declarative-only app compilations, canonical artifacts, activation blocks, certification evidence, and no-effect builder status.

## Verification

Run:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 93 schemas
```

STATUS:
  Completeness: 100%
  Invariants verified: open schema index, closed runtime boundary, schema urn matching, URI scheme declaration, compatibility rules, deployment handoff receipt contract, deployment orchestration validation contract, gateway publication readiness contract, gateway publication receipt validation contract, deployment publication closure validation contract, capability candidate contract, capability maturity contract, policy proof report contract, memory lattice contract, trust ledger bundle contract, trust ledger anchor receipt contract, agent identity contract, claim verification report contract, collaboration case contract, connector self-healing receipt contract, domain operating pack contract, multimodal operation receipt contract, temporal operation receipt contract, temporal memory receipt contract, temporal evidence freshness receipt contract, temporal reapproval receipt contract, temporal dispatch window receipt contract, temporal memory refresh receipt contract, temporal scheduler receipt contract, temporal SLA receipt contract, capability upgrade plan contract, autonomous test-generation plan contract, world-state contract, goal compilation contract, workflow mining report contract, simulation receipt contract, deployment witness artifact contract, finance approval live handoff artifact contract, production evidence witness contract, capability evidence endpoint contract, audit verification endpoint contract, proof verification endpoint contract, gateway observability snapshot contract, operator control tower snapshot contract, low-code builder catalog contract, effect assurance record contract, capability adapter closure plan contract, promotion closure plan contract, promotion environment binding contract, promotion environment binding receipt contract, promotion handoff packet contract, governed runtime promotion validator contract, terminal closure certificate contract, reflex deployment witness envelope contract, reflex validator receipt contract
  Open issues: none
  Next action: publish the manifest from `docs.mullusi.com` with versioned release notes
