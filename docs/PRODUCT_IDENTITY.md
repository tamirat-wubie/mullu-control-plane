# Product Identity

Purpose: define the standard naming boundary for Mullu Govern as the public Mullusi product.
Governance scope: product naming, public positioning, repository boundary, deployment surface, and customer-facing surfaces.
Dependencies: `README.md`, `docs/00_platform_overview.md`, `docs/01_shared_invariants.md`, `docs/NAMING_MIGRATION_PLAN.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: Mullu Govern is the public product; Mullu is the suite/family; Mullusi is the company and ecosystem brand; Mullu Platform is a developer and architecture term; Mullu Control Plane is the internal/admin technical surface; internal substrates are not user-facing product names; public launch remains blocked until clearance gates close.

## Standard Names

| Name | Classification | Meaning | Use |
| --- | --- | --- | --- |
| Mullusi | Company and ecosystem brand | The owner, public ecosystem, governance authority, research publisher, and trust surface | Company site, research, billing, governance, audit, ecosystem |
| Mullu | Suite/family | The Mullusi product family containing Govern, Proof, Ledger, Inspect, Code, Desk, CLI, and Control Plane | Suite navigation, ecosystem maps, family-level docs |
| Mullu Govern | Public product | Governed symbolic execution for approvals, budgets, traces, audit, lineage, policy enforcement, skill boundaries, deployment controls, and proof-backed actions | Public website, onboarding, pricing, product UI, citations |
| Mullu Platform | Developer/platform term | The universal governed agentic framework beneath Mullu | SDKs, APIs, architecture docs, deployment docs |
| Mullu Proof | Evidence surface | Receipts, proof stamps, lineage packages, and compliance evidence | Audit, export, proof review, trust boundary |
| Mullu Ledger | Financial/audit surface | Budgets, spend limits, payment states, receipts, settlements, and financial compliance evidence | Budget and payment governance |
| Mullu Inspect | Product surface | Browser inspection and symbolic web understanding | Browser extension, inspection workflows |
| Mullu CLI | Product surface | Terminal-native governed execution | Local installation, developer and operator workflows |
| Mullu Code | Product surface | Repository and software-development execution | IDE, repo, review, and build workflows |
| Mullu Desk | Product surface | Computer-use and desktop-work execution | Local desktop and workspace operations |
| Mullu Control Plane | Admin surface | Governance, approvals, status, traces, budgets, lineage, and deployment controls | Enterprise admin, operations, audit, and release management |
| MAF Core | Internal substrate | Shared kernel and capability substrate inside Mullu Platform | Kernel docs, Rust crates, proof substrate |
| MCOI Runtime | Internal vertical runtime | Computer-operations runtime built on the substrate | Computer-control, browser, file, document, and workflow execution |

## Product Boundary

Mullu Govern is the public product by Mullusi. A user should be able to say:

```text
I use Mullu Govern.
Mullu is the suite family.
Mullusi is the company behind it.
```

Mullu Govern covers:

1. Governed symbolic workflows.
2. Approval-gated execution.
3. Budget and spend enforcement.
4. Trace, lineage, and audit preservation.
5. Deployment controls.
6. Skill and capability boundaries.
7. Proof-backed action closure.

## Naming Rules

1. Use `Mullu Govern` for the main public product.
2. Use `Mullu` for the suite/family.
3. Use `Mullu [Surface]` for customer-facing surfaces such as `Mullu Proof`, `Mullu Ledger`, `Mullu Inspect`, `Mullu CLI`, `Mullu Code`, and `Mullu Desk`.
4. Use `Mullu Control Plane` only for internal/admin, runtime, deployment, observability, and technical control surfaces.
5. Use `Mullu Platform` only for developer, SDK, API, deployment, and architecture contexts.
6. Use `Mullusi` for company, brand, governance authority, billing, research, audit, and public ecosystem references.
7. Use `MAF Core`, `MCOI Runtime`, `DMRS`, `SCCE`, `USCL`, `Mfidel`, `SCCML`, and related substrate names only for internal technical lineage.
8. Do not introduce generic product names such as `Mullusi Handler`, `Mullusi Work`, or `Mullusi Operator` unless a future surface has a narrower reason to carry that name.

## Public Positioning

Mullu Govern is governed symbolic execution for real work. It lets a person or
organization define goals, admit capabilities, route actions through approvals,
enforce budgets and policy, verify effects, preserve audit receipts, and promote
successful patterns into reusable operational memory.

Public anchor:

```text
Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.
```

The public promise is governed execution before action: explicit authority,
deterministic receipts, policy gates, rollback paths, and proof-backed closure.

## Surface Model

| Surface | Primary user | Required surface |
| --- | --- | --- |
| Mullu Govern | Individual, team, enterprise | Governed execution across approvals, budgets, traces, audit, policy, deployment controls, and proof-backed actions |
| Mullu Proof | Auditor, reviewer, operator | Receipts, lineage, proof stamps, compliance evidence, and trust exports |
| Mullu Ledger | Finance operator, admin | Budget, spend, payment, settlement, and financial audit control |
| Mullu Inspect | Individual, researcher, operator | Browser inspection, page structure, evidence capture, and symbolic web review |
| Mullu CLI | Developer, operator | Terminal-native governed execution with receipts and policy gates |
| Mullu Code | Developer, product builder | Repo work, code authoring, tests, review, and release support |
| Mullu Desk | Individual, operator | Computer-use workflows, documents, local apps, and workspace actions |
| Mullu Control Plane | Enterprise admin | Internal/admin tenant isolation, audit export, budgets, approvals, policy packs, and deployment witness |
| Mullu Platform Developer | Builder and integrator | SDKs, schemas, capability registry, sandbox, API gateway, and proof receipts |

## Domain Mapping

| Asset | Use |
| --- | --- |
| `mullusi.com` | Company site, research, governance, audit, papers |
| `mullu.ai` | Preferred suite/product domain if available |
| `mullu-govern.com`, `govern.mullusi.com`, or `mullusi.com/govern` | Mullu Govern public route candidates |
| `app.mullu.ai` or `mullu.mullusi.com` | Web app surface |
| `inspect.mullu.ai` | Mullu Inspect landing |
| `dashboard.mullusi.com` | Control Plane admin, governance, and audit |
| `docs.mullusi.com` | Research, SDK, and developer docs |
| `api.mullusi.com` | API gateway |

## Clearance Gates

Preliminary findings are recorded in `docs/NAME_CLEARANCE_PRELIMINARY.md`.

The product name is not legally cleared until these checks are complete:

1. Trademark search for `Mullu Govern` and `Mullu` in software, SaaS, developer-tooling, browser-extension, and enterprise-governance classes.
2. Domain availability check for `mullu.ai`, `mullu.app`, `mullu.dev`, and fallback domains.
3. Conflict review for unrelated existing public uses of `Mullu Govern`, `Mullu`, and close variants, including media, games, cultural references, and regional platforms.
4. First-reference rule for launch copy: `Mullu Govern, by Mullusi`.

## Resolution

The public product name is `Mullu Govern`.
`Mullu` remains the suite/family name.
`Mullu Platform` remains the developer and architecture name.
`Mullu Control Plane` remains the internal/admin technical surface.
`Mullusi` remains the company, ecosystem, governance, and research authority.
