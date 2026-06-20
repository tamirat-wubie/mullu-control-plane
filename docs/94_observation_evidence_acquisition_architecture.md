<!--
Purpose: define the platform-wide observation and evidence acquisition architecture that turns world reads into governed planning input.
Governance scope: OCE field completeness, RAG source-to-evidence relationships, CDCV observation causality, CQTE freshness and trust gates, UWMA receipt anchoring, SRCA bounded sensing, and PRS verification closure.
Dependencies: docs/00_platform_overview.md, docs/06_capability_planes.md, docs/10_external_integration_plane.md, docs/16_world_state_plane.md, docs/21_workflow_runtime.md, docs/22_goal_reasoning.md, docs/74_truth_kernel_plane.md, docs/75_problem_star_compilation_receipt.md, docs/77_search_decision_contract.md, docs/78_search_receipt_contract.md, docs/79_worker_failure_receipt_contract.md, docs/83_connector_action_promotion_gate_contract.md, docs/87_browser_observation_receipt_contract.md, docs/89_trusted_capture_evidence_packet_contract.md, docs/95_repository_observation_evidence_packet_contract.md, scripts/validate_observation_evidence_acquisition_architecture.py, tests/test_validate_observation_evidence_acquisition_architecture.py.
Invariants: observation is not execution; evidence packets are not truth commits; planning cannot consume unobserved or stale evidence for hard constraints; live provider claims remain AwaitingEvidence until a live read witness exists; no raw secret, private payload, or unclassified personal payload is promoted into planning input.
-->

# Observation Evidence Acquisition Architecture

<!-- TYPE: Reference -->
<!-- AUDIENCE: architecture maintainers, planner implementers, adapter implementers, governance reviewers -->

> **In one box:** This page defines how Mullu checks what is actually true
> before it plans or acts. It turns observed facts into reviewable evidence
> packets, then lets planning use only the packets that pass freshness, source,
> privacy, and governance checks.
>
> This is a Foundation Mode architecture contract, not a live-provider readiness
> claim.

---

## Boundary

