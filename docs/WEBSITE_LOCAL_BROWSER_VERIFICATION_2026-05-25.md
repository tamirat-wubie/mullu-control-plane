# Website Local Browser Verification 2026-05-25

Purpose: record repo-local browser verification for the Mullu Govern static site copy after the public naming boundary update.
Governance scope: local visual/layout verification, product/suite/admin label separation, route-link checks, and non-launch evidence handling.
Dependencies: `site/mullu/index.html`, `site/proof/index.html`, `docs/PRODUCT_BOUNDARY.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/public-naming-readiness.json`.
Invariants: local browser verification does not close live deployment, domain ownership, trademark, close-variant, or legal gates; paid public launch remains blocked.

## Verification Context

| Field | Value |
| --- | --- |
| Date | 2026-05-25 |
| Local route root | `http://127.0.0.1:8765/` |
| Static source | `site/` |
| Product route checked | `http://127.0.0.1:8765/mullu/` |
| Proof route checked | `http://127.0.0.1:8765/proof/?v=mobile-table-fix-label` and cache-busted wide checks |
| Browser surface | Codex in-app browser |
| Evidence class | Local pre-deployment browser evidence only |

## Observed Route Results

| Route | Viewport | Expected boundary | Result |
| --- | --- | --- | --- |
| `/mullu/` | current browser viewport | Nav uses `Surfaces`; page title uses `Mullu Govern, by Mullusi`; request email subject uses `Mullu Govern private beta access` | Pass |
| `/mullu/` | mobile `390 x 844` | `Suite surfaces` separates public products, operator surfaces, internal/admin surface, and substrates | Pass |
| `/mullu/` | wide `1280 x 720` | No horizontal overflow; `Mullu Control Plane` remains internal/admin | Pass |
| `/proof/` | mobile `390 x 844` | Proof nav links to `Mullu Govern`; status table does not overflow | Pass |
| `/proof/` | wide `1280 x 720` | Proof page retains `Mullu Govern` product boundary and no horizontal overflow | Pass |

## Browser Findings

The unversioned `/mullu/` route initially showed cached pre-patch labels in the in-app browser. A normal reload refreshed the exact URL and confirmed the current file is served with:

1. `Surfaces` in the top navigation.
2. `Suite surfaces` in the structure map.
3. `Public products: Mullu Govern, Mullu Proof, Mullu Ledger`.
4. `Internal/admin: Mullu Control Plane`.
5. `mailto:hello@mullusi.com?subject=Mullu%20Govern%20private%20beta%20access`.

This cache behavior is local browser state only. The local HTTP response for `/mullu/` contained the updated strings directly.

## Local Screenshot Artifacts

These artifacts are local verification aids under `.tmp/` and are not launch evidence:

| Artifact | Purpose |
| --- | --- |
| `.tmp/mullu-govern-site-mobile-surface-boundary.png` | Mobile product route check |
| `.tmp/mullu-proof-site-mobile-label.png` | Mobile proof route label and overflow check |
| `.tmp/mullu-proof-site-wide-surface-boundary.png` | Wide proof route check |

## Validation Commands

```powershell
python scripts\validate_public_naming_readiness.py
python -m pytest tests\test_public_naming_readiness.py tests\test_validate_public_repository_surface.py tests\test_validate_release_status.py -q
python scripts\validate_release_status.py
git diff --check
```

## Gate Interpretation

This evidence supports internal alignment and local route QA only. It does not satisfy:

1. official USPTO evidence,
2. official WIPO evidence,
3. official EUIPO/TMview evidence,
4. close-variant legal confusion analysis,
5. domain ownership evidence,
6. final legal review.

STATUS:
  Completeness: 100%
  Invariants verified: [Mullu Govern public product label, Mullu suite/family boundary, Mullu Control Plane internal/admin boundary, local mobile layout bounded, local wide layout bounded, paid public launch remains blocked]
  Open issues: [official trademark searches, close-variant review, domain ownership evidence, legal review]
  Next action: attach official external clearance and domain evidence before changing public launch state
