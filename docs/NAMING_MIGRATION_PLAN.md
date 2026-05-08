# Naming Migration Plan

Purpose: define the controlled migration from platform-first naming to `Mullu` flagship product naming.
Governance scope: product docs, developer docs, runtime metadata, public copy, release notes, tests, and future surfaces.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/NAME_CLEARANCE_PRELIMINARY.md`, `docs/PUBLIC_LAUNCH_COPY.md`.
Invariants: do not rename internal substrates; do not rewrite historical release evidence unless the name is actively user-facing; keep `Mullu Platform` where the context is developer, SDK, API, deployment, or architecture.

## Migration Rule

| Context | Name to use | Action |
| --- | --- | --- |
| Public product, pricing, signup, onboarding, homepage | Mullu | Rename from platform-first wording |
| First public mention | Mullu, by Mullusi | Use once per surface |
| Developer docs, SDKs, schemas, deployment architecture | Mullu Platform | Keep |
| Browser surface | Mullu Inspect | Keep or promote |
| Terminal surface | Mullu CLI | Keep or promote |
| Future coding surface | Mullu Code | Reserve |
| Future desktop/computer-use surface | Mullu Desk | Reserve |
| Admin, approval, trace, budget, tenant, deployment surface | Mullu Control Plane | Keep |
| MAF, MCOI, DMRS, SCCE, USCL, Mfidel, SCCML | Existing internal names | Keep |
| Historical release notes | Existing historical title | Keep unless republished as public marketing |

## Current Findings

The remaining `Mullu Platform` references in active docs and code are mostly
developer, schema, deployment, architecture, or runtime metadata contexts. These
are allowed by `docs/PRODUCT_IDENTITY.md`.

The stale names `Mullusi Handler`, `Mullusi Work`, and `Mullusi Operator` should
not appear as active product names. They may appear only inside a rule that says
not to introduce them.

## Product Copy Rule

Use this launch pattern:

```text
Mullu, by Mullusi
Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.
```

Then use `Mullu` alone after the first reference.

## Runtime Metadata Rule

Runtime metadata may keep `Mullu Platform` when it identifies an API, schema,
developer framework, or deployment surface. User-facing app titles should use
`Mullu` unless the screen is specifically an admin/developer platform surface.

## Do Not Rename

1. `MAF Core`
2. `MCOI Runtime`
3. `Mullu Control Plane`
4. `DMRS`
5. `SCCE`
6. `USCL`
7. `Mfidel`
8. `SCCML`
9. Historical release-note titles that preserve repository evidence

## Required Follow-Up

1. Complete official name clearance.
2. Lock product domain or fallback path.
3. Update public website copy.
4. Update product screenshots and UI titles.
5. Update package metadata only where it becomes public-facing.
6. Keep architecture docs stable unless a section is clearly marketing-facing.
