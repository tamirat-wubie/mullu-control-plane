<!--
Purpose: define the Foundation Mode dependency-graph boundary for local public-safe dependency question drafting without claiming graph completeness, dependency contract readiness, import readiness, package install approval, version-lock readiness, service dependency binding, provider binding, vulnerability scan pass, runtime readiness, owner approval, test pass, implementation, publication, or deployment.
Governance scope: module dependency questions, package dependency questions, runtime dependency questions, service dependency questions, provider dependency questions, data dependency questions, governance dependency questions, operator dependency questions, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md, examples/foundation_dependency_graph_witness.awaiting_evidence.json, scripts/validate_foundation_dependency_graph_boundary.py.
Invariants: no dependency-graph completeness claim, no dependency contract readiness claim, no import boundary readiness claim, no package install approval, no version-lock readiness claim, no service dependency binding, no external provider binding, no vulnerability scan pass claim, no runtime dependency readiness claim, no owner approval assignment, no test pass claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Dependency Graph Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** dependency-graph preparation means drafting local public-safe
> questions about what modules, packages, runtimes, services, providers, data
> stores, governance surfaces, and operator workflows may depend on. It does
> not prove dependencies are complete, installed, version-locked, scanned,
> bound to services, ready at runtime, implemented, publishable, or deployable.

Witness packet: [`../examples/foundation_dependency_graph_witness.awaiting_evidence.json`](../examples/foundation_dependency_graph_witness.awaiting_evidence.json)

Rule: Dependency-graph preparation is a local planning boundary, not a
dependency-graph-completion, dependency-contract-readiness, import-readiness,
package-install, version-lock, service-dependency-binding, provider-binding,
vulnerability-scan-pass, runtime-readiness, owner-approval, test-pass,
refactor-approval, implementation-approval, publication, or deployment
certificate.

No dependency-graph completeness, dependency contract readiness, import
boundary readiness, package install approval, version-lock readiness, service
dependency binding, external provider binding, vulnerability scan pass, runtime
dependency readiness, owner approval assignment, test pass, refactor approval,
implementation approval, external publication, or deployment claim is permitted
by this boundary.

## What This Boundary Solves

Interface maps show how components meet. Dependency graphs show what each
surface relies on. This boundary lets the repository prepare dependency
questions without installing packages, binding external providers, activating
services, pinning versions as ready, claiming scans, or approving
implementation.

This is preparation only:

1. The repository can name dependency-graph surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature dependency, install, binding, scan, runtime,
   owner, test, implementation, publication, or deployment claims.
4. Private endpoints, account identifiers, package targets, secrets,
   credentials, customer data, service targets, and local private paths stay
   out of the public packet.

## Current State

```text
dependency_graph_boundary_state=AwaitingEvidence
dependency_graph_complete_claimed=false
dependency_contract_ready_claimed=false
import_boundary_ready_claimed=false
package_install_allowed=false
version_lock_ready_claimed=false
service_dependency_bound=false
external_provider_bound=false
vulnerability_scan_pass_claimed=false
runtime_dependency_ready_claimed=false
owner_approval_assigned=false
test_pass_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Dependency-Graph Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Module dependencies | Draft module-to-module dependency questions. | Do not claim dependency-graph completeness. |
| Package dependencies | Draft package and library questions. | Do not install or pin packages as ready. |
| Runtime dependencies | Draft runtime and process questions. | Do not claim runtime dependency readiness. |
| Service dependencies | Draft internal service dependency questions. | Do not bind services or endpoints. |
| Provider dependencies | Draft provider and account-boundary questions. | Do not bind external providers. |
| Data dependencies | Draft data store and retention dependency questions. | Do not claim data readiness. |
| Governance dependencies | Draft policy, approval, and receipt dependency questions. | Do not claim governance integration readiness. |
| Operator dependencies | Draft operator workflow and support dependency questions. | Do not claim owner, support, exposure, or deployment readiness. |

## Operator Procedure

1. Pick one dependency surface from the table.
2. Draft only public-safe dependency questions.
3. Avoid URLs, emails, private paths, provider account ids, package targets,
   service targets, endpoint targets, customer identifiers, secrets,
   credentials, implementation ids, refactor ids, scan-pass claims, test-pass
   claims, or deployment targets.
4. Mark unknown packages, imports, versions, services, providers, scans,
   runtime behavior, owner approval, tests, implementation, and exposure points
   as `AwaitingEvidence`.
5. Do not use this graph to authorize dependency installs, service activation,
   provider binding, coding, refactor, publication, external exposure,
   customer access, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_dependency_graph_boundary.py
```

The validator checks that the dependency-graph witness:

1. keeps graph completeness, dependency contract readiness, import readiness,
   package install, version-lock readiness, service dependency binding, provider
   binding, vulnerability scan pass, runtime dependency readiness, owner
   approval, test pass, refactor approval, implementation approval,
   publication, and deployment disabled;
2. keeps every dependency-graph surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, package,
   dependency, customer, secret, credential, service, implementation, refactor,
   scan-pass, test-pass, publication, or deployment shaped values; and
4. rejects dependency-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare interface maps safely | [Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md) |
| Prepare local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: dependency-graph completeness blocked, dependency contract readiness blocked, import boundary readiness blocked, package install blocked, version-lock readiness blocked, service dependency binding blocked, external provider binding blocked, vulnerability scan pass blocked, runtime dependency readiness blocked, owner approval blocked, test pass blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: module-dependency evidence, package-dependency evidence, runtime-dependency evidence, service-dependency evidence, provider-dependency evidence, data-dependency evidence, governance-dependency evidence, and operator-dependency evidence remain AwaitingEvidence
  Next action: run the dependency-graph validator before using dependency notes as readiness evidence
