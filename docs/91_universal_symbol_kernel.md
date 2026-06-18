# Universal Symbol Kernel

Purpose: apply the user-defined Mullu symbol concept as a platform-wide Foundation Mode contract before live runtime authority is granted.

Governance scope: symbol identity, boundary, metadata, relations, causality, lineage, governance, proof, skill projection, authority denial, and evidence references.

Dependencies: `schemas/universal_symbol.schema.json`, `examples/universal_symbol_kernel.foundation.json`, `docs/40_proof_coverage_matrix.md`, `scripts/validate_universal_symbol_kernel.py`, `scripts/proof_coverage_matrix.py`, `tests/test_validate_universal_symbol_kernel.py`, `tests/test_proof_coverage_matrix.py`, `tests/fixtures/proof_coverage_matrix.json`, `mcoi/mcoi_runtime/core/symbol_skill_adapter.py`, `mcoi/mcoi_runtime/app/symbol_operator_read_models.py`, `mcoi/mcoi_runtime/app/software_receipt_observability.py`, `mcoi/mcoi_runtime/app/routers/components.py`, `mcoi/tests/test_symbol_skill_adapter.py`, `mcoi/tests/test_symbol_operator_read_models.py`, `mcoi/tests/test_software_receipt_observability.py`, `mcoi/mcoi_runtime/contracts/snet.py`, `mcoi/mcoi_runtime/snet/engine.py`, and `docs/MULLU_COMPONENT_HARNESS.md`.

Invariants:

- A symbol is a boundary-drawn, constraint-held, mesh-embedded causal unit.
- Concepts, skills, components, receipts, actions, questions, answers, metadata, relations, traces, proofs, failures, unknowns, policies, boundaries, and artifacts are symbolizable.
- Symbolization does not grant connector calls, runtime dispatch, filesystem writes, external writes, state mutation, terminal closure, or success claims.
- Raw private payloads and raw secret values are never retained by the Foundation Mode symbol contract.
- Skill projection is advisory only until a separate runtime adapter, authority receipt, and terminal closure witness exist.

## Plain meaning

Mullu already had SNet symbols. This kernel makes the next boundary explicit:

```text
SNet symbol machinery
+ component harness boundaries
+ receipt/proof chains
+ SCCML causal traces
= universal symbol envelope
```

This does not make every runtime object automatically symbolic yet. It creates the first canonical schema and validation gate required before that deeper conversion can be claimed.

## Core definition

```text
UniversalSymbol = identity + boundary + metadata + relations + causality + lineage + governance + proof + skill projection + authority boundary
```

A symbol may describe a concept, a skill, a component, a receipt, an action, a question, an answer, metadata, a relation, a trace, a proof, a failure, an unknown, a policy, a boundary, or an artifact.

## What this adds beyond SNet

SNet currently handles recursive WH inquiry over local symbols. The Universal Symbol Kernel adds a platform-wide envelope so non-SNet objects can later become symbol-native too.

| Existing surface | Universal-symbol interpretation |
| --- | --- |
| TeamOps provider observation receipt | `symbol_kind=receipt` |
| Software development change receipt | `symbol_kind=action` or `receipt` |
| SCCML trace adapter witness | `symbol_kind=trace` |
| Worker runtime receipt | `symbol_kind=receipt` |
| Component harness entry | `symbol_kind=component` |
| Policy boundary | `symbol_kind=policy` or `boundary` |
| Failure receipt | `symbol_kind=failure` |
| Unknown record | `symbol_kind=unknown` |

## Foundation Mode boundary

The committed example is:

```text
examples/universal_symbol_kernel.foundation.json
```

It keeps all effect-bearing authority denied:

```text
raw_private_payload_stored=false
raw_secret_value_stored=false
connector_call_performed=false
external_write_performed=false
filesystem_write_performed=false
runtime_dispatch_performed=false
state_mutation_performed=false
terminal_closure_allowed=false
success_claim_allowed=false
```

## Audit and refinement pass

The first audit found these weakness classes and applied the refinements below:

| Finding | Risk | Refinement |
| --- | --- | --- |
| Validator checked governance invariants but did not validate the example against the JSON Schema. | A malformed symbol could pass local semantic checks while violating the wire contract. | The validator now runs Draft 2020-12 JSON Schema validation with format checking. |
| Evidence references were checked for presence in the example but not for local file existence. | A stale evidence reference could silently remain in the symbol packet. | The validator now rejects local evidence refs whose files are missing. |
| Edge-case coverage did not test unknown fields or invalid symbol kinds. | Schema drift could enter without test coverage. | Tests now reject additional properties and invalid `symbol_kind` values. |
| Authority drift tests covered one connector field only. | Other authority fields still rely on shared validator logic. | The validator centralizes all authority-denial fields and verifies the denial count. |
| Foundation governance allowed authority and approval refs while still claiming no authority. | A packet could look like a Foundation contract while carrying live authority pointers. | The validator now rejects non-empty authority and approval refs for the foundation example. |
| Foundation proof state could be upgraded to `proven` without a terminal witness. | The contract could imply closure before runtime adapter evidence exists. | The validator now keeps the foundation proof state at `awaiting_evidence`. |
| Local evidence refs were not checked for repository-bound path traversal. | A symbol packet could anchor evidence outside the governed repository boundary. | The validator now rejects absolute and repository-escaping local evidence refs. |
| `symbolizable_surface_count` was not bound to the schema `symbol_kind` enum. | The summary could claim complete symbolizability while undercounting supported kinds. | The validator now derives the expected count from the schema enum and rejects drift. |
| Ref arrays could carry empty string values. | Empty refs weaken causal traceability and evidence anchoring. | The schema now requires non-empty string items for reusable ref arrays. |
| Causal state and trace refs could be empty. | A causal symbol could exist without a named pre-state, post-state, or trace. | The schema now requires non-empty `pre_state_ref`, `post_state_ref`, and `causal_trace_ref`. |

