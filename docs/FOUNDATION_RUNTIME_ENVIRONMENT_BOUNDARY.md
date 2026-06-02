<!--
Purpose: define the Foundation Mode runtime and environment boundary before any runtime-readiness claim, dependency-install claim, database activation, container activation, network endpoint activation, cloud runtime activation, migration execution, public endpoint publication, or deployment claim.
Governance scope: local runtime posture, workstation repeatability posture, dependency posture, database posture, container posture, endpoint posture, no cloud runtime, no migration execution, no public endpoint, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_runtime_environment_witness.awaiting_evidence.json, scripts/validate_foundation_runtime_environment_boundary.py.
Invariants: no local runtime verification claim, no workstation repeatability claim, no dependency install verification claim, no database runtime activation, no container runtime activation, no network endpoint activation, no public endpoint publication, no cloud runtime activation, no migration execution, no deployment claim.
-->

# Foundation Runtime Environment Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** runtime/environment preparation means drafting the local
> command list, toolchain questions, and repeatability checks needed before a
> runtime is trusted. It does not verify the workstation, activate databases,
> start containers, open endpoints, run migrations, connect cloud runtimes, or
> deploy anything.

Witness packet: [`../examples/foundation_runtime_environment_witness.awaiting_evidence.json`](../examples/foundation_runtime_environment_witness.awaiting_evidence.json)

Rule: Runtime/environment preparation is a local planning boundary, not permission to claim runtime readiness.

No local runtime verification, workstation repeatability verification,
dependency-install verification, database runtime activation, container runtime
activation, network endpoint activation, public endpoint publication, cloud
runtime activation, migration execution, or deployment claim is permitted by
this boundary.

## What This Boundary Solves

Local proof needs a repeatable environment, but environment work can quietly
turn into live services, database state, exposed endpoints, or deployment
pressure. This boundary keeps setup work public-safe and local until later
evidence proves each runtime surface.

This boundary keeps the work small:

1. Draft local command categories.
2. Draft toolchain, dependency, database, container, endpoint, migration, and
   rollback questions.
3. Keep real environment values, connection strings, ports, hostnames, private
   paths, and provider targets out of the repository.
4. Keep runtime and deployment readiness in `AwaitingEvidence`.

## Current State

```text
runtime_environment_boundary_state=AwaitingEvidence
local_runtime_verified=false
workstation_repeatability_verified=false
dependency_install_verified=false
database_runtime_allowed=false
container_runtime_allowed=false
network_endpoint_allowed=false
public_endpoint_allowed=false
cloud_runtime_allowed=false
migration_execution_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not store or claim here |
| --- | --- | --- |
| Runtime command inventory | Command categories only. | Live command output, hostnames, ports, or runtime-ready claim. |
| Toolchain version questions | Version questions only. | Verified workstation or dependency-install claim. |
| Dependency install questions | Install-risk questions only. | Installed-state proof or package registry credentials. |
| Database runtime questions | Database-role questions only. | Connection strings, migrations, or active database state. |
| Container runtime questions | Container-boundary questions only. | Active containers, registry targets, or image publication. |
| Endpoint exposure questions | Exposure-risk questions only. | Network listeners, public endpoints, or routing targets. |
| Migration rollback questions | Rollback questions only. | Executed migrations or state-changing database proof. |
| Local verification checklist | Checklist labels only. | Runtime readiness or deployment readiness. |

## Operator Procedure

1. Keep runtime/environment materials as local drafts.
2. Do not start public endpoints, cloud runtimes, database services, containers,
   or migrations through this boundary.
3. Do not store connection strings, hostnames, port assignments, registry
   targets, private paths, secrets, or environment variable assignments.
4. Do not claim local runtime readiness, workstation repeatability, dependency
   installation, or deployment readiness without later witness evidence.
5. Treat every runtime/environment surface as `AwaitingEvidence` until a later
   witness promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_runtime_environment_boundary.py
```

The validator checks that the witness packet:

1. keeps every runtime/environment surface in `AwaitingEvidence`;
2. blocks runtime verification, workstation verification, dependency-install
   verification, database activation, container activation, endpoint activation,
   cloud runtime activation, migration execution, and deployment;
3. rejects URL, email, private-path, environment-assignment, endpoint-shaped,
   port-shaped, connection-string-shaped, registry-shaped, or secret-shaped
   values; and
4. rejects runtime/environment readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare cost/budget safely | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: local runtime verification blocked, workstation repeatability blocked, dependency-install verification blocked, database runtime blocked, container runtime blocked, network endpoint blocked, public endpoint blocked, cloud runtime blocked, migration execution blocked, deployment blocked
  Open issues: toolchain proof, dependency proof, database proof, container proof, endpoint proof, migration rollback proof, and deployment evidence remain AwaitingEvidence
  Next action: run the runtime/environment boundary validator, then keep runtime readiness and deployment claims closed until evidence promotes them
