# Product Identity

Purpose: define the standard naming boundary for Mullu as the flagship Mullusi product.
Governance scope: product naming, public positioning, repository boundary, deployment surface, and customer-facing surfaces.
Dependencies: `README.md`, `docs/00_platform_overview.md`, `docs/01_shared_invariants.md`, `docs/NAMING_MIGRATION_PLAN.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: Mullu is the flagship product; Mullusi is the company and ecosystem brand; Mullu Platform is a developer and architecture term; internal substrates are not user-facing product names; public launch remains blocked until clearance gates close.

## Standard Names

| Name | Classification | Meaning | Use |
| --- | --- | --- | --- |
| Mullusi | Company and ecosystem brand | The owner, public ecosystem, governance authority, research publisher, and trust surface | Company site, research, billing, governance, audit, ecosystem |
| Mullu | Flagship product | The symbolic intelligence users buy and use across personal, team, enterprise, and deployment work | Public website, onboarding, pricing, product UI, citations |
| Mullu Platform | Developer/platform term | The universal governed agentic framework beneath Mullu | SDKs, APIs, architecture docs, deployment docs |
| Mullu Inspect | Product surface | Browser inspection and symbolic web understanding | Browser extension, inspection workflows |
| Mullu CLI | Product surface | Terminal-native governed execution | Local installation, developer and operator workflows |
| Mullu Code | Product surface | Repository and software-development execution | IDE, repo, review, and build workflows |
| Mullu Desk | Product surface | Computer-use and desktop-work execution | Local desktop and workspace operations |
| Mullu Control Plane | Admin surface | Governance, approvals, status, traces, budgets, lineage, and deployment controls | Enterprise admin, operations, audit, and release management |
| MAF Core | Internal substrate | Shared kernel and capability substrate inside Mullu Platform | Kernel docs, Rust crates, proof substrate |
| MCOI Runtime | Internal vertical runtime | Computer-operations runtime built on the substrate | Computer-control, browser, file, document, and workflow execution |

## Product Boundary

Mullu is the flagship product by Mullusi. A user should be able to say:

```text
I use Mullu.
Mullu has surfaces.
Mullusi is the company behind it.
```

Mullu covers:

1. Personal governed work.
2. Team and company operations.
3. Enterprise deployment.
4. Governed connector execution.
5. Capability marketplace expansion.
6. Audit-backed production operation.
7. Research-citable symbolic execution.

## Naming Rules

1. Use `Mullu` for the main public product.
2. Use `Mullu [Surface]` for customer-facing surfaces such as `Mullu Inspect`, `Mullu CLI`, `Mullu Code`, and `Mullu Desk`.
3. Use `Mullu Platform` only for developer, SDK, API, deployment, and architecture contexts.
4. Use `Mullusi` for company, brand, governance authority, billing, research, audit, and public ecosystem references.
5. Use `MAF Core`, `MCOI Runtime`, `DMRS`, `SCCE`, `USCL`, `Mfidel`, `SCCML`, and related substrate names only for internal technical lineage.
6. Do not introduce generic product names such as `Mullusi Handler`, `Mullusi Work`, or `Mullusi Operator` unless a future surface has a narrower reason to carry that name.

## Public Positioning

Mullu is governed symbolic intelligence for real work. It lets a person or
organization define goals, admit capabilities, execute bounded work, verify
effects, preserve audit receipts, and promote successful patterns into reusable
operational memory.

Public anchor:

```text
Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.
```

The public promise is not loose automation. The public promise is governed work:
explicit authority, deterministic receipts, policy gates, rollback paths, and
proof-backed closure.

## Surface Model

| Surface | Primary user | Required surface |
| --- | --- | --- |
| Mullu | Individual, team, enterprise | Conversational governed work across files, research, workflows, deployment, and connectors |
| Mullu Inspect | Individual, researcher, operator | Browser inspection, page structure, evidence capture, and symbolic web review |
| Mullu CLI | Developer, operator | Terminal-native governed execution with receipts and policy gates |
| Mullu Code | Developer, product builder | Repo work, code authoring, tests, review, and release support |
| Mullu Desk | Individual, operator | Computer-use workflows, documents, local apps, and workspace actions |
| Mullu Control Plane | Enterprise admin | Tenant isolation, audit export, budgets, approvals, policy packs, and deployment witness |
| Mullu Platform Developer | Builder and integrator | SDKs, schemas, capability registry, sandbox, API gateway, and proof receipts |

## Domain Mapping

| Asset | Use |
| --- | --- |
| `mullusi.com` | Company site, research, governance, audit, papers |
| `mullu.ai` | Preferred product domain if available |
| `app.mullu.ai` or `mullu.mullusi.com` | Web app surface |
| `inspect.mullu.ai` | Mullu Inspect landing |
| `dashboard.mullusi.com` | Control Plane admin, governance, and audit |
| `docs.mullusi.com` | Research, SDK, and developer docs |
| `api.mullusi.com` | API gateway |

## Clearance Gates

Preliminary findings are recorded in `docs/NAME_CLEARANCE_PRELIMINARY.md`.

The product name is not legally cleared until these checks are complete:

1. Trademark search for `Mullu` in software, SaaS, developer-tooling, browser-extension, and enterprise-governance classes.
2. Domain availability check for `mullu.ai`, `mullu.app`, `mullu.dev`, and fallback domains.
3. Conflict review for unrelated existing public uses of `Mullu`, including media, games, cultural references, and regional platforms.
4. First-reference rule for launch copy: `Mullu, by Mullusi`.

## Resolution

The flagship product name is `Mullu`.
`Mullu Platform` remains the developer and architecture name.
`Mullusi` remains the company, ecosystem, governance, and research authority.