The refinement keeps the boundary narrow: schema validity, evidence-file existence, and no-authority invariants are stronger, but runtime dispatch and automatic skill symbolization remain blocked.

The current schema declares 16 supported symbol kinds, so the foundation example records `symbolizable_surface_count=16`. Future schema expansions must update the example count or the validator will reject the drift.

## Symbol Skill Adapter proof thread

The first bounded runtime-adjacent adapter now exists at:

```text
mcoi/mcoi_runtime/core/symbol_skill_adapter.py
```

It projects existing digest-only source records into schema-valid `UniversalSymbol` envelopes for:

```text
teamops_receipt
software_dev_receipt
sccml_trace
worker_receipt
component_registry_entry
generic_receipt
```

The adapter is not a live runtime admission path. It is pure and side-effect free. It accepts already-existing source records or contract objects, rejects raw payload or raw secret retention, and emits only references, digest boundaries, lineage, causality, proof state, and denied authority flags.

The focused test contract is:

```text
mcoi/tests/test_symbol_skill_adapter.py
```

It validates adapter output against `schemas/universal_symbol.schema.json` and covers software development receipts, TeamOps receipts, SCCML trace witnesses, component entries, raw payload rejection, and deterministic symbol identity.

## Read-only operator projection

The first selected operator view integration is:

```text
mcoi/mcoi_runtime/app/software_receipt_observability.py
```

It registers a sibling dashboard source:

```text
software_receipt_symbols
```

That source projects stored software development receipts into `UniversalSymbol` envelopes through the adapter. The output carries explicit inspection-only fields:

```text
read_model_is_not_execution_authority=true
symbol_projection_is_read_only=true
runtime_dispatch_performed=false
connector_call_performed=false
filesystem_write_performed=false
state_mutation_performed=false
terminal_closure_allowed=false
```

This is not runtime admission and does not persist new symbol state. It is a bounded operator read model over already-stored receipts.

The next selected operator view integration is:

```text
mcoi/mcoi_runtime/app/symbol_operator_read_models.py
```

It adds read-only symbol projections for:

```text
component registry entries
worker receipt ledger chains
```

The component projection is exposed through a GET-only route:

```text
/api/v1/components/symbols
```

The worker projection reads only `examples/worker_receipt_ledger_read_model.foundation.json`; it does not read a live receipt store, dispatch a worker, emit runtime receipts, invoke connectors, or claim closure.

## Proof coverage binding

The proof coverage matrix now carries a dedicated surface:

```text
universal_symbol_operator_read_models
```

It binds the component symbol route, software receipt symbol observability source, and worker receipt symbol projection to concrete test witnesses. The canonical machine witness is:

```text
tests/fixtures/proof_coverage_matrix.json
```

## Verification

Run:

```powershell
python scripts\validate_universal_symbol_kernel.py
python -m pytest tests\test_validate_universal_symbol_kernel.py -q
python -m pytest mcoi\tests\test_symbol_skill_adapter.py -q
python -m pytest mcoi\tests\test_software_receipt_observability.py -q
python -m pytest mcoi\tests\test_symbol_operator_read_models.py -q
python -m pytest tests\test_proof_coverage_matrix.py -q
```

Expected result:

```text
[PASS] universal_symbol_kernel
STATUS: passed
```

## What it does not claim

This contract does not claim:

```text
live universal symbol runtime
automatic skill symbolization
connector access
filesystem writes
runtime dispatch
state mutation
terminal closure
product readiness
customer readiness
public SaaS readiness
```

## Next action

The next real implementation step is a proof-state coverage report that compares symbol projections against proof coverage matrix surfaces without granting runtime authority.

STATUS:
  Completeness: foundation boundary added, audit-refined, first Symbol Skill Adapter proof thread added, software receipt read-only operator projection added, component/worker symbol projections added, and proof coverage matrix binding added
  Invariants verified by validator and tests: JSON Schema conformance, symbol-native envelope, 16 symbol kinds, everything-symbolizable flag, evidence-file presence, repository-bound evidence refs, authority denial, no raw private payload, no raw secret, no authority refs, no approval refs, no terminal closure, awaiting-evidence proof state, read-only symbol projection, proof matrix witness binding
  Open issues: proof-state coverage report, adapter receipt persistence policy, and skill-by-skill runtime admission remain AwaitingEvidence
