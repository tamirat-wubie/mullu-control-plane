# Causal Dependency-Gated Recursive Component Convergence Mesh

> **Status:** Foundation Mode reference runtime. The package is additive and is
> not registered as a public route, connector, deployment service, or autonomous
> execution authority.

Purpose: define and implement the governed recursive working pattern in which a
component may pause one blocked continuation, recursively settle exact inner or
related component requirements, resume from the preserved point, reconcile the
returned results, reopen causally affected work, and certify only the active
required closure.

Governance scope: component contracts, exact projection requests, continuation
frames, dual topology, scheduling, settlement, certificates, causal
invalidation, cycle diagnosis, semantic feedback convergence, persistence,
closure certification, SNet adaptation, Universal Action handoff, and external
effect barriers.

Dependencies: `mcoi/mcoi_runtime/convergence`, the existing SNet runtime, and
the existing Universal Action Kernel. The convergence package does not replace
those systems.

## Canonical Name

**Causal Dependency-Gated Recursive Component Convergence Mesh**

Short name:

```text
CDG-RCCM
```

Reference runtime:

```text
Recursive Convergence Orchestration Kernel
```

Primary execution algorithm:

```text
Dependency-Gated Recursive Convergence Algorithm
```

## Governing Pattern

```text
frame component work
-> discover exact dependency projection
-> preserve blocked continuation
-> recursively activate provider component
-> settle provider to required level
-> issue versioned projection certificate
-> resume blocked continuation
-> integrate dependency result
-> validate local invariants
-> reconcile component boundaries
-> issue component certificate
-> invalidate causally affected consumers when results change
-> certify the active required closure when quiescent
```

The central rule is:

```text
A blocked continuation advances only when every hard dependency request has a
current certificate for the exact requested projection at or above the required
settlement level.
```

## Package Map

| Module | Responsibility |
| --- | --- |
| `contracts.py` | Immutable contracts, requests, frames, certificates, outcomes, and audit events. |
| `topology.py` | Separate containment graph, typed dependency mesh, active closure, SCC detection, and cycle classification. |
| `invalidation.py` | Projection read index and causal stale-certificate propagation. |
| `kernel.py` | Fair frame scheduler, recursive provider activation, certification, convergence regions, and closure. |
| `persistence.py` | Deterministic snapshot and recovery without serializing executable component code. |
| `effects.py` | Closure-gated idempotent effect staging, execution verification, compensation, and recovery. |
| `adapters/snet.py` | Parent-after-child certification for the existing SNet recursive inquiry prototype. |
| `adapters/universal_action.py` | Closure-certificate gate in front of the existing Universal Action Kernel. |

## Dual Topology

### Containment graph

The containment graph represents ownership or physical/logical inclusion:

```text
system contains subsystem
component contains part
project contains task
```

It must remain acyclic. A containment cycle is rejected as a modeling error.

### Dependency mesh

The dependency mesh represents causal requirements:

```text
requires
constrains
observes
reconciles_with
shares
alternative_to
precedes
evidences
temporal_previous
supersedes
resource_wait
authority_wait
```

Dependency cycles are diagnosed rather than treated uniformly.

## Cycle Classes

| Cycle class | Kernel response |
| --- | --- |
| `structural_containment` | Reject topology. |
| `semantic_feedback` | Execute the declared bounded convergence region. |
| `temporal_feedback` | Block until an explicit epoch relation is supplied. |
| `resource_deadlock` | Block and require resource-order or preemption repair. |
| `authority_deadlock` | Block and require governance escalation. |
| `alternative_selection` | Return bounded uncertainty unless a selection policy resolves it. |
| `hidden_self_dependency` | Fail closed because an undeclared self-read was exposed. |

Strongly connected component detection identifies a cyclic region. It does not,
by itself, authorize fixed-point execution. Only a diagnosed semantic feedback
region with component convergence methods may run through the region solver.

## Settlement Levels

| Level | Meaning |
| --- | --- |
| `PROVISIONAL` | Working result that may still change. |
| `LOCALLY_STABLE` | Local convergence and invariant checks hold. |
| `BOUNDARY_RECONCILED` | Required component interfaces and dependency boundaries pass. |
| `CLOSURE_CERTIFIED` | The active required closure is quiescent and current. |
| `WORLD_VERIFIED` | A physical observation supports the external-world claim. |

A component step cannot issue its own certificate. It submits a `Candidate`; the
kernel invokes the component validator and reconciler and then constructs the
certificate.

## Exact Dependency Request

A request binds:

```text
consumer component
provider component
projection name
minimum settlement level
dependency gate
relation type
consistency mode
epoch
assumptions
freshness bound
fallback providers
quorum
```

