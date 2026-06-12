# Security Policy

## Supported versions

Only the latest `main` branch is supported during pre-release development.

## Reporting

Report vulnerabilities privately to the repository owner before public disclosure.

## Kernel security rules

- External systems can propose edits but cannot directly mutate kernel state.
- All accepted edits must produce a causal commit with before/after hashes.
- Projection endpoints must not expose private invariant internals by default.
- Unsafe Rust is forbidden unless an architecture decision record explicitly approves it.
- Secrets must never be committed. Use repository/environment secrets for deployment.
- Backup artifacts must be treated as sensitive because they can contain internal state, event history, and audit records.
- Rate limiting is a runtime protection, not an authorization control.
- Restore operations must verify backup hashes and event-chain signatures before files are promoted into service.

## v7 identity and signing boundary

Trusted identity headers are unsafe unless the service is behind a gateway that strips client-supplied identity headers and injects verified OIDC/mTLS values. Leave `MIND_TRUSTED_IDENTITY_HEADERS=false` unless that gateway boundary exists.

Do not use `MIND_COMMIT_SIGNING_SEED_HEX` for production secret custody. The v7 signing model includes secret-manager/HSM/KMS/external-request states so production can move signing out of environment variables.

## v8 security notes

- Prefer direct OIDC/JWKS verification or a hardened mTLS/OIDC gateway over bootstrap tokens.
- Keep JWKS files current until automated refresh/discovery is added.
- Managed signing completions must be accepted only after the returned signature verifies against the exact commit payload.
- Cloud backup plans should be executed with object-lock/retention policies where supported by the target provider.
- Replication batches should be transported over authenticated channels and appended durably only after follower validation.

## v9 security notes

```text
+ OIDC discovery/JWKS refresh evidence is ledgered.
+ Vendor signing receipts are not trusted unless the resulting commit signature verifies.
+ Replicated follower ingestion verifies event-record hashes before persistence.
+ Local cloud mirror transfer verifies backup body hashes and backup integrity.
```

Remaining security work:

```text
- live JWKS fetch must enforce HTTPS, issuer pinning, cache lifetime, and rollback protection.
- vendor signing adapters should verify provider attestations where available.
- replication transport needs authenticated channel binding and replay protection.
```
