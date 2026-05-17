# Domain Ownership Evidence

Purpose: store registrar, DNS, HTTPS, renewal, MFA, and lock evidence for the selected Mullu public route.
Governance scope: domain control, renewal control, DNS authority, HTTPS readiness, and launch route boundary.
Dependencies: `docs/DOMAIN_ACQUISITION_PLAN.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`, `docs/CLEARANCE_EVIDENCE_CAPTURE_PLAN_2026-05-15.md`.
Invariants: no domain ownership gate is closed by this placeholder; official registrar or DNS-zone evidence is required.

## Required Evidence

| Evidence item | Status |
| --- | --- |
| Registrar account ownership | Pending capture |
| Registered owner or organization account | Pending capture |
| Renewal owner and renewal date | Pending capture |
| Auto-renew status | Pending capture |
| Registrar lock status | Pending capture |
| MFA status | Pending capture |
| DNS provider and zone control | Pending capture |
| HTTPS certificate status | Pending capture |
| DNSSEC/HSTS status if enabled | Pending capture |
| TXT ownership verification if available | Pending capture |

## Required Files

1. Registrar screenshots or exports.
2. DNS zone screenshots or exports.
3. HTTPS certificate evidence.
4. `decision.md` with selected route, owner, and launch impact.

STATUS:
  Completeness: 20%
  Invariants verified: [domain evidence scope declared, ownership controls declared, gate remains pending]
  Open issues: [registrar evidence, DNS evidence, HTTPS evidence, owner decision]
  Next action: capture domain ownership records and update `decision.md`
