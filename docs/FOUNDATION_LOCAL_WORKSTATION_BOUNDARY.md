<!--
Purpose: define the Foundation Mode local-workstation boundary before any machine, toolchain, dependency-install, or full-test readiness claim.
Governance scope: local workstation planning, command inventory questions, toolchain questions, shell/profile questions, dependency-install questions, test-command questions, environment-variable questions, permission-boundary questions, local receipt questions, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_local_workstation_witness.awaiting_evidence.json, scripts/validate_foundation_local_workstation_boundary.py.
Invariants: no local workstation verification claim, no Python toolchain verification claim, no Node toolchain verification claim, no Rust toolchain verification claim, no dependency-install authorization, no environment mutation, no privileged command, no service start, no full-test-suite pass claim, no cloud dependency, no private path recording, and no deployment claim.
-->

# Foundation Local Workstation Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** local-workstation preparation means listing the local command,
> toolchain, shell, dependency, test, environment, permission, and receipt
> questions needed before repeatable setup can be trusted. It does not verify
> the machine, install dependencies, mutate the environment, start services,
> claim all tests pass, depend on cloud, record private paths, or deploy
> anything.

Witness packet: [`../examples/foundation_local_workstation_witness.awaiting_evidence.json`](../examples/foundation_local_workstation_witness.awaiting_evidence.json)

Rule: Local-workstation preparation is a local planning boundary, not
permission to claim workstation repeatability.

No local workstation verification, Python toolchain verification, Node
toolchain verification, Rust toolchain verification, dependency-install
authorization, environment mutation, privileged command, service start,
full-test-suite pass claim, cloud dependency, private path recording, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode should not depend on paid cloud to prove basics, but it also
should not overstate what the current machine proves. A local workstation can
run validators and focused tests while still lacking a complete repeatability
record. This boundary keeps those two facts separate.

This is preparation only:

1. The repository can name local workstation surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature machine, install, full-test, service, cloud,
   or deployment claims.
4. No private path, shell profile, environment value, package install, privileged
   command, service start, cloud dependency, or deployment is created by this
   document or validator.

## Current State

```text
local_workstation_boundary_state=AwaitingEvidence
local_workstation_verified=false
python_toolchain_verified=false
node_toolchain_verified=false
rust_toolchain_verified=false
dependency_install_allowed=false
environment_mutation_allowed=false
privileged_command_allowed=false
service_start_allowed=false
full_test_suite_pass_claimed=false
cloud_dependency_allowed=false
private_path_recording_allowed=false
deployment_allowed=false
```

## Local-Workstation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Local command inventory | Draft command categories that matter. | Do not claim the workstation is verified. |
| Toolchain version questions | Draft Python, Node, Rust, and package-manager questions. | Do not record private install paths or claim toolchain verification. |
| Shell profile questions | Draft shell/profile risk questions. | Do not mutate shell profiles or environment files. |
| Dependency-install questions | Draft install and lockfile questions. | Do not install dependencies from this boundary. |
| Test-command questions | Draft focused and full-test questions. | Do not claim the full test suite passed. |
| Environment-variable questions | Draft variable-name categories only. | Do not record real values or secrets. |
| Permission-boundary questions | Draft local permission and admin-rights questions. | Do not run privileged commands. |
| Local receipt questions | Draft how local evidence should be kept. | Do not publish evidence or imply deployment readiness. |

## Operator Procedure

1. Keep command, toolchain, shell, dependency, and environment notes public-safe.
2. Do not record private paths, private machine details, shell-profile contents,
   environment values, tokens, install targets, or account identifiers in Git.
3. Treat every local-workstation surface as `AwaitingEvidence`.
4. Run only bounded validators and focused tests that the current task requires.
5. Do not use this boundary to claim a repeatable workstation, a complete local
   setup, a full-test pass, service readiness, cloud readiness, or deployment
   readiness.

## Validation

Run:

```powershell
python scripts/validate_foundation_local_workstation_boundary.py
```

The validator checks that the local-workstation witness:

1. keeps workstation verification, toolchain verification, dependency install,
   environment mutation, privileged commands, service start, full-test-suite
   pass, cloud dependency, private path recording, and deployment disabled;
2. keeps every surface in `AwaitingEvidence`;
3. rejects URL, email, private path, environment assignment, toolchain target,
   install target, shell profile target, command target, service target, or
   cloud target shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare runtime/environment safely | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: local workstation verification blocked, toolchain verification blocked, dependency install blocked, environment mutation blocked, privileged command blocked, service start blocked, full-test-suite pass claim blocked, cloud dependency blocked, private path recording blocked, deployment blocked
  Open issues: command inventory evidence, toolchain evidence, shell/profile evidence, dependency-install evidence, full-test evidence, environment-variable evidence, permission evidence, and local receipt evidence remain AwaitingEvidence
  Next action: run the local-workstation boundary validator before any future workstation-repeatability claim
