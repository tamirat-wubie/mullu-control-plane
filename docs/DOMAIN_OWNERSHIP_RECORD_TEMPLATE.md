# Domain Ownership Record Template

Purpose: record registrar and DNS ownership evidence for Mullu Govern product domains and Mullu suite domains.
Governance scope: domain control, renewal ownership, DNS routing, security controls, and launch readiness.
Dependencies: `docs/DOMAIN_ACQUISITION_PLAN.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: a domain is not launch-ready until registrar ownership, DNS control, renewal responsibility, and security controls are recorded.

## Domain Record

| Field | Value |
| --- | --- |
| Domain |  |
| Intended role |  |
| Registrar |  |
| Registered owner/account |  |
| Acquisition date |  |
| Renewal date |  |
| Renewal price |  |
| Auto-renew enabled |  |
| Registrar lock enabled |  |
| MFA enabled |  |
| DNS provider |  |
| DNSSEC enabled |  |
| Evidence path |  |

## Routing

| Record | Value | Purpose | Verified |
| --- | --- | --- | --- |
| A/AAAA |  | Apex routing |  |
| CNAME |  | App/subdomain routing |  |
| TXT |  | Ownership verification |  |
| MX |  | Mail routing if enabled |  |
| SPF |  | Mail authentication |  |
| DKIM |  | Mail authentication |  |
| DMARC |  | Mail policy |  |

## Surface Mapping

| Surface | Route | Status |
| --- | --- | --- |
| Product homepage |  |  |
| Web app |  |  |
| Inspect surface |  |  |
| CLI install page |  |  |
| Developer docs |  |  |
| API |  |  |
| Admin dashboard |  |  |

## Security Review

| Control | Status | Evidence |
| --- | --- | --- |
| Registrar MFA |  |  |
| Registrar lock |  |  |
| DNSSEC |  |  |
| HTTPS certificate |  |  |
| HSTS |  |  |
| Mail authentication |  |  |
| Organization owner recorded |  |  |
| Renewal owner recorded |  |  |

## Decision

Choose one:

1. Domain ready for public use.
2. Domain ready for private beta only.
3. Domain held for defensive ownership only.
4. Domain not acquired.
5. Domain rejected.

Decision:

```text
Pending
```
