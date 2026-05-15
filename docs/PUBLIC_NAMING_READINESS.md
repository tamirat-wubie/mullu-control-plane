# Public Naming Readiness

Purpose: define the release gate for exposing `Mullu` as the public product name.
Governance scope: brand clearance, domain ownership, website copy, SDK/API terminology, admin surfaces, and product launch evidence.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `docs/NAME_CLEARANCE_PRELIMINARY.md`, `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md`, `docs/NAMING_MIGRATION_PLAN.md`, `docs/TRADEMARK_SEARCH_RUNBOOK.md`, `docs/DOMAIN_ACQUISITION_PLAN.md`, `docs/WEBSITE_UPDATE_CHECKLIST.md`, `docs/WEBSITE_RECHECK_LOG.md`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md`, `docs/PUBLIC_NAMING_STATE_TRANSITION.md`, `docs/PUBLIC_NAMING_HANDOFF.md`, `docs/CLEARANCE_PACKET_TEMPLATE.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`, `docs/public-naming-readiness.json`.
Invariants: `Mullu` is the product name only after clearance; `Mullusi` remains the company and governance authority; `Mullu Platform` remains valid for developer contracts and architecture surfaces.

## Readiness Gates

| Gate | Requirement | Status |
| --- | --- | --- |
| Product identity | `Mullu` is documented as flagship product | Closed |
| Company boundary | `Mullusi` is documented as company, ecosystem, governance authority | Closed |
| Platform boundary | `Mullu Platform` is reserved for developer, SDK, API, deployment, and architecture contexts | Closed |
| Admin boundary | `Mullu Control Plane` is documented as admin/governance/deployment surface | Closed |
| Blocked generic names | `Mullusi Handler`, `Mullusi Work`, `Mullusi Operator`, and `Mullu AI` are blocked as public product names | Closed |
| Public copy | Launch-ready homepage copy exists | Closed |
| Product route draft | Deploy-ready `/mullu/index.html` product page exists and remains private beta | Closed |
| Product route deployment handoff | Product route deployed to the live website source repository and verified | Closed |
| Trademark runbook | Official search procedure exists | Closed |
| TSDR evidence template | Official USPTO close-variant serial capture template exists | Closed |
| Domain plan | Domain acquisition and routing plan exists | Closed |
| Website checklist | Public-site update checklist exists | Closed |
| Website deployment evidence template | Live-route verification template exists | Closed |
| Website deployment probe | Historical direct route failure evidence recorded from 2026-05-07 | Closed with blocker |
| Website deployment verification | `https://mullusi.com/mullu/` verified live with HTTP 200 private-beta product content | Closed |
| Website recheck log | Non-authoritative public index signal is recorded and superseded by direct live-route evidence | Closed |
| State transition rules | Launch-state mutation rules exist | Closed |
| Handoff summary | Reviewer-facing public naming handoff exists | Closed |
| PR summary | Review and release-note summary exists | Closed |
| Review packet | Final reviewer-facing clearance packet exists | Closed |
| Artifact manifest | Full naming package inventory exists | Closed |
| Clearance packet template | Evidence packet template exists | Closed |
| Domain ownership template | Domain-control record template exists | Closed |
| Draft clearance packet | Preliminary evidence packet exists | Closed |
| Machine-readable witness | JSON readiness witness exists | Closed |
| Readiness validator | Validator checks JSON witness and evidence docs | Closed |
| Readiness tests | Focused Python tests cover witness, failure modes, report output, and transition plan output | Closed |
| Readiness report | CLI report summarizes open launch blockers | Closed |
| Transition planner | CLI planner derives remaining launch-state actions | Closed |
| Naming schemas | JSON schemas exist for readiness witness and clearance draft | Closed |
| Official clearance access log | 2026-05-15 USPTO/TSDR and domain-access attempts are recorded without closing clearance gates | Closed |
| Preliminary web search | Obvious public conflicts recorded | Closed with review items |
| Close-variant review | `MULU` software/service-adjacent public records captured for official review | Open |
| USPTO search | Exact and similar marks checked | Open |
| WIPO search | Exact and similar marks checked | Open |
| EUIPO/TMview search | Exact and similar marks checked | Open |
| Domain ownership | Primary or fallback product domain acquired | Open |
| Legal review | Counsel or qualified trademark review completed | Open |
| Homepage update | Product landing page updated at `https://mullusi.com/mullu/` with private-beta copy | Closed |
| App title update | User-facing app title uses `Mullu` | Open |
| SDK/API stability review | Technical contracts intentionally keep `Mullu Platform` where required | Open |

## Keep Technical Contracts Stable

The following may remain `Mullu Platform` after public launch:

1. OpenAPI titles.
2. SDK generation manifests.
3. Schema package documentation.
4. Deployment and architecture docs.
5. Generated configuration headers.
6. Internal runtime metadata that identifies the platform layer.

Do not rename these unless a separate compatibility review confirms downstream
SDKs, tests, docs, and generated clients will not drift.

## Verification Commands

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_release_status.py
```

## Product-Facing Update Targets

After clearance closes, update:

1. Homepage hero.
2. Product pricing page.
3. Signup/onboarding flow.
4. Browser extension listing.
5. CLI install page.
6. Public docs landing page.
7. Product screenshots.
8. Footer first-reference copy: `Mullu, by Mullusi`.

## Product Route Draft

The deploy-ready static product route is:

```text
site/mullu/index.html
```

It has been deployed as `/mullu/index.html` in the public GitHub Pages source
repository as private beta / request-access copy, not a paid public launch page.

The current deployment handoff target is:

```text
../mullusi_website/mullu/index.html
```

The live route is verified in:

```text
docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md
```

## Launch Decision

`Mullu` is approved for internal alignment and product planning.

`Mullu` is not approved for paid public launch until all open clearance gates
close.