This prevents a consumer from waiting for unrelated provider work.

## Continuation Suspension

A `ContinuationFrame` stores:

```text
component and root identity
epoch
phase and resume token
partial state
target projections
pending dependency requests
dependency certificate versions
projection read set
generation and depth
priority and lifecycle status
parent frame
```

Only the blocked frame is suspended. Other frames belonging to the same
component or root may remain runnable.

## Certificates

A `ProjectionCertificate` binds:

```text
component and projection
epoch
settlement level
state hash
rule hash
input hash
dependency certificate lineage
assumptions
evidence references
evidence scope
confidence
projection value
audit digest
current/stale state
```

A certificate remains valid only while its causal basis remains current.

## Causal Invalidation

Consumers record exact projection paths in a read index. When a projection
changes:

```text
changed projection path
-> stale prior provider certificate
-> stale dependent certificates recursively
-> identify frames that consumed the changed path
-> restore their preserved replay continuation
-> enqueue only those affected frames
```

The implementation favors correctness over minimal recomputation. Conservative
over-invalidation is acceptable; under-invalidation is not.

## Active Required Closure

For root component `r`, only the transitive closure of blocking dependency
requests is required for root certification. Unrelated registered components and
inactive alternatives do not block the result.

Closure requires:

```text
no active ready or running frame
no unresolved hard dependency in the active closure
all active frames quiescent
all root projection certificates current
all root projections boundary reconciled
no terminal component fault, conflict, cancellation, or blocked dependency
```

The closure certificate extends the root boundary certificate and records the
active closure plus the current audit digest.

## External Effects

Component steps are intended to remain side-effect free. External actions pass
through a separate barrier:

```text
closure certificate
-> explicit authority references
-> idempotent effect plan
-> injected executor
-> injected verifier
-> verified receipt or compensation
-> recovery-required outcome when automatic repair is insufficient
```

The `UniversalActionClosureAdapter` permits an existing Universal Action Kernel
request only when the supplied certificate is current and at least
`CLOSURE_CERTIFIED` and the caller-provided authority check passes.

A simulation or model certificate cannot become `WORLD_VERIFIED`. That level
requires a `WorldObservation` whose evidence scope is
`PHYSICALLY_VERIFIED`.

## SNet Integration

The existing SNet prototype settles a symbol from local records before its
promoted children are expanded. The adapter preserves that local inquiry state
but changes component certification order:

```text
run local SNet tick
-> discover promoted child symbols
-> request each child symbol projection at BOUNDARY_RECONCILED
-> suspend parent continuation
-> recursively settle child adapters
-> resume parent
-> issue parent candidate and certificate
```

No SNet connector, filesystem, route, or dispatch authority is added.

## Persistence

`dump_kernel_snapshot` stores deterministic runtime data:

```text
frames
requests and request solutions
provider-frame bindings
certificates and latest-certificate index
audit events
component terminal outcomes
containment edges
projection read index
current epoch and root context
```

Executable component code is not serialized. Recovery requires the caller to
supply compatible component implementations before restoring the saved state.
Malformed or version-incompatible snapshots fail closed.

## Outcome Taxonomy

```text
CERTIFIED
UNSAT
UNKNOWN
BLOCKED
STALE
FAULT
CANCELLED
DEGRADED
RECOVERY_REQUIRED
```

No non-success outcome is silently converted to certification.

## Safety Invariants

```text
No containment cycle is accepted.
No component self-certifies.
No undeclared output projection is certified.
No blocked continuation loses its resume point.
No cross-epoch frame is executed.
No stale certificate satisfies a dependency.
No changed consumed projection remains unpropagated.
No semantic cycle executes without declared region methods.
No root closure is issued before active-closure quiescence.
No direct external effect bypasses closure and authority gates.
No physical-world claim exceeds its evidence scope.
```

## Validation

```powershell
python -m py_compile mcoi/mcoi_runtime/convergence/*.py mcoi/mcoi_runtime/convergence/adapters/*.py scripts/validate_cdg_rccm_component_contract.py
python -m pytest mcoi/tests/test_recursive_convergence_kernel.py mcoi/tests/test_cdg_rccm_component_contract.py -q
python scripts/validate_cdg_rccm_component_contract.py
python scripts/validate_sdlc_artifact.py
python scripts/proof_coverage_matrix.py --check
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-cdg-rccm-20260618.json
```

## Current Boundary

This package is a reference runtime and adapter layer. This change does not:

```text
register a public API route
activate a connector
start a standing worker
change the system of record
replace workflow or Universal Action runtime behavior
claim production readiness
claim arbitrary convergence
claim deployment closure
```

Promotion beyond this boundary requires separate security, authority, runtime,
operational, rollback, and deployment evidence.
