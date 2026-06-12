<!--
Purpose: Define the governed boundary for durable Gmail connector runtime access after the bounded live adapter evidence proof.
Governance scope: OAuth authority, least-privilege scope selection, secret redaction, refresh-token lifecycle, revocation, audit receipts, and release blocking.
Dependencies: gateway/email_calendar_connector_adapters.py, gateway/email_calendar_worker.py, gateway/gmail_oauth_lifecycle.py, examples/sdlc/requirement_durable_gmail_connector_runtime_20260611.json, examples/sdlc/security_review_durable_gmail_connector_runtime_20260611.json, schemas/durable_gmail_oauth_operator_handoff.schema.json, scripts/validate_durable_gmail_connector_runtime_plan.py, scripts/validate_durable_gmail_oauth_operator_handoff.py, scripts/validate_durable_gmail_oauth_runtime_preflight.py, scripts/mint_gmail_oauth_access_token.py, scripts/produce_durable_gmail_oauth_operator_handoff.py, scripts/produce_durable_gmail_oauth_live_receipt.py.
Invariants: No Google Cloud credential creation, OAuth client creation, consent-screen publication, or production verification claim is performed by this repository-local plan.
-->

# Durable Gmail Connector Runtime Plan

## Architecture

The completed adapter-evidence milestone proved that the email/calendar worker can execute a bounded Gmail read probe when a scoped connector token is supplied. Durable runtime access is a different boundary:

```text
bounded evidence token
-> governed OAuth app boundary
-> least-privilege scope decision
-> refresh-token storage and rotation
-> revocation and failed-refresh recovery
-> approval-gated write actions
-> production readiness witness
```

The durable boundary is not closed by the prior live adapter receipt. It stays `AwaitingEvidence` until the provider-side OAuth and runtime lifecycle witnesses exist.

## Requirement Boundary

| Boundary | Required decision |
| --- | --- |
| Scope | Select the narrowest Gmail scope that satisfies the connector operation before any credential mutation. |
| Environment | Keep testing/staging and production OAuth projects separate when public production use is planned. |
| Consent | Configure consent-screen identity, support contact, domain ownership, and app use statement before user-data access is expanded. |
| Secret lifecycle | Store only secret presence and receipt refs in repository artifacts; never serialize access tokens, refresh tokens, client secrets, or private keys. |
| Runtime | Implement refresh, expiry, rotation, revocation, and failed-refresh recovery before durable access is claimed. |
| Approval | Keep Gmail send and draft actions approval-gated; a read-only probe token must not admit write operations. |

## Algorithm

1. Choose the connector operation family: read-only search, message metadata, draft creation, or send.
2. Map the operation family to the least-privilege Gmail scope using current Google Workspace documentation.
3. Classify the scope as non-sensitive, sensitive, or restricted before creating or changing provider credentials.
4. If sensitive or restricted, record the required Google verification path before public production use.
5. Create provider-side credentials only after explicit operator authority and record a redacted witness.
6. Bind runtime secrets through the governed secret store and record presence-only receipts.
7. Produce the repository-local operator handoff packet before any provider or secret-store mutation.
8. Classify refresh-token outcomes through the repository-local lifecycle contract: refreshed, retryable provider error, revoked or expired refresh token, OAuth client rejection, scope rejection, malformed provider response, and too-short access-token lifetime.
9. Run `scripts\mint_gmail_oauth_access_token.py` in the live-evidence workflow or `scripts\produce_durable_gmail_oauth_live_receipt.py` in local proof mode to refresh a transient access token, execute the existing Gmail read-only live probe, and persist only redacted refresh and adapter evidence.
10. Run approval-gated send/draft evidence only if write operations are in scope.
11. Update release readiness only after all receipts pass.

## Non-Goals

- No Google Cloud credential creation in this change.
- No OAuth consent-screen publication in this change.
- No production verification submission in this change.
- No repository storage of token values, refresh-token values, client secrets, or private keys.
- No expansion from Gmail to Google Calendar or Microsoft Graph in this change.

## Evidence Gates

| Gate | Status before durable runtime claim |
| --- | --- |
| OAuth consent-screen witness | Required |
| OAuth client witness | Required |
| Least-privilege scope receipt | Required |
| Refresh-token storage receipt | Required |
| Rotation and revocation receipt | Required |
| Failed-refresh recovery receipt | Required |
| Read-only Gmail probe receipt | Required |
| Write-action approval receipt | Required only if draft or send is enabled |
| Security review | Release-blocking until provider and runtime witnesses exist |

## Verification

Run:

```powershell
python scripts\validate_durable_gmail_connector_runtime_plan.py
python scripts\produce_durable_gmail_oauth_operator_handoff.py --json
python scripts\validate_durable_gmail_oauth_operator_handoff.py --require-blocked --json
python scripts\validate_durable_gmail_oauth_runtime_preflight.py --json
python scripts\mint_gmail_oauth_access_token.py --json
python scripts\produce_durable_gmail_oauth_live_receipt.py --json
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_durable_gmail_connector_runtime_20260611.json --strict
python -m pytest tests\test_durable_gmail_connector_runtime_plan.py tests\test_validate_durable_gmail_oauth_operator_handoff.py tests\test_validate_durable_gmail_oauth_runtime_preflight.py tests\test_mint_gmail_oauth_access_token.py tests\test_produce_durable_gmail_oauth_operator_handoff.py tests\test_produce_durable_gmail_oauth_live_receipt.py tests\test_gateway\test_gmail_oauth_lifecycle.py -q
```

The plan validator must pass while still reporting the durable provider-side runtime boundary as not yet production-releasable. The operator handoff producer emits only command templates, expected evidence refs, scope decisions, recommended non-secret defaults, and presence-only binding names; it performs no Google Cloud, Gmail, or GitHub secret mutation. Recommended defaults are not observed preflight evidence: the runtime preflight remains `AwaitingEvidence` until the required Gmail OAuth scope, durable secret presence, provider witnesses, refresh-token storage receipt, and revocation/recovery receipt exist. The workflow token mint helper writes the access token only to the requested runtime environment file, and the durable live receipt producer performs one token refresh and one Gmail read-only probe before writing only redacted refresh classification, access-token digest evidence, and existing email/calendar worker receipt refs. The lifecycle contract classifies refresh outcomes without printing token, refresh-token, client-secret, or private-key values.

STATUS:
  Completeness: 100%
  Invariants verified: [external credential mutation blocked, least-privilege scope gate defined, secret value serialization blocked, operator handoff packet redacted, refresh and revocation evidence required, failed-refresh recovery classified, write actions approval-gated]
  Open issues: [OAuth consent-screen witness, OAuth client witness, refresh-token lifecycle witness, revocation witness]
  Next action: execute provider-side OAuth setup only under explicit operator authority
