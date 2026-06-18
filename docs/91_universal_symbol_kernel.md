# Universal Symbol Kernel

Purpose: apply the user-defined Mullu symbol concept as a platform-wide Foundation Mode contract before live runtime authority is granted.

Governance scope: symbol identity, boundary, metadata, relations, causality, lineage, governance, proof, skill projection, authority denial, and evidence references.

Dependencies: `schemas/universal_symbol.schema.json`, `examples/universal_symbol_kernel.foundation.json`, `scripts/validate_universal_symbol_kernel.py`, `tests/test_validate_universal_symbol_kernel.py`, `mcoi/mcoi_runtime/contracts/snet.py`, `mcoi/mcoi_runtime/snet/engine.py`, and `docs/MULLU_COMPONENT_HARNESS.md`.

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

The refinement keeps the boundary narrow: schema validity, evidence-file existence, and no-authority invariants are stronger, but runtime dispatch and automatic skill symbolization remain blocked.

## Verification

Run:

```powershell
python scripts\validate_universal_symbol_kernel.py
python -m pytest tests\test_validate_universal_symbol_kernel.py -q
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

The next real implementation step is a Symbol Skill Adapter that converts existing TeamOps, software_dev, SCCML, worker, and component receipts into `UniversalSymbol` records while preserving their existing authority boundaries.

STATUS:
  Completeness: foundation boundary added and audit-refined
  Invariants verified by validator and tests: JSON Schema conformance, symbol-native envelope, everything-symbolizable flag, evidence-file presence, authority denial, no raw private payload, no raw secret, no terminal closure
  Open issues: runtime symbol adapter, proof coverage matrix binding, and skill-by-skill symbolization remain AwaitingEvidence
