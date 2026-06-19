# Non-Live OpenQASM Export Planning Witness

Purpose: define a Foundation Mode witness for planning a future OpenQASM export path without emitting OpenQASM source, invoking a simulator, calling a backend, reading credentials, or claiming quantum results.

Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/93_universal_symbolic_quantum_capability_boundary.md`, `schemas/non_live_openqasm_export_planning_witness.schema.json`, `examples/non_live_openqasm_export_planning_witness.foundation.json`, `scripts/validate_non_live_openqasm_export_planning_witness.py`.
Invariants: planning only; read only; no source emission; no simulator execution; no backend call; no quantum job submission; no quantum advantage claim; no production readiness claim; no terminal closure.

## Integration Decision

The OpenQASM path fits only as a non-live export planning witness beneath the universal symbolic quantum capability boundary.

Accepted role:

```text
symbolic circuit intent capture
OpenQASM target version declaration
register sizing plan
gate set plan
measurement mapping plan
resource projection plan
export precondition list
witness ledger requirement
```

Denied role:

```text
OpenQASM source emission
QIR source emission
simulator invocation
backend execution
hardware credential access
quantum job submission
cryptanalysis execution
quantum advantage claim
production readiness claim
terminal closure
```

## Planning Chain

```text
USQCA-PQE Foundation Mode Boundary
-> non-live OpenQASM export planning witness
-> symbolic circuit intent
-> target version declaration
-> register and measurement plan
-> gate set and resource projection
-> future exporter witness requirement
-> no emitted source and no execution authority
```

## Required Planning Gates

```text
ParentQuantumBoundaryGate
OpenQasmVersionDeclarationGate
SymbolicCircuitIntentGate
RegisterSizingGate
GateSetDeclarationGate
MeasurementMappingGate
ResourceProjectionGate
BackendIndependenceGate
NoExecutionAuthorityGate
WitnessLedgerGate
```

## Immutable Invariants

1. A planning witness is not an exporter.
2. A target OpenQASM version declaration is not emitted source code.
3. A circuit intent plan is not simulator input.
4. A resource projection is not backend feasibility proof.
5. A measurement mapping plan is not an observed result distribution.
6. Backend-specific pragmas are denied in this planning layer.
7. Any future exporter requires a separate witness, schema, validator, resource evidence, and operator authorization.
8. No OpenQASM, QIR, simulator, backend, credential, or job-submission effect is created by this witness.

## Constructive Deltas

- Adds a non-live OpenQASM planning witness under the existing quantum boundary.
- Defines the preconditions a later exporter must satisfy before source emission.
- Keeps the quantum path useful for architecture review without creating runtime authority.

## Fracture Deltas

- No OpenQASM source is emitted.
- No QIR source is emitted.
- No simulator runtime is invoked.
- No backend is called.
- No hardware credentials are read.
- No quantum result, advantage, fault-tolerant, or production readiness claim is made.

## Next Valid Action

Review this planning witness alongside `docs/95_non_live_local_quantum_simulator_boundary_witness.md`. A later exporter implementation must be a separate governed change with source-emission authority, exporter tests, resource honesty evidence, and a no-execution boundary.
