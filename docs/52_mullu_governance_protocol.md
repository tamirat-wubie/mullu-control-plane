# Mullu Governance Protocol

> **In one box:** The public, open *rules schema* anyone can read and validate
> against, plus where the closed reference runtime boundary sits — "here is our
> governance contract, in the open." New here? →
> [Plain-English Overview](explain/PLAIN_ENGLISH.md); unknown word? →
> [Glossary](GLOSSARY.md). *(Doc type: Reference.)*

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
12. Deployment publication closure plans are public contracts when they translate live deployment witness blockers into approval-bound operator actions without mutating public status.
13. Deployment publication evidence packets are public contracts when they bind readiness receipts, blocker receipts, DNS receipts, closure plans, schema validation, and dry-run dispatch plans without mutating DNS, workflows, ingress, secrets, or deployment status.
14. Deployment publication operator input requests are public contracts when they translate blocked evidence packets into public-safe missing input names, upstream evidence names, blocked actions, and next actions without serializing secret values, DNS target values, provider account details, IP addresses, or private host details.
15. Finance email/calendar operator input requests are public contracts when they translate blocked redacted binding receipts into public-safe worker, token, and scope witness input names without serializing worker URLs, signing secrets, connector tokens, scope values, provider account details, or mailbox contents.
16. Capability candidate packages are public contracts when they bind generated capability proposals to schemas, adapters, policy rules, evals, mock providers, sandbox tests, receipts, rollback paths, and promotion blocks.
17. Capability maturity assessments are public contracts when they derive C0-C7 production and autonomy readiness from explicit evidence and block overclaims.
18. Policy proof reports are public contracts when they certify bounded invariant checks, proved properties, and counterexample paths without weakening policy.
19. Memory lattice admission claims are public contracts when they distinguish working, episodic, semantic, and procedural memory admission.
20. Trust ledger bundles are public contracts when they bind terminal closure, deployment, commit, audit root, evidence refs, and signatures.
21. Trust ledger anchor receipts are public contracts when they bind signed bundles to external anchor targets without replacing terminal closure.
22. Agent identities are public contracts when they bind owner, tenant, role, allowed and forbidden capabilities, budget, memory scope, approval scope, delegation scope, evidence history, and reputation.
23. Claim verification reports are public contracts when they bind claim type, source evidence, support edges, contradiction edges, freshness windows, domain risk, and planning/execution admission.
24. Collaboration cases are public contracts when they bind requester separation, approval controls, decider authority, evidence hashing, and non-terminal case closure.
25. Connector self-healing receipts are public contracts when they classify provider failures, bound recovery actions, preserve failure receipts, and require verification before renewed connector use.
26. Interpreted requests are public contracts when they bind tenant, actor, channel, raw-message hash, intent class, slots, risk precheck, confidence, and governance constraints before planning, search, approval, or execution.
27. Interpretation receipts are public contracts when they record what the gateway believed the user requested without storing raw message text or raw parameter values.
28. Clarification requests are public contracts when they block missing-slot interpretation from planning or execution and carry one safe user question with default `no_execution`.
29. Capability plan previews are public contracts when they expose read-only plan topology, risk, approval, and evidence obligations before execution without storing raw goal text or raw step params.
30. Domain operating packs are public contracts when they package governed schemas, policies, workflows, connectors, evals, risk rules, evidence exports, and dashboard views behind activation-blocked certification.
31. Multimodal operation receipts are public contracts when they gate modality-bound worker dispatch with source-preserving evidence.
32. Temporal operation receipts are public contracts when they certify runtime-owned time checks for schedules, expiry, approval validity, evidence freshness, budget windows, causal prerequisites, and monotonic duration witnesses.
33. Temporal resolution receipts are public contracts when they certify original temporal text, runtime-owned current time, tenant timezone, bounded phrase parsing, ambiguity handling, business-calendar resolution, and high-risk clarification before scheduling or dispatch.
34. Temporal memory receipts are public contracts when they certify memory age, evidence freshness, validity windows, confidence decay, tenant-owner scope, allowed use, and supersession before memory can guide action.
35. Temporal evidence freshness receipts are public contracts when they certify evidence age, freshness, source kind, max-age policy, tenant scope, allowed use, and non-terminal freshness checks before evidence can support action.
36. Temporal reapproval receipts are public contracts when they re-check high-risk or critical approval validity, approver role coverage, scope, revocation, expiry, approval age, and source schedule binding at execution time before dispatch.
37. Temporal dispatch window receipts are public contracts when they certify tenant timezone, allowed dispatch windows, blackout windows, holidays, source schedule and reapproval binding, evidence refs, and non-terminal dispatch admission before worker execution.
38. Temporal budget window receipts are public contracts when they certify tenant-local budget reset periods, active spend snapshots, projected spend, remaining budget, source temporal and reapproval binding, evidence refs, and non-terminal budget admission before worker execution.
39. Temporal causal order receipts are public contracts when they certify required timestamped events, tenant and command scope, predecessor edges, source receipt binding, missing events, out-of-order events, and non-terminal causal admission before worker execution.
40. Temporal monotonic duration receipts are public contracts when they certify elapsed latency, timeout, cooldown, retry-delay, and watchdog measurements from monotonic clock readings rather than wall-clock time before dispatch.
41. Temporal accepted-risk expiry receipts are public contracts when they certify accepted-risk lifecycle state, expiry, tenant and command scope, owner, approver, case, review obligation, evidence refs, and non-terminal reuse admission before dispatch.
42. Temporal credential expiry receipts are public contracts when they certify connector credential lifecycle state, expiry, provider and credential scope, rotation windows, owner, evidence refs, source binding receipts, and no-secret serialization before dispatch.
43. Temporal retention window receipts are public contracts when they certify retention_until, delete_after, legal hold, tenant scope, retention policy, owner, evidence refs, source data decision binding, and non-terminal lifecycle-action admission before deletion, archive, anonymization, or retention review.
44. Temporal rate-limit window receipts are public contracts when they certify tenant, endpoint, and identity scope, active token windows, projected token consumption, burst limits, retry-after timing, evidence refs, and non-terminal rate-limit admission before dispatch.
45. Temporal retry window receipts are public contracts when they certify retry-after timing, cooldown windows, max attempts, retry expiry, tenant and command scope, evidence refs, source temporal receipts, and non-terminal retry admission before repeated dispatch.
46. Temporal lease window receipts are public contracts when they certify lease ownership, tenant and command scope, resource scope, worker scope, fencing tokens, lease expiry, renewal warnings, evidence refs, source temporal receipts, and non-terminal lease admission before worker dispatch.
47. Temporal idempotency window receipts are public contracts when they certify idempotency keys, request fingerprints, replay windows, committed effects, terminal receipt binding, tenant and command scope, evidence refs, source temporal receipts, and non-terminal duplicate-dispatch admission before worker execution.
48. Temporal missed-run receipts are public contracts when they certify late, expired, duplicate-dispatched, and recovery-due scheduled commands with runtime-owned time truth, scheduler source receipts, evidence refs, high-risk reapproval binding, and non-terminal skip or recovery admission before retry or closure.
49. Temporal recurrence window receipts are public contracts when they certify next recurring occurrences with runtime-owned time truth, tenant timezone preservation, recurrence rule parsing, DST-sensitive next-occurrence checks, series completion, duplicate-run prevention, scheduler source receipts, evidence refs, and high-risk due-candidate reapproval binding before recurring dispatch.
50. Temporal memory refresh receipts are public contracts when they certify memory refresh status, refreshed-at time, source evidence refs, tenant scope, allowed use, and non-terminal refresh checks before refreshed memory can guide action.
51. Temporal scheduler receipts are public contracts when they certify lease acquisition, retry windows, missed-run handling, idempotency, recurrence declarations, and high-risk temporal rechecks before scheduled dispatch.
52. Temporal SLA receipts are public contracts when they certify business calendars, business-time response and resolution deadlines, warning escalation, breach detection, tenant scope, evidence refs, and dispatch windows before escalation or action.
53. Capability upgrade plans are public contracts when they turn health signals into activation-blocked upgrade proposals with eval, sandbox, ChangeCommand, ChangeCertificate, canary, terminal-closure, and learning-admission gates.
54. Autonomous test-generation plans are public contracts when they convert certified failure traces into activation-blocked replay, policy, tenant, approval, budget, and sandbox test proposals.
55. World-state projections are public contracts when they expose sourced operational reality for planning and execution gates.
56. Goal compilation reports are public contracts when they bind objectives to plan DAGs, evidence obligations, rollback obligations, approvals, and certificates.
57. Workflow mining reports are public contracts when they convert repeated human traces into blocked, review-required workflow drafts.
58. Simulation receipts are public contracts when they certify dry-run controls, failure modes, and compensation paths before risky execution.
59. Effect assurance records are public contracts when they certify planned, observed, and reconciled reality changes.
60. Deployment witness artifacts are public contracts when they support published gateway health claims.
61. Capability adapter closure plans are public contracts when they translate adapter blockers into operator actions, verification commands, and receipt validators.
62. General-agent promotion closure plans are public contracts when they coordinate operator approval and production-promotion work.
63. General-agent promotion handoff packets are public contracts when they bind runbooks, checklists, closure plans, validation reports, blockers, and terminal proof commands.
64. General-agent promotion environment bindings are public contracts when they define the presence-only inputs required for operator handoff preflight.
65. General-agent promotion environment binding receipts are public contracts when they record presence-only binding evidence without serializing values.
66. Governed runtime promotion validators are public contracts when they provide domain-neutral terminal commands over compatibility-bound promotion evidence.
67. Terminal closure certificates are public contracts when they certify final command disposition.
68. Reflex deployment witness envelopes are public contracts when they export replayable promotion evidence for offline validation.
69. Reflex deployment witness validator receipts are public contracts when they certify CI replay evidence without exposing raw JUnit paths.
70. Finance approval packet proofs are public contracts when they bind packet state, policy decisions, evidence references, approval/effect references, closure certificates, and audit roots for finance review or closure.
71. Finance approval live handoff artifacts are public contracts when they bind connector evidence, readiness gates, promotion boundaries, chain validation, and redacted operator summaries before live finance claims.
72. Finance payment provider binding receipts are public contracts when they record presence-only payment credential evidence, provider scope, provider-binding refs, and no-secret serialization before non-sandbox payment closure.
73. Production evidence witnesses are public contracts when they bind deployed version, commit, environment, live/sandbox capability evidence, conformance, audit, proof-store checks, and HMAC signature into one runtime claim.
74. Capability evidence endpoint responses are public contracts when they expose live, pilot, sandbox, tested, and described-only capability maturity without promotion overclaim.
75. Audit verification endpoint responses are public contracts when they expose latest anchor verification state, checked entries, and unanchored event counts.
76. Proof verification endpoint responses are public contracts when they bind conformance signature, production evidence signature, and audit-anchor verification into one closure projection.
77. Gateway observability snapshots are public contracts when they expose bounded run metrics, cost projections, latency, escalation, denial, receipt, and missing-signal state.
78. Operator control tower snapshots are public contracts when they aggregate governed read models into read-only operator panels without exposing raw tool surfaces or mutable execution handles.
79. Low-code builder catalogs are public contracts when they expose declarative-only app compilations, canonical artifacts, activation blocks, certification evidence, and no-effect builder status.
80. Marketplace SDK catalogs are public contracts when they expose certified offerings, publication decisions, SDK contracts, channel eligibility, and raw-execution-surface denial.
81. Public production health declaration receipts are public contracts when they bind a published deployment witness, matching HTTPS health endpoint, status mutation, and operator approval reference.
82. Runtime conformance collection envelopes are public contracts when they preserve live `/runtime/conformance` probe status, signature verification, authority read-model checks, and bounded collection errors.
83. Mullu clearance capture requirements are public contracts when they preserve remaining naming-clearance evidence intake, reviewer authority, and paid-launch blockers in machine-readable form.
84. Public naming decision witnesses are public contracts when they preserve product name authority, private-beta allowance, paid-launch blockers, open gates, and blocked public names in machine-readable form.
85. Mullu clearance capture readiness reports are public contracts when they derive required-file presence, missing evidence, gate status, and paid-launch blockers from the clearance capture requirements.
86. GCI capability contracts are public contracts when they bind capability identity, governance tier, T/E/C/R/V axes, effect class, source trust, preconditions, failure modes, and reversibility before execution admission.
87. GCI rejected-path receipts are public contracts when they record `Phi_gov` capability blocks, source-trust failures, missing axes, governance-depth failures, and causal ledger bindings without executing the target action.
88. Governed swarm staging activation witnesses are public contracts when they bind feature flags, runtime release pins, route probes, audit-store closure, rollback preservation, and terminal activation evidence.
89. Governed swarm staging runner preflight receipts are public contracts when they prove the selected runner can see the staging URL input, deployed control-plane commit, runtime bridge, and audit JSONL before witness collection.
90. Governed swarm staging evidence bundles are public contracts when they bind runner preflight receipts and activation witnesses into one cross-checked staging activation claim.
91. Governed swarm promotion readiness reports are public contracts when they convert staging evidence bundles into pilot-ready or production-blocked promotion decisions.
92. Gateway DNS resolution receipts are public contracts when they bind a concrete gateway host, UTC check time, resolved address set, bounded resolver error state, and next action before deployment publication.
93. Gateway DNS target binding receipts are public contracts when they bind the intended gateway host, URL, environment, DNS record type, origin target, authoritative provider, readiness state, and next action before DNS publication.
94. Evidence classification manifests are public contracts when they classify fixture, local, CI, staging, pilot, production, external, and historical evidence before public readiness or production claims.
95. P3 memory topology read models are public contracts when they expose read-only nested-mind topology projections without raw topology metadata, raw memory metadata, live write authority, or execution authority.
96. Workspace governance preflight receipts are public contracts when they bind canonical repository-local validation command names, command tails, observed return codes, closed field surfaces, terminal-closure flags, and status derivation into replayable governance evidence.
97. Workspace governance inventory reports are public contracts when they bind repository-local governance artifact names, paths, purposes, sizes, missing-artifact counts, issue counts, and non-terminal closure flags into replayable governance evidence.
98. Workspace governance integrity reports are public contracts when they bind repository-local governance artifact names, paths, purposes, sizes, SHA-256 digests, missing-artifact counts, issue counts, and non-terminal closure flags into replayable governance evidence.
99. Workspace governance witnesses are public contracts when they bind repository-local governance artifact inventory, artifact count, block conditions, release status, governance scope, and self-validation artifacts into preflight-admissible evidence.
100. TeamOps shared inbox operator handoff packets are public contracts when they bind assistant profile authority, shared inbox witness refs, owner queue evidence, approval policy, idempotency policy, Gmail OAuth scope, blocked live-probe conditions, and no-send/no-secret-serialization flags before TeamOps connector promotion.

