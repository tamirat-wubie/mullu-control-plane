# Product Boundary

Purpose: bind this repository to the Mullu Govern product naming system.
Governance scope: control-plane proprietary wording, admin surface identity, developer metadata, Foundation Mode, and launch-readiness constraints.
Dependencies: `README.md`, `docs/FOUNDATION_MODE.md`, `docs/00_platform_overview.md`.
Invariants: Foundation Mode is the current operating posture until promoted by witness; Mullu Govern is the public product; Mullu is the suite/family; Mullusi is the company and ecosystem brand; Mullu Control Plane is the admin/governance/deployment surface; Mullu Platform remains valid for SDK, API, schema, and architecture contexts.

## Boundary

Ownership: Mullu Govern is a proprietary invention of Tamirat Wubie, governed
for use under the Mullusi company boundary. Product naming, repository metadata,
package metadata, and launch copy must not imply free public use.

| Name | Use in this repository |
| --- | --- |
| Mullu Govern | Public governed-execution product name |
| Mullu | Proprietary Mullusi suite/family name |
| Mullusi | Company, governance authority, billing, research, and trust context |
| Mullu Control Plane | This repository's primary admin/governance/deployment surface |
| Mullu Platform | Developer, SDK, API, schema, deployment, and architecture context |
| MAF Core | Internal substrate |
| MCOI Runtime | Internal computer-operations runtime |

## Company Description

```text
Mullu Govern is the governed execution product by Mullusi for symbolic
workflows, approvals, budgets, audit trails, lineage, deployment controls, and
proof-backed actions.
```

```text
Mullu Control Plane is the internal/admin technical surface that provides
gateway, approvals, status, traces, budgets, lineage, and deployment controls.
```

## Allowed Existing Technical Uses

The following phrases may remain when the context is technical or historical:

1. `Mullu Platform`
2. `Mullu Platform Configuration`
3. `Mullu Platform MCOI Runtime`
4. `Mullu Platform` in historical release notes
5. `Mullu Platform` in OpenAPI titles and schema names
6. `Mullu Control Plane` for admin, runtime, deployment, observability, and repository-local technical surfaces

## Repository Rename Target

The public repository name target is:

```text
mullu-govern
```

The current `mullu-control-plane` repository and local directory may remain
until a separate migration updates remotes, deployment references, CI secrets,
and release evidence paths.

This rename target is not a repository-split trigger. During Foundation Mode,
the intended posture remains one repository for the current platform runtime.
Any later split into web, API, core, SDK, or docs repositories requires signed
deployment witness evidence, public runtime evidence, first-user evidence, and
real coordination pressure. Until those gates close, users should see the
product as `Mullu Govern`, operators should treat the company boundary as
`Mullusi`, and developers should continue working in `mullu-control-plane`.

## Blocked Public Names

Do not introduce these as product names:

1. `Mullusi Handler`
2. `Mullusi Work`
3. `Mullusi Operator`
4. `Mullu Generic`

## Launch Constraint

External paid-user launch under `Mullu Govern` remains blocked until Foundation
Mode promotion, local proof-thread evidence, trademark, domain, legal
clearance, deployment witness, and public-health evidence close in the product
identity package.

## Foundation Scope Constraint

Foundation Mode product scope is bounded by
[`FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md`](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md).
The selected local learning lane is a proof lane only. It does not restrict the
long-term Mullu Govern platform, and it does not authorize pilot access,
customer access, market validation, paid launch, or deployment-readiness claims.

Foundation Mode operator readiness is bounded by
[`FOUNDATION_OPERATOR_READINESS_BOUNDARY.md`](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md).
Operator-readiness planning may be drafted locally, but it does not claim
capacity, schedule, skill, team readiness, hiring readiness, delegation
readiness, support coverage, incident coverage, legal authority, financial
authority, or support deployment-readiness claims.

