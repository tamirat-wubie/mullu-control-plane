# Domain Acquisition Plan

Purpose: define the domain acquisition and routing plan for `Mullu Govern` as the public product and `Mullu` as the suite/family.
Governance scope: domain availability, canonical product URL, fallback hierarchy, DNS ownership evidence, and public launch routing.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/PUBLIC_LAUNCH_COPY.md`.
Invariants: no public paid launch under `Mullu Govern` until at least one suitable product domain or subdomain is controlled.

## Domain Priority

| Priority | Domain | Role | Decision |
| ---: | --- | --- | --- |
| 1 | `mullu.ai` | Primary product domain | Acquire if available and legally acceptable |
| 2 | `mullu.app` | App-forwarding product domain | Acquire if available |
| 3 | `mullu.dev` | Developer/product domain | Acquire if available |
| 4 | `getmullu.com` | Marketing fallback | Acquire if clean primary domains are unavailable |
| 5 | `mullu.mullusi.com` | Controlled subdomain fallback | Use if external product domains are unavailable |
| 6 | `mullusi.com/mullu` | Company-site fallback | Use for earliest public page before standalone domain |
| 7 | `govern.mullusi.com` | Mullu Govern product subdomain | Use after route ownership and product-copy review |
| 8 | `mullusi.com/govern` | Mullu Govern route fallback | Use if `/mullu` remains suite-family route |

## Recommended Routing

| Surface | Preferred route | Fallback route |
| --- | --- | --- |
| Mullu Govern homepage | `govern.mullusi.com` or `mullu.ai/govern` | `mullusi.com/govern` or `mullusi.com/mullu` |
| Mullu suite homepage | `mullu.ai` | `mullusi.com/mullu` |
| Web app | `app.mullu.ai` | `mullu.mullusi.com` |
| Inspect surface | `inspect.mullu.ai` | `mullusi.com/mullu/inspect` |
| CLI install | `cli.mullu.ai` | `docs.mullusi.com/mullu/cli` |
| Developer docs | `docs.mullusi.com` | `mullu.dev/docs` |
| API | `api.mullusi.com` | `api.mullu.ai` only after API boundary review |
| Admin dashboard | `dashboard.mullusi.com` | Keep under Mullusi trust domain |

## Acquisition Evidence

For each candidate domain, record:

1. Registrar searched.
2. Date and timezone.
3. Availability result.
4. Price and renewal price.
5. Premium-domain status.
6. Whois/privacy status if already registered.
7. Confusable domains discovered.
8. Acquisition result.
9. DNS ownership proof.
10. Renewal owner and payment account.

## DNS and Security Requirements

1. Use DNSSEC where supported.
2. Use registrar lock.
3. Use organization-controlled registrar account.
4. Enforce MFA on registrar account.
5. Configure SPF, DKIM, and DMARC for any mail-enabled domain.
6. Use HSTS after HTTPS is stable.
7. Keep admin/governance surfaces on `mullusi.com` trust domains unless a security review approves product-domain routing.

## Launch Decision

Minimum domain requirement for public launch:

```text
Either mullu.ai is acquired
or mullu.mullusi.com is live under controlled Mullusi DNS.
```

Do not advertise `mullu.ai`, `mullu.app`, `mullu.dev`, or `getmullu.com` until
registrar ownership and DNS control are verified.
