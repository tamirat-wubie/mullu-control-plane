# Mullu Reasoning Integrity Mesh

Purpose: define a narrow reasoning governance pack that blocks unsupported
completion claims, separates concept/spec/code/runtime scopes, and keeps
judgments evidence-bound.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

Dependencies:
- `governance/reasoning_method_registry.yaml`
- `governance/judgment_integrity_gate.yaml`
- `governance/weakness_taxonomy.yaml`
- `governance/reasoning_edge_case_forge.yaml`
- `scripts/validate_reasoning_integrity_mesh.py`
- `tests/governance/test_reasoning_integrity_mesh.py`

Invariants:
- Reasoning claims must remain scoped to concept, spec, code, or runtime.
- Completion claims require evidence references and validator references.
- High confidence requires evidence references.
- Local contradictions cannot become global truth.
- Recursive refinement terminates when no new constructive or fracture delta
  exists.
- Metaphor or interface language cannot override governance mechanism.

---

## 1. Decision

The Reasoning Integrity Mesh is a Foundation Mode governance pack. It adds
documentation, governance ledgers, a read-only validator, and focused tests.
It does not add runtime authority, routes, dispatch paths, connector calls,
or production-readiness claims.

The pack is admitted only as a local proof surface:

```text
reasoning_claim -> scope_classification -> evidence_gate
  -> contradiction_scope_check -> recursive_settlement_check
  -> metaphor_mechanism_check -> judgment
```

## 2. Scope Boundary

| Scope | Meaning | Allowed claim | Blocked claim |
| --- | --- | --- | --- |
| concept | idea or architectural intention | "The concept is defined." | "The feature is implemented." |
| spec | written contract or requirement | "The contract exists." | "Runtime behavior is proven." |
| code | checked-in implementation or validator | "The code path exists." | "The service is live." |
| runtime | observed execution evidence | "This run passed this witness." | "All future runs are solved." |

Required invariant: `concept_spec_code_runtime_scope_separation`.

## 3. Method Registry Contract

The method registry names the only reasoning methods admitted by this pack:

1. `scope_classifier`
2. `evidence_bound_completion_check`
3. `confidence_evidence_gate`
4. `contradiction_scope_limiter`
5. `recursive_delta_settlement`
6. `metaphor_mechanism_guard`

Every method must declare required inputs, required evidence references,
blocked claims, output contract, failure mode, and governance laws.

## 4. Judgment Integrity Gate

The judgment gate fail-closes on these hard rules:

| Rule | Required behavior |
| --- | --- |
| `unsupported_completion_claim` | reject completion claims without evidence and validator references |
| `scope_confusion_claim` | reject concept/spec/code/runtime scope substitution |
| `high_confidence_without_evidence` | reject high confidence without evidence references |
| `local_contradiction_globalized` | reject local contradictions promoted to global truth |
| `unbounded_recursive_refinement` | reject recursive refinement without a delta stop condition |
| `metaphor_over_mechanism` | reject metaphor or interface language used as mechanism proof |

Required invariant: `high_confidence_requires_evidence_refs`.

## 5. Weakness Taxonomy

The taxonomy defines six hard weakness classes:

1. `false_completion_claim`
2. `scope_confusion`
3. `confidence_overclaim`
4. `contradiction_globalization`
5. `recursive_nontermination`
6. `metaphor_mechanism_override`

Each class must declare detection, repair, severity, and a proof obligation.

## 6. Edge Case Forge

The edge-case forge must include rejection cases for:

1. concept text claiming runtime completion;
2. spec text claiming code implementation;
3. code existence claiming live runtime behavior;
4. high confidence without evidence references;
5. local contradiction promoted to global truth;
6. recursive refinement with no new constructive or fracture delta;
7. metaphor/interface wording replacing mechanism evidence.

It must also include one positive evidence-bound completion case so the gate
does not collapse into unconditional denial.

## 7. Recursive Refinement Termination

Recursive refinement is permitted only when each pass emits at least one new
constructive delta or fracture delta. The fixed point is:

```text
if constructive_delta_count == 0 and fracture_delta_count == 0:
  stop_refinement
```

Required invariant: `recursive_refinement_stops_on_empty_delta`.

## 8. Acceptance Contract

The validator must prove:

1. `unsupported_completion_claim` is rejected unless evidence is present.
2. `concept_spec_code_runtime_scope_separation` is enforced.
3. `high_confidence_requires_evidence_refs` is enforced.
4. `local_contradiction_cannot_be_global_truth` is enforced.
5. `recursive_refinement_stops_on_empty_delta` is enforced.
6. `metaphor_interface_language_cannot_override_mechanism` is enforced.

## 9. Proof-of-Resolution Stamp

```text
PRS:
  change_id: reasoning_integrity_mesh_pack
  affected_surfaces: docs/reasoning, governance, scripts, tests/governance
  symbols_defined: ReasoningIntegrityMesh, JudgmentIntegrityGate, WeaknessTaxonomy, EdgeCaseForge
  constraints_enforced: evidence-bound completion, scope separation, high-confidence evidence, local contradiction boundary, recursive fixed point, mechanism proof
  invariants_preserved: no runtime behavior change, no connector authority, no public readiness claim, Foundation Mode only
  tests_or_validators: scripts/validate_reasoning_integrity_mesh.py, tests/governance/test_reasoning_integrity_mesh.py
  witness_artifacts: governance/reasoning_method_registry.yaml, governance/judgment_integrity_gate.yaml, governance/weakness_taxonomy.yaml, governance/reasoning_edge_case_forge.yaml
  rollback_or_halt_path: remove the pack files or revert the issue branch; validator fail-closes on drift
  open_issues: none
```

STATUS:
  Completeness: 100%
  Invariants verified: unsupported completion claims require evidence, concept/spec/code/runtime separation, high confidence requires evidence refs, local contradictions remain local, recursive refinement terminates on empty delta, metaphor/interface language cannot override mechanism
  Open issues: none
  Next action: use the mesh as the bounded reasoning guard for future completion-claim surfaces