Foundation Mode learning path is bounded by
[`FOUNDATION_LEARNING_PATH_BOUNDARY.md`](FOUNDATION_LEARNING_PATH_BOUNDARY.md).
Learning-path planning may be drafted locally, but it does not claim skill
readiness, training completion, certification, paid-course activation, mentor
assignment, hiring readiness, delegation readiness, public tutorial
publication, curriculum completion, production-operation readiness,
customer-support readiness, external account use, or deployment-readiness
claims.

Foundation Mode architecture mapping is bounded by
[`FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md`](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md).
Architecture-map planning may be drafted locally, but it does not claim
architecture completeness, module inventory completeness, interface contract
readiness, dependency graph readiness, invariant closure, hazard closure,
proof coverage closure, integration readiness, runtime readiness, refactor
approval, implementation approval, external publication, or deployment
readiness claims.

Foundation Mode system-boundary inventory is bounded by
[`FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md`](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md).
System-boundary inventory planning may be drafted locally, but it does not
claim inventory completeness, ownership closure, trust closure, tenant
readiness, data classification closure, endpoint readiness, service binding,
integration readiness, runtime readiness, exposure approval, implementation
approval, external publication, or deployment readiness claims.

Foundation Mode module inventory is bounded by
[`FOUNDATION_MODULE_INVENTORY_BOUNDARY.md`](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md).
Module-inventory planning may be drafted locally, but it does not claim module
inventory completeness, ownership assignment, contract readiness, interface
readiness, dependency readiness, integration readiness, runtime readiness,
refactor approval, implementation approval, external publication, or
deployment readiness claims.

Foundation Mode component contracts are bounded by
[`FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md`](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md).
Component-contract planning may be drafted locally, but it does not claim
component contract readiness, input readiness, output readiness, error
readiness, evidence readiness, state readiness, dependency readiness, owner
approval, test pass, refactor approval, implementation approval, external
publication, or deployment readiness claims.

Foundation Mode interface maps are bounded by
[`FOUNDATION_INTERFACE_MAP_BOUNDARY.md`](FOUNDATION_INTERFACE_MAP_BOUNDARY.md).
Interface-map planning may be drafted locally, but it does not claim
interface-map completeness, interface contract readiness, endpoint readiness,
service binding, event/message readiness, data-flow readiness, trust closure,
integration readiness, runtime readiness, owner approval, test pass, refactor
approval, implementation approval, external publication, or deployment
readiness claims.

Foundation Mode dependency graphs are bounded by
[`FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md`](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md).
Dependency-graph planning may be drafted locally, but it does not claim
dependency-graph completeness, dependency contract readiness, import readiness,
package install approval, version-lock readiness, service dependency binding,
provider binding, vulnerability scan pass, runtime dependency readiness, owner
approval, test pass, refactor approval, implementation approval, external
publication, or deployment readiness claims.

Foundation Mode invariant maps are bounded by
[`FOUNDATION_INVARIANT_MAP_BOUNDARY.md`](FOUNDATION_INVARIANT_MAP_BOUNDARY.md).
Invariant-map planning may be drafted locally, but it does not claim
invariant-map completeness, invariant proof readiness, invariant enforcement
readiness, invariant conflict resolution, invariant monitor readiness, runtime
invariant readiness, owner approval, test pass, refactor approval,
implementation approval, external publication, or deployment readiness claims.

Foundation Mode hazard maps are bounded by
[`FOUNDATION_HAZARD_MAP_BOUNDARY.md`](FOUNDATION_HAZARD_MAP_BOUNDARY.md).
Hazard-map planning may be drafted locally, but it does not claim hazard-map
completeness, hazard classification readiness, hazard severity closure,
mitigation readiness, safety review readiness, runtime hazard readiness, owner
approval, test pass, refactor approval, implementation approval, external
publication, or deployment readiness claims.

Foundation Mode proof references are bounded by
[`FOUNDATION_PROOF_REFERENCE_BOUNDARY.md`](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md).
Proof-reference planning may be drafted locally, but it does not claim
proof-reference completeness, proof coverage closure, evidence promotion,
terminal closure, verification pass, proof approval, runtime proof readiness,
owner approval, test pass, refactor approval, implementation approval,
external publication, or deployment readiness claims.