[Observation Evidence Acquisition Architecture](GLOSSARY.md#observation-evidence-acquisition-architecture)
answers this question:

```text
What evidence is trusted enough to become planning input right now?
```

It owns the path from a read surface to an [evidence packet](GLOSSARY.md#evidence-packet):

```text
ObservationRequest
  -> source authority preflight
  -> read-only sensing
  -> observation normalization
  -> evidence classification
  -> freshness check
  -> contradiction check
  -> EvidencePacket
  -> EvidenceAdmissionDecision
  -> WorldStateProjection
  -> ProblemStar input
```

It does not own:

| Surface | Owner |
| --- | --- |
| Goal decomposition and action planning | Planning Plane and Goal Reasoning |
| Execution admission | Policy, UAO, connector promotion, and worker admission gates |
| External write effects | Execution Plane and connector workers |
| Truth-state mutation | Mullu Truth Kernel and governed commit adapters |
| Long-term learning | Learning Admission and Memory Plane |
| Terminal closure | Verification Plane, receipt ledger, and closure contracts |

Hard boundary:

```text
evidence_packet != truth_commit
evidence_packet != execution_authority
evidence_packet != terminal_closure
```

## Core Loop

The full control loop is:

```text
Observe
  -> Understand
  -> Plan
  -> Admit authority
  -> Execute
  -> Observe result
  -> Verify
  -> Recover or close
  -> Learn
```

Planning is downstream of observation. A plan that lacks current evidence is a
proposal over unknown state, not an executable decision.

## Requirement Boundary

| Field | Value |
| --- | --- |
| `change_id` | `observation-evidence-acquisition-architecture-20260619` |
| `requirement_id` | `REQ-observation-evidence-acquisition-architecture-20260619` |
| `intent` | Add a first-class architecture contract for live observation, evidence packets, admission, world-state projection, and planning input. |
| `owner_or_actor` | Mullu Control Plane architecture maintainers. |
| `target_surfaces` | Docs, planning input contracts, evidence receipts, read-only adapters, world-state projections, recovery records, and benchmark criteria. |
| `scope` | Documentation architecture only in this change. |
| `non_goals` | No live connector call, no credential access, no runtime dispatch, no schema mutation, no file capture beyond this documentation edit, no public readiness claim. |
| `constraints` | Foundation Mode, no silent evidence promotion, no raw secret retention, no hard-constraint planning on stale or unknown evidence, Mfidel atomicity preserved if observed payloads contain fidel symbols. |
| `success_criteria` | The architecture defines inputs, gates, packet fields, state projection, admission outcomes, recovery behavior, and benchmark hooks. |
| `acceptance_tests` | Markdown contract review, platform overview link check, governance preflight receipt. |
| `required_evidence_refs` | This document, platform overview reference, glossary entries, workspace governance preflight receipt. |
| `blocked_unknowns` | Live provider read witnesses, read-only connector authority, provider-specific evidence schemas, and runtime evidence ledger append remain future proof threads. |
| `next_state` | `SolvedVerified` for local read-only repository observation after producer and validators pass; `AwaitingEvidence` for provider and connector observation. |

## Evidence Packet Contract

Every admitted evidence packet must carry:

| Field | Meaning |
| --- | --- |
| `packet_id` | Stable packet identity. |
| `observation_request_id` | The sensing request that caused the packet. |
| `source_kind` | Repo, inbox, calendar, CI, provider, worker, deployment, approval, browser, search, document, or operator-supplied source. |
| `source_ref` | Redacted or hash-bound source reference. |
| `observed_at` | Timestamp assigned by the observation boundary. |
| `fresh_until` | Expiry time or explicit non-expiring reason. |
| `collector_ref` | Adapter, worker, or operator surface that collected the observation. |
| `authority_ref` | Proof that the collector was allowed to read the source. |
| `consent_scope_ref` | Required when the source can include private or people data. |
| `classification_ref` | Public, internal, private, secret-shaped, regulated, or unknown classification. |
| `payload_digest_ref` | Digest reference for raw or structured payload, never raw secret material. |
| `normalized_observation_ref` | Structured observation digest or local receipt ref. |
| `confidence` | Evidence-quality score with bounded meaning, never proof by itself. |
| `contradiction_refs` | Conflicts with previous evidence. |
| `privacy_guards` | Redaction, minimization, and raw-retention decisions. |
| `planning_admission` | `admit`, `defer`, `reject`, or `escalate`. |
| `recovery_actions` | Required next sensing, repair, or escalation steps. |
| `receipt_refs` | Trace, UAO where applicable, LifeMeaningJudgment where applicable, and validator refs. |

Missing required fields fail closed:

```text
missing(source_ref | observed_at | freshness | classification | authority_ref)
  -> planning_admission = reject
```

## Source Classes

| Source class | Example reads | Required guard |
| --- | --- | --- |
| Repository | Git status, diff, tests, file inventory | Local path boundary and no secret printing. |
| CI | Check run status, logs, artifacts | Provider read authority and log redaction. |
| Inbox or calendar | Message state, event state | Connector read scope, consent, minimization, and no send authority. |
| Provider | API status, billing status, deployment status | Credential scope witness and response digest. |
| Worker | Worker output, timeout, failure, partial effect | Worker receipt and replay ref. |
| Deployment | Health, DNS, endpoint, artifact | Deployment witness and public-claim guard. |
| Approval | Human decision, waiver, exception | Approval receipt and expiry. |
| Browser or search | DOM digest, screenshot digest, citation metadata | Observation receipt, capture policy, and raw payload denial. |
| Operator-supplied | Manual status or copied evidence | Lower trust class unless anchored by a receipt. |

Foundation Mode default:

```text
live provider evidence without live read witness -> AwaitingEvidence
operator-supplied preview evidence -> advisory, not live truth
```

## Admission Rules

| Condition | Outcome |
| --- | --- |
| Evidence is current, classified, authority-bound, and contradiction-free | `admit` for the declared planning scope. |
| Evidence is current but advisory or operator-supplied only | `defer` or admit as soft utility only. |
| Evidence is stale, missing authority, secret-shaped, or unclassified | `reject`. |
| Evidence conflicts with hard constraints or live state | `escalate` and create contradiction refs. |
| Evidence requires a connector read that has no live witness | `AwaitingEvidence`. |
| Evidence observes a failed or partial execution | Emit worker failure or recovery receipt before any closure claim. |

Hard-constraint rule:

```text
planning_input.requires_hard_constraint
  and evidence.ProofState in {Unknown, BudgetUnknown}
  -> block planning use and plan sensing
```

Soft-utility rule:

```text
planning_input.requires_soft_ranking
  and evidence.ProofState == Unknown
  -> degrade only if policy permits and the uncertainty is visible
```

## Relationship To The Seven Peer Architectures

| Peer architecture | Observation relationship |
| --- | --- |
| Planning | Supplies current, admitted evidence before decomposition or action selection. |
| Execution Admission | Provides the evidence refs used by UAO, policy, connector promotion, budget, rollback, and approval gates. |
| State / World Model | Projects admitted packets into current and historical state snapshots. |
| Feedback / Recovery | Converts failed, missing, stale, or contradictory observations into recovery actions. |
| Capability Routing | Routes a goal to a domain, source class, read adapter, evidence packet, and admission gate. |
| Memory / Learning | Promotes only verified evidence patterns, never raw unadmitted observations. |
| Evaluation / Benchmark | Measures freshness, contradiction detection, missing-evidence blocking, recovery routing, and closure correctness. |

## Planning Input Gate

Planning may consume evidence only through this gate:

```text
EvidencePacket
  -> EvidenceAdmissionDecision
  -> WorldStateProjection
  -> ProblemStar.evidence
```

Planning must not consume:

1. Raw connector responses without packetization.
2. Operator summaries without source refs.
3. Expired evidence without explicit stale handling.
4. Conflicting evidence without contradiction refs.
5. Secret-shaped payloads.
6. Private payloads without consent, minimization, and classification refs.
7. Evidence that claims live provider state without a live read witness.

## Feedback And Recovery

Observation failures become explicit recovery work:

| Failure | Recovery output |
| --- | --- |
| Connector read failed | ObservationGap plus connector recovery action. |
| Credential stale | Credential freshness blocker and operator handoff. |
| Evidence missing | Sensing plan before planning or admission. |
| Provider result mismatched | ContradictionRecord and verification escalation. |
| Worker timeout | WorkerFailureReceipt and replay or lease investigation. |
| CI failed | CI failure triage and changed-surface evidence. |
| Closure drift | Re-observation and closure invalidation check. |

No observation failure may silently become a planning assumption.

## Benchmark Hooks

Observation quality is benchmarked by:

| Metric | Question |
| --- | --- |
| `freshness_pass_rate` | Did the packet prove it is current enough for the planning scope? |
| `source_binding_rate` | Did every claim point to a source or receipt? |
| `contradiction_detection_rate` | Did conflicting evidence produce contradiction refs? |
| `missing_evidence_block_rate` | Did missing hard evidence block planning use? |
| `privacy_guard_pass_rate` | Did sensitive surfaces remain redacted or rejected? |
| `recovery_routing_rate` | Did failed observations produce bounded recovery actions? |
| `closure_verification_rate` | Did result observation match the expected effect before closure? |

## Implementation Sequence

1. Keep this document as the cross-platform architecture contract.
2. Keep existing narrow receipts as source-specific packets: repository, search,
   browser observation, trusted capture, worker failure, connector promotion,
   and ProblemStar compilation.
3. Add provider-specific evidence packet schemas only when a concrete read path
   needs them.
4. Add read-only adapter witnesses before claiming provider or connector live
   observation.
5. Project admitted packets into the World State Plane with expiry and
   contradiction handling.
6. Feed planning only through ProblemStar evidence fields.
7. Add benchmarks for missing evidence, stale evidence, contradiction handling,
   recovery routing, and closure observation.

## Non-Goals

This architecture does not:

1. Grant live inbox, calendar, CI, provider, browser, deployment, or worker
   authority.
2. Bypass connector promotion, UAO, Phi_gov, approval, or LifeMeaningJudgment.
3. Store raw secrets or unclassified private payloads.
4. Treat confidence as proof.
5. Treat evidence packets as truth commits.
6. Claim public runtime, provider, customer, deployment, or terminal readiness.
7. Weaken Mfidel atomicity for observed Amharic, Ge'ez, or Mfidel payloads.

## Verification

Run:

```powershell
python scripts/validate_observation_evidence_acquisition_architecture.py
python -m pytest tests/test_validate_observation_evidence_acquisition_architecture.py -q
python scripts/validate_repository_observation_evidence_packet.py
python -m pytest tests/test_validate_repository_observation_evidence_packet.py -q
python scripts/produce_repository_observation_evidence_packet.py --json
python scripts/validate_agents_governance.py
python scripts/validate_workspace_governance_witness.py
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-observation-evidence-architecture-20260619.json
python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-observation-evidence-architecture-20260619.json
```

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand the platform boundary | [Platform Overview](00_platform_overview.md) |
| Understand the capability planes | [Capability Planes](06_capability_planes.md) |
| Understand current world-state evidence | [World State Plane](16_world_state_plane.md) |
| Understand repository observation packets | [RepositoryObservationEvidencePacket Contract](95_repository_observation_evidence_packet_contract.md) |
| Understand pre-solver evidence separation | [ProblemStar Compilation Receipt](75_problem_star_compilation_receipt.md) |
| Understand browser observation receipts | [BrowserObservationReceipt Contract](87_browser_observation_receipt_contract.md) |
| Understand trusted capture packets | [TrustedCaptureEvidencePacket Contract](89_trusted_capture_evidence_packet_contract.md) |
| Look up a confusing word | [Glossary](GLOSSARY.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |

<- Back to [Start Here](START_HERE.md)

STATUS:
  Completeness: 100%
  Invariants verified: observation is not execution, evidence packet is not truth commit, evidence packet is not terminal closure, hard-constraint planning blocks on Unknown evidence, local repository observation has a digest-only read witness path, live provider observation remains AwaitingEvidence without witness, raw secret promotion denied, Mfidel atomicity preserved
  Open issues: live provider read witnesses, provider-specific evidence schemas, runtime evidence ledger append, and observation benchmarks remain future proof threads
  Next action: project admitted repository packets into the World State Plane with expiry and contradiction handling