## Verification

Run:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 201 schemas
```

STATUS:
  Completeness: 100%
  Invariants verified: open schema index, closed runtime boundary, schema urn matching, URI scheme declaration, compatibility rules, deployment handoff receipt contract, deployment orchestration validation contract, gateway publication readiness contract, gateway DNS resolution receipt contract, gateway DNS target binding receipt contract, deployment upstream blocker receipt contract, gateway publication receipt validation contract, deployment publication closure validation contract, deployment publication closure plan contract, deployment publication evidence packet contract, finance approval email/calendar operator input request contract, public production health declaration contract, runtime conformance collection contract, capability candidate contract, capability maturity contract, GCI capability contract, GCI rejected-path receipt contract, governed swarm staging evidence bundle contract, governed swarm promotion readiness contract, policy proof report contract, memory lattice contract, trust ledger bundle contract, trust ledger anchor receipt contract, trust ledger anchor submission receipt contract, trust ledger remote submission preflight contract, agent identity contract, claim verification report contract, collaboration case contract, connector self-healing receipt contract, interpreted request contract, interpretation receipt contract, clarification request contract, domain operating pack contract, multimodal operation receipt contract, temporal operation receipt contract, temporal resolution receipt contract, temporal memory receipt contract, temporal evidence freshness receipt contract, temporal reapproval receipt contract, temporal dispatch window receipt contract, temporal budget window receipt contract, temporal causal order receipt contract, temporal monotonic duration receipt contract, temporal accepted-risk expiry receipt contract, temporal credential expiry receipt contract, temporal retention window receipt contract, temporal rate-limit window receipt contract, temporal retry window receipt contract, temporal lease window receipt contract, temporal idempotency window receipt contract, temporal missed-run receipt contract, temporal recurrence window receipt contract, temporal memory refresh receipt contract, temporal scheduler receipt contract, temporal SLA receipt contract, capability upgrade plan contract, autonomous test-generation plan contract, world-state contract, goal compilation contract, workflow mining report contract, simulation receipt contract, effect assurance record contract, deployment witness artifact contract, finance approval live handoff artifact contract, finance payment provider binding receipt contract, production evidence witness contract, capability evidence endpoint contract, audit verification endpoint contract, proof verification endpoint contract, gateway observability snapshot contract, operator control tower snapshot contract, low-code builder catalog contract, marketplace SDK catalog contract, capability adapter closure plan contract, promotion closure plan contract, promotion environment binding contract, promotion environment binding receipt contract, promotion handoff packet contract, governed runtime promotion validator contract, terminal closure certificate contract, reflex deployment witness envelope contract, reflex validator receipt contract, clearance capture requirements contract, public naming decision contract, clearance capture readiness report contract, evidence classification manifest contract, P3 memory topology read model contract, workspace governance preflight receipt contract, workspace governance inventory report contract, workspace governance integrity report contract, workspace governance witness contract
  Open issues: none
  Next action: publish the manifest from `docs.mullusi.com` with versioned release notes
