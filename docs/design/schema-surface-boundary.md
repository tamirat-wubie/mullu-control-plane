# Schema surface boundary

<!-- TYPE: Design -->
<!-- AUDIENCE: developers adding runtime contracts or public protocol schemas -->

## Decision

Treat `schemas/*.schema.json` as the public Mullu Governance Protocol surface.
Treat `mcoi/mcoi_runtime/contracts/*.py` as runtime contract implementation
unless a matching public schema is intentionally added and indexed.

This keeps additive runtime work from accidentally widening the public protocol
surface.

## Boundary rule

```text
runtime-only contract
  → mcoi/mcoi_runtime/contracts/*.py
  → tests/*
  → docs/design/*
  → no public manifest update required

public wire/protocol contract
  → schemas/*.schema.json
  → schemas/mullu_governance_protocol.manifest.json entry required
  → validator coverage required
```

The protocol manifest validator intentionally compares every public schema file
under `schemas/*.schema.json` with `schemas/mullu_governance_protocol.manifest.json`.
If a schema file is added without a manifest entry, CI fails. This is correct:
a schema under `schemas/` is a public claim, not a private implementation detail.

## When to add a public schema

Add a `schemas/*.schema.json` file only when all of these are true:

1. The object is meant to be consumed as a stable wire or public protocol
   contract.
2. The schema `$id` uses `urn:mullusi:schema:<schema-id>:<version>`.
3. The schema is added to `schemas/mullu_governance_protocol.manifest.json`.
4. The change is described as a protocol-surface change in the PR body.
5. Backward-compatibility and version impact are explicit.

## When not to add a public schema

Do not add a public schema when the change is only:

- a Python runtime dataclass or helper.
- a read model internal to the control plane.
- a default-off integration seam.
- a proof-of-concept contract not ready for third-party implementation.
- a test fixture shape.

Use runtime contracts and tests instead.

## Nested-mind application

The nested-mind typed projection import currently belongs to the runtime-only
side:

```text
mcoi/mcoi_runtime/contracts/nested_mind.py
```

It validates the control-plane read boundary for nested-mind Γ projection and
history envelopes. It does not yet need to be a public Mullu Governance Protocol
schema because no third-party implementation contract is being claimed.

If nested-mind projection import later becomes a stable public protocol surface,
then add:

```text
schemas/nested_mind_projection.schema.json
schemas/mullu_governance_protocol.manifest.json entry
```

in the same PR.

## PR checklist

For any PR touching `schemas/*.schema.json`:

```text
[ ] The schema is meant to be public protocol surface.
[ ] The schema has a stable `$id` URN.
[ ] The manifest includes exactly one matching entry.
[ ] `python scripts/validate_protocol_manifest.py` passes.
```

For runtime-only contracts:

```text
[ ] No new `schemas/*.schema.json` file was added.
[ ] Runtime contract tests cover validation and failure behavior.
[ ] Docs state the boundary if the contract could be mistaken for public API.
```
