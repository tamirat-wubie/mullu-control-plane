# Research Epistemics Profile v1

> **Status:** Foundation Mode specification. No runtime research execution,
> retrieval, synthesis, memory-write, truth-mutation, publication, medical,
> connector, external-action, or autonomous architecture-modification authority
> is granted.

## Purpose

Research Epistemics Profile v1 is the bounded epistemic configuration for Mullu
Govern Research. It refines the existing MCOI research surfaces without creating
a second stateful research engine.

The complete architecture is named **MCOI Governed Research Architecture**. The
legacy migration label `WRE-A2` is retained only as a historical branch and PR
reference until migration closure; it is not the canonical technical name.

## Canonical Names

| Scope | Canonical name |
| --- | --- |
| Public capability | Mullu Govern Research |
| Internal architecture | MCOI Governed Research Architecture |
| Epistemic configuration | Research Epistemics Profile v1 |
| Existing workflow runtime | ResearchRuntimeEngine |
| Legacy migration name | `WRE-A2` (non-canonical; retire after migration) |

## Architecture Projection

```text
R_MCOI := <G,Q,E,W,V,M,A,H>
```

| Symbol | Meaning |
| --- | --- |
| G | governance |
| Q | question and scope |
| E | epistemics and evidence |
| W | workflow and convergence |
| V | validation |
| M | memory and revision |
| A | authority and effect boundary |
| H | provenance and causal history |

The governing separation remains:

```text
Evidence and inference determine factual confidence.
Governance determines permissible action and disclosure.
```

WHQR remains the canonical split gate: truth and evidence are not rewritten by
normative preference, while the norm gate may block, escalate, or require
approval for an action.

## Existing Substrates Reused

| Concern | Existing repository surface |
| --- | --- |
| Truth, evidence, and norm separation | `mcoi/mcoi_runtime/contracts/whqr.py` |
| Claim provenance and execution admission | `gateway/claim_verification.py` |
| Support, contradiction, and derivation graph | `mcoi/mcoi_runtime/contracts/universal_evidence_graph.py` |
| Questions, hypotheses, experiments, synthesis, review | `mcoi/mcoi_runtime/contracts/research_runtime.py` |
| Provenance, decay, supersession, and memory conflicts | `mcoi/mcoi_runtime/contracts/memory_mesh.py` |
| Citation-backed disagreement preservation | `schemas/research_source_conflict_map.schema.json` |
| Exact-result truth mutation boundary | `mcoi/mcoi_runtime/truth_kernel_adapter.py` |

Research Epistemics Profile v1 extends these surfaces through additive
contracts. It must not introduce a parallel research engine, memory system,
truth kernel, or orchestration runtime.

## Ready-Now Contracts

The current bounded implementation covers these contracts only:

```text
ResearchEpistemicsProfile
EpistemicClaimType
ResearchConfidenceVector
ResearchDisposition
ResearchAbstentionRecord
SourceLineageRecord
ResearchContradictionRecord
```

`EpistemicClaimType` describes the semantic type of a research claim and remains
separate from the existing `ClaimKind`, which describes provenance such as
observed fact, user claim, model inference, or external-source claim.

Canonical `EpistemicClaimType` values:

```text
EMPIRICAL
CAUSAL
PREDICTIVE
HISTORICAL
NORMATIVE
ONTOLOGICAL
SYMBOLIC_STRUCTURAL
```

Canonical `ResearchConfidenceVector` dimensions:

```text
evidential
logical
provenance
empirical
temporal_applicability
calibration
action_safety
```

One scalar confidence may be retained only as a compatibility projection. It is
not the canonical epistemic state.

Canonical `ResearchDisposition` values:

```text
VALIDATED_CONCLUSION
SUPPORTED_HYPOTHESIS
SPECULATIVE_HYPOTHESIS
COMPETING_MODEL
UNRESOLVED_CONTRADICTION
PARTIAL_RESULT
ABSTENTION
SAFETY_ESCALATION
```

Canonical `ResearchAbstentionRecord` fields:

```text
blocked_claim_ref
reason
missing_requirements
safe_partial_result_refs
required_next_evidence
```

Canonical `SourceLineageRecord` fields:

```text
source_id
origin_digest
parent_source_refs
citation_ancestry
derivative_status
independence_group
retrieved_at
integrity_status
```

Distinct source identifiers do not automatically count as independent evidence.

Canonical `ResearchContradictionRecord` fields:

```text
contradiction_id
claim_refs
contradiction_class
scope_overlap
temporal_overlap
severity
cause_candidates
resolution_attempts
branch_status
```

Canonical contradiction classes:

```text
FACTUAL
DEFINITIONAL
TEMPORAL
SCOPE
METHODOLOGICAL
STATISTICAL
ONTOLOGICAL
NORMATIVE
MODEL_DEPENDENT
EXECUTION_FAILURE
```

A failed experiment is not automatically a factual contradiction.

## Deferred Contracts

These contracts remain blocked until CDG-RCCM is stable and a separate
operator-reviewed implementation thread opens:

```text
ResearchCapabilityRouter
ResearchValidationProfile
ResearchClosureCertificate
ResearchMemoryAdmissionGate
```

External retrieval authority, automatic publication, Truth Kernel promotion of
empirical conclusions, autonomous architecture modification, and medical
diagnosis or treatment authority remain deferred.

## Current Authority Boundary

All fields below remain false in the Foundation fixture:

```text
runtime_research_execution_allowed
external_retrieval_allowed
connector_calls_allowed
answer_synthesis_authority
memory_write_allowed
truth_mutation_allowed
publication_allowed
medical_decision_authority
autonomous_self_modification_allowed
```

## Truth, Memory, and External-Action Boundary

A research conclusion does not automatically become a Truth Kernel mutation.
Approximate, contradicted, budget-limited, or uncertain research results remain
evidence-bearing claims unless the existing exact-result admission gate accepts
them.

Research conclusions must not automatically receive `VERIFIED` trust or
confidence `1.0`. Memory admission requires complete provenance, explicit
disposition, recorded contradictions, defined temporal validity, integrity
checks, and no poisoning alert.

External publication or action requires:

```text
ResearchClosureCertificate
-> authority evidence
-> risk policy
-> approval
-> effect plan
-> execution receipt
-> verification
```

No research result bypasses Universal Action or governance surfaces.

## Validation

```text
python scripts/validate_research_epistemics_profile.py
python -m pytest tests/test_validate_research_epistemics_profile.py -q
```

Expected validator result:

```text
[PASS] research_epistemics_profile
```