Foundation Mode gap registers are bounded by
[`FOUNDATION_GAP_REGISTER_BOUNDARY.md`](FOUNDATION_GAP_REGISTER_BOUNDARY.md).
Gap-register planning may be drafted locally, but it does not claim
gap-register completeness, gap closure, priority closure, owner assignment,
remediation readiness, roadmap commitment, evidence promotion, terminal
closure, test pass, refactor approval, implementation approval, external
publication, or deployment readiness claims.

Foundation Mode diff review is bounded by
[`FOUNDATION_DIFF_REVIEW_BOUNDARY.md`](FOUNDATION_DIFF_REVIEW_BOUNDARY.md).
Diff-review planning may be drafted locally, but it does not claim
diff-review completeness, diff scope closure, ownership assignment, staging
approval, commit approval, branch switch approval, push approval, pull request
approval, release readiness, revert approval, test pass, source-control
publication, external publication, or deployment readiness claims.

Foundation Mode change handoff is bounded by
[`FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md`](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md).
Change-handoff planning may be drafted locally, but it does not claim
change-handoff completeness, changed-file review completeness, diff scope
closure, ownership assignment, validation completeness, secret clearance,
staging approval, commit approval, branch switch approval, push approval, pull
request approval, release readiness, revert approval, source-control
publication, external publication, or deployment readiness claims.

Foundation Mode local workstation posture is bounded by
[`FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md`](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md).
Local-workstation planning may be drafted locally, but it does not verify the
workstation, verify toolchains, install dependencies, mutate environment files,
start services, claim full-test pass, depend on cloud, record private paths, or
support deployment-readiness claims.

Foundation Mode documentation posture is bounded by
[`FOUNDATION_DOCUMENTATION_BOUNDARY.md`](FOUNDATION_DOCUMENTATION_BOUNDARY.md).
Documentation planning may be drafted locally, but it does not claim
documentation completeness, canonical docs, public-launch copy, customer
readiness, deployment readiness, legal clearance, commercial readiness,
external publication, or support deployment-readiness claims.

Foundation Mode claim posture is bounded by
[`FOUNDATION_CLAIM_BOUNDARY.md`](FOUNDATION_CLAIM_BOUNDARY.md).
Claim-boundary planning may be drafted locally, but it does not claim
production health, endpoint readiness, customer readiness, pilot readiness,
legal clearance, commercial readiness, public launch, compliance certification,
external publication, or support deployment-readiness claims.

Foundation Mode website posture is bounded by
[`FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md`](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md).
Website-posture planning may be drafted locally, but it does not mutate website
files, publish routes, invite access, open waitlists, open beta, accept pilot
signups, collect customer intake, claim production runtime, claim endpoint
readiness, launch paid use, or support deployment-readiness claims.

Foundation Mode research-notebook posture is bounded by
[`FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md`](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md).
Research-notebook planning may be drafted locally, but it does not claim patent
protection, trade-secret protection, scientific validation, physical-world
validation, market validation, customer readiness, external publication, paid
launch, secret evidence, or support deployment-readiness claims.

Foundation Mode evidence-ledger posture is bounded by
[`FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md`](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md).
Evidence-ledger planning may be drafted locally, but it does not promote
evidence, claim terminal closure, claim readiness, claim legal clearance, claim
patent protection, claim customer readiness, launch paid use, record secret
evidence, publish externally, or support deployment-readiness claims.

Foundation Mode decision-journal posture is bounded by
[`FOUNDATION_DECISION_JOURNAL_BOUNDARY.md`](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md).
Decision-journal planning may be drafted locally, but it does not execute
decisions, authorize irreversible action, commit to a roadmap, promise
deadlines, delegate authority, make customer commitments, claim legal
authority, authorize company action, file patents, authorize spending, publish
externally, or support deployment-readiness claims.

