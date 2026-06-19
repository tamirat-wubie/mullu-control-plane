# WRE-A2 Research Epistemics Profile

> **Status:** Foundation Mode specification. No runtime, retrieval, synthesis,
> memory-write, truth-mutation, publication, medical, connector, or autonomous
> self-modification authority is granted.

## Purpose

WRE-A2 refines the existing Mullu research surfaces without creating a second
research engine. It defines the epistemic contract that future research-runtime
changes must satisfy.

The governing separation is:

```text
Evidence and inference determine factual confidence.
Governance determines whether an action or disclosure is permitted.
```

WHQR remains the canonical split gate: truth and evidence are not rewritten by
normative preference, while the norm gate may block, escalate, or require
approval for an action.

## Existing Substrates Reused

| WRE-A2 concern | Existing repository surface |
| --- | --- |
| Truth, evidence, and norm separation | `mcoi/mcoi_runtime/contracts/whqr.py` |
| Claim provenance and execution admission | `gateway/claim_verification.py` |
| Support, contradiction, and derivation graph | `mcoi/mcoi_runtime/contracts/universal_evidence_graph.py` |
| Questions, hypotheses, experiments, synthesis, review | `mcoi/mcoi_runtime/contracts/research_runtime.py` |
| Provenance, decay, supersession, and memory conflicts | `mcoi/mcoi_runtime/contracts/memory_mesh.py` |
| Citation-backed disagreement preservation | `schemas/research_source_conflict_map.schema.json` |
| Exact-result truth mutation boundary | `mcoi/mcoi_runtime/truth_kernel_adapter.py` |

WRE-A2 must extend these surfaces through adapters and additive contracts. It
must not introduce a parallel `WREEngine`, memory system, truth kernel, or
orchestration runtime.

## Canonical Additions

The profile introduces four requirements for later implementation:

1. **Epistemic claim type** independent from claim provenance: empirical,
   causal, predictive, historical, normative, ontological, or
   symbolic-structural.
2. **Typed confidence vector** instead of treating one scalar as canonical:
   evidential, logical, provenance, empirical, temporal applicability,
   calibration, and action safety.
3. **Explicit result disposition:** validated conclusion, supported hypothesis,
   speculative hypothesis, competing model, unresolved contradiction, partial
   result, abstention, or safety escalation.
4. **Source-lineage independence:** distinct source identifiers alone do not
   prove independent origin.

A research conclusion does not automatically become a Truth Kernel mutation.
Empirical and probabilistic results remain scoped, versioned evidence claims;
only the existing exact-result admission gate may produce a truth-commit
candidate.

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

## Sequencing

1. **Current change:** schema, fixture, validator, tests, and this boundary only.
2. **Next gate:** wait until CDG-RCCM PR `#1960` is green and merged.
3. Add immutable epistemics contracts and adapters without public routes or
   state mutation.
4. Add a parallel, opt-in synthesis path; preserve the existing runtime until
   compatibility and migration evidence pass.
5. Defer MEDICA and other high-stakes descendants to separate domain-specific
   safety and regulatory work.

## Validation

```text
python scripts/validate_research_epistemics_profile.py
python -m pytest tests/test_validate_research_epistemics_profile.py -q
```

Expected validator result:

```text
[PASS] research_epistemics_profile
```
