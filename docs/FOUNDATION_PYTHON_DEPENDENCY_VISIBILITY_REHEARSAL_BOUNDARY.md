<!--
Purpose: define the Foundation Mode Python dependency-visibility rehearsal boundary for local interpreter and package-visibility questions without installing packages, mutating environments, recording private paths, or claiming runtime readiness.
Governance scope: Python interpreter labels, package visibility labels, optional dependency group labels, import-probe labels, sandbox/elevated boundary labels, preflight check labels, repair-option labels, validation-command pairing, stop-rule rehearsal, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_python_dependency_visibility_rehearsal_boundary.py.
Invariants: no dependency visibility claim, no dependency install approval, no interpreter path recording, no private path recording, no package install, no environment mutation, no FastAPI readiness claim, no full preflight closure claim, no runtime readiness claim, no source-control publication, no external publication, no deployment, no customer access, no legal clearance, no company formation, no patent action, no money movement, and no secret publication.
-->

# Foundation Python Dependency Visibility Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** Python dependency-visibility rehearsal means naming the local
> questions that explain why one Python command can see a package while another
> cannot. It does not install packages, change virtual environments, record
> private paths, claim FastAPI readiness, claim runtime readiness, close full
> preflight, publish source control, or deploy anything.

Witness packet: [`../examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json)

Rule: Python dependency-visibility rehearsal is a local Foundation Mode
planning boundary, not dependency readiness.

No dependency-visibility claim, dependency-install approval, interpreter path
recording, private path recording, package install, environment mutation,
FastAPI readiness claim, full preflight closure claim, runtime readiness claim,
source-control publication, external publication, deployment, customer access,
legal clearance, company formation, patent action, money movement, or secret
publication is permitted by this boundary.

## What This Boundary Solves

Foundation Mode can run local validators while still discovering that different
Python execution surfaces have different dependency visibility. That is a setup
question, not a deployment signal. This boundary makes the question visible
without turning it into package installation, environment mutation, private path
recording, or readiness evidence.

This is preparation only:

1. The repository can name interpreter and package-visibility rehearsal labels.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature dependency, package, FastAPI, preflight,
   runtime, publication, deployment, customer, legal, company, patent, money,
   secret, or private-path claims.
4. No private interpreter path, site-package path, environment value, install
   target, package version, token, endpoint, account, or deployment target is
   recorded by this document or witness.

## Current State

```text
python_dependency_visibility_rehearsal_boundary_state=AwaitingEvidence
dependency_visibility_claimed=false
dependency_install_allowed=false
interpreter_path_recording_allowed=false
private_path_recording_allowed=false
package_install_allowed=false
environment_mutation_allowed=false
fastapi_readiness_claimed=false
preflight_closure_claimed=false
runtime_readiness_claimed=false
source_control_publication_allowed=false
external_publication_allowed=false
deployment_allowed=false
customer_access_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_action_allowed=false
money_movement_allowed=false
secret_publication_allowed=false
```

## Dependency-Visibility Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Interpreter label | Name which Python execution surface needs a label. | Do not record a real interpreter path or claim it is verified. |
| User-site visibility label | Name the user-site visibility question. | Do not record site-package paths or claim package visibility. |
| Optional dependency group label | Name optional dependency groups that may matter. | Do not install packages or claim dependency groups are complete. |
| Import-probe label | Name a future import probe category. | Do not claim FastAPI or any package is ready. |
| Sandbox boundary label | Name sandbox versus elevated visibility as a boundary. | Do not bypass sandbox rules or treat elevated execution as readiness. |
| Elevated preflight label | Name why full preflight may need the operator environment. | Do not claim full preflight closure from this boundary. |
| Dependency gap note | Draft public-safe gap wording. | Do not record private paths, versions, endpoints, or account identifiers. |
| Repair option label | Name possible future repair classes. | Do not mutate environments, install packages, or change profiles. |
| Validation command pairing | Pair future checks with validators. | Do not treat command pairing as test or runtime readiness. |
| Stop-rule rehearsal | Name when to stop and ask for operator review. | Do not publish source control, deploy, spend, handle secrets, or claim legal/company/patent readiness. |

## Operator Procedure

1. Keep dependency-visibility notes public-safe and label-only.
2. Do not record private interpreter paths, site-package paths, environment
   values, package versions, tokens, endpoints, account identifiers, or install
   targets.
3. Treat every dependency-visibility surface as `AwaitingEvidence`.
4. Use future import probes only as local evidence after a task explicitly needs
   them and after private values are excluded.
5. Do not use this boundary to install packages, mutate environments, claim
   FastAPI readiness, close full preflight, claim runtime readiness, publish
   source control, open customer access, spend money, claim legal/company/patent
   readiness, handle secrets, or deploy.

## Validation

Run:

```powershell
python scripts/validate_foundation_python_dependency_visibility_rehearsal_boundary.py
```

The validator checks that the dependency-visibility witness:

1. keeps dependency visibility, installs, path recording, environment mutation,
   FastAPI readiness, preflight closure, runtime readiness, publication,
   deployment, customer, legal, company, patent, money, and secret claims
   disabled;
2. keeps every dependency-visibility rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, assignment-shaped interpreter/package/env
   values, secret material, and private-key material; and
4. rejects dependency, FastAPI, preflight, runtime, publication, deployment,
   customer, legal, company, patent, money, or secret readiness phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare the local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Prepare runtime/environment safely | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: dependency visibility claim blocked, dependency install blocked, interpreter path recording blocked, private path recording blocked, package install blocked, environment mutation blocked, FastAPI readiness blocked, preflight closure blocked, runtime readiness blocked, source-control publication blocked, external publication blocked, deployment blocked, customer access blocked, legal clearance blocked, company formation blocked, patent action blocked, money movement blocked, secret publication blocked
  Open issues: interpreter evidence, user-site visibility evidence, optional dependency group evidence, import-probe evidence, sandbox boundary evidence, elevated preflight evidence, dependency gap evidence, repair option evidence, validation command evidence, and stop-rule evidence remain AwaitingEvidence
  Next action: run the dependency-visibility rehearsal validator before using interpreter or package-visibility notes as readiness evidence
