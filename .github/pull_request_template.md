## Summary

<!-- Describe the constructive delta and the invariant this PR protects. -->

## Governance posture

- [ ] No silent authority expansion.
- [ ] New write or mutation paths are explicit and gated.
- [ ] Runtime-only contracts are not presented as public protocol surface.

## Schema surface boundary

If this PR adds or changes `schemas/*.schema.json`:

- [ ] The schema is intended as public Mullu Governance Protocol surface.
- [ ] The schema `$id` is stable and uses `urn:mullusi:schema:<schema-id>:<version>`.
- [ ] `schemas/mullu_governance_protocol.manifest.json` has exactly one matching entry.
- [ ] `python scripts/validate_protocol_manifest.py` passes.
- [ ] The PR body states backward-compatibility and version impact.

If this PR adds runtime-only contracts:

- [ ] No new public `schemas/*.schema.json` file was added accidentally.
- [ ] Runtime contract tests cover validation and rejection behavior.
- [ ] Docs identify the boundary when the shape could be mistaken for public API.

## Validation

```bash
python scripts/validate_protocol_manifest.py
python scripts/validate_release_status.py --strict
```

Additional targeted checks:

```bash
# add targeted tests here
```