Foundation Mode next-action posture is bounded by
[`FOUNDATION_NEXT_ACTION_BOUNDARY.md`](FOUNDATION_NEXT_ACTION_BOUNDARY.md).
Next-action planning may be drafted locally, but it does not authorize broad
continuation, external action, deployment, publication, spending, customer
action, legal/business action, claim promotion, secret use, credential use,
service activation, source-control publication, roadmap commitment, or deadline
promise.

Foundation Mode secrets and credentials are bounded by
[`FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md).
Secrets/credentials planning may be drafted locally, but it does not store real
secrets, activate credentials, bind provider accounts, enable external calls,
commit environment files, or support deployment-readiness claims.

Foundation Mode security baseline posture is bounded by
[`FOUNDATION_SECURITY_BASELINE_BOUNDARY.md`](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md).
Security-baseline planning may be drafted locally, but it does not claim scan
pass, dependency audit pass, threat-model approval, access-control
verification, compliance certification, customer-security readiness, or support
deployment-readiness claims.

Foundation Mode cost and budget posture is bounded by
[`FOUNDATION_COST_BUDGET_BOUNDARY.md`](FOUNDATION_COST_BUDGET_BOUNDARY.md).
Cost/budget planning may be drafted locally, but it does not authorize
spending, paid infrastructure, provider billing, payment-method binding,
subscription creation, purchase approval, invoice payment, vendor commitment, or
deployment-readiness claims.

Foundation Mode runtime and environment posture is bounded by
[`FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md).
Runtime/environment planning may be drafted locally, but it does not verify
runtime readiness, activate databases, start containers, open endpoints, run
migrations, connect cloud runtimes, or support deployment-readiness claims.

Foundation Mode backup and export posture is bounded by
[`FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md).
Backup/export planning may be drafted locally, but it does not run backups,
activate cloud sync, export files, publish archives, delete data, record
private paths, move secrets, move personal data, claim restore readiness, or
support deployment-readiness claims.

Foundation Mode deployment deferral is bounded by
[`FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md`](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md).
Deployment prerequisite questions may be drafted locally, but they do not
approve deployment plans, activate cloud resources, open public endpoints, claim
production health, claim runtime readiness, open customer access, authorize
spending, authorize credential or secret use, execute migrations, mutate DNS,
publish externally, or support deployment-readiness claims.

Foundation Mode external infrastructure is bounded by
[`FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md`](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md).
External-infrastructure questions may be drafted locally, but they do not
claim external-infrastructure completeness, verify DNS authority, bind DNS
targets, mutate DNS, provision runtime hosts, provision databases, verify
secret placement, claim endpoint reachability, bind repository variables,
dispatch workflows, activate paid infrastructure, open customer access, publish
externally, or support deployment-readiness claims.

Foundation Mode pilot deferral is bounded by
[`FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md`](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md).
Pilot prerequisite questions may be drafted locally, but they do not execute
pilots, invite participants, open access channels, open waitlists, open beta,
collect personal data, claim market validation, promise support, claim legal
clearance, authorize paid pilots, publish externally, or support deployment
claims.

Foundation Mode support readiness is bounded by
[`FOUNDATION_SUPPORT_READINESS_BOUNDARY.md`](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md).
Support planning may be drafted locally, but it does not open customer support,
support SLA, onboarding, paid support, incident-response readiness, or
deployment-readiness claims.

Foundation Mode intake and onboarding are bounded by
[`FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md`](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md).
Intake planning may be drafted locally, but it does not publish forms, open
waitlists, accept pilot signups, collect personal data, import CRM records,
start outreach, onboard customers, enable paid access, or support deployment
claims.

Foundation Mode privacy and data retention are bounded by
[`FOUNDATION_PRIVACY_DATA_BOUNDARY.md`](FOUNDATION_PRIVACY_DATA_BOUNDARY.md).
Privacy/data planning may be drafted locally, but it does not collect or store
personal data, publish privacy notices, capture consent, enable tracking,
activate processors, claim legal clearance, open customer access, or support
deployment claims.
