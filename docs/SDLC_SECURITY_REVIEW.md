# SDLC Security Review

Purpose: define security review classification and release-blocking findings for governed software changes.
Governance scope: OCE finding fields, RAG impact-to-check mapping, CDCV mitigation traceability, CQTE severity decision rules, UWMA security receipts, and PRS residual-risk closure.
Dependencies: `docs/SDLC.md`, `schemas/sdlc_security_review.schema.json`, and `scripts/validate_sdlc_security_review.py`.
Invariants: unresolved critical or high findings block release; redaction, tenant-scope, authorization, and receipt integrity checks are explicit when applicable.

## Impact Categories

```text
none
auth
tenant_scope
budget
filesystem
network
external_api
secrets
policy
deployment
memory
receipts
audit
```

## Required Checks

| Category | Required check |
| --- | --- |
| tenant_scope | IDOR or cross-tenant test |
| filesystem | path traversal test |
| network | allowlist or SSRF test |
| secrets | redaction test |
| budget | budget ownership test |
| policy | policy bypass test |
| deployment | deployment witness test |
| memory | memory admission test |
| receipts | receipt integrity test |
| audit | audit visibility test |

## Release Block

```text
unresolved_finding.severity in {critical, high} -> block_release
```

Each finding must include severity, status, mitigation, evidence references, and residual risk. If impact is `none`, the review must still state why no security-sensitive surface was touched.
