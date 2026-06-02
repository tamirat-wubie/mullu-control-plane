<!--
Purpose: define the local compatibility boundary for GitHub App installation token format changes.
Governance scope: GitHub App installation token handling, token storage shape, validation assumptions, CI scanning, per-request override testing, and deployment blocking.
Dependencies: examples/foundation_github_app_token_format_witness.awaiting_evidence.json and scripts/validate_foundation_github_app_token_format_boundary.py.
Invariants: tokens are opaque; token length is not fixed; ghs_ tokens may be long; JWT-shaped ghs_ tokens must not be parsed; no live credential is stored; no deployment readiness claim is made.
-->

# Foundation GitHub App Token Format Boundary

> GitHub App installation tokens are opaque bearer tokens. The repository must not assume a fixed token length, fixed suffix shape, or parseable internal structure.

## Why This Exists

GitHub announced that GitHub App installation tokens are moving to a new stateless `ghs_...` format. The new tokens may be much longer, roughly 520 characters, and may contain JWT-style dot separators. Any app, workflow, schema, secret wrapper, validator, log scrubber, or test fixture that assumes old fixed-length tokens can break.

This boundary converts that platform notice into repository rules.

Witness packet: [`../examples/foundation_github_app_token_format_witness.awaiting_evidence.json`](../examples/foundation_github_app_token_format_witness.awaiting_evidence.json)

## Required Compatibility Rules

1. Accept `ghs_` tokens as opaque strings.
2. Do not require `len(token) == 40`, `len(token) == 36`, or any other exact length.
3. Do not use regexes that assume `ghs_` is followed by a fixed 36-character suffix.
4. Do not reject dot separators inside a `ghs_` token.
5. Do not parse GitHub App installation tokens as JWTs, even when they look JWT-shaped.
6. Ensure any storage field, config value, secret wrapper, or serialized token field can hold at least 520 characters.
7. Keep real tokens out of Git, logs, fixtures, receipts, docs, and examples.
8. Use GitHub's temporary per-request override header only for validation of both token formats.

## Temporary Validation Header

For the installation-token creation request only:

```http
POST /app/installations/:installation_id/access_tokens
X-GitHub-Stateless-S2S-Token: enabled
```

Use `enabled` to test the new stateless token format and `disabled` to test the classic opaque format. Remove the override after compatibility is validated.

## Safe Test Fixtures

Use synthetic non-secret fixtures only. They are not real credentials.

```text
ghs_short_opaque_fixture_without_secret_value
ghs_long_stateless_fixture.with.dot.separators.and.length.padding................................................................................................................................................................................................................................................................................................................................................................................................................................................
```

## Blocked Pattern Families

The validator blocks future assumptions about exact token length, fixed `ghs_` suffix length, short database fields for GitHub installation tokens, JWT parsing of installation tokens, and fixed 40-character masking or slicing.

## Operator Checklist

- Search for exact-length token validation.
- Search for fixed-size database fields that hold GitHub installation tokens.
- Search for log scrubbers that only mask the first 40 characters.
- Search for tests using fixed 40-character `ghs_` fixtures.
- Run the compatibility validator.
- Run one controlled GitHub App token request with the override set to `enabled` and one with `disabled` if live GitHub App credentials exist outside the repository.

## Status

```text
github_app_token_format_boundary_state=ActiveLocalGuard
tokens_are_opaque=true
fixed_length_token_validation_allowed=false
jwt_parsing_of_installation_tokens_allowed=false
minimum_storage_capacity_chars=520
real_tokens_committed=false
deployment_allowed=false
```

## Validation

Run:

```bash
python scripts/validate_foundation_github_app_token_format_boundary.py
```

This validates the committed docs, examples, workflows, source, and configuration files for obvious fixed-length GitHub App installation token assumptions.
