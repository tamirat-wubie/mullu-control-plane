# Schema Compatibility Policy

These schemas define the canonical shared JSON interchange surface for Mullu Platform.

## Compatibility Rules

1. Root objects are strict. Unknown top-level fields are rejected unless they are carried inside `metadata` or `extensions`.
2. `metadata` and `extensions` are the only forward-compatible escape hatches.
3. Shared docs in `docs/` define meaning. Schemas define field names, required fields, and enums for interchange.
4. Existing field meanings are stable. Do not repurpose an existing field for a different semantic role.
5. Additive changes are preferred. New required fields or reinterpreted enums require a coordinated docs, schema, and runtime update.
6. Python and Rust implementations must map to these fields without reinterpretation.
7. `workflow` and `plan` are shared coordination surfaces. They do not redefine policy, verification, or execution semantics.

## File Map

| File | Purpose |
| --- | --- |
| `capability_descriptor.schema.json` | Canonical capability declaration |
| `policy_decision.schema.json` | Canonical policy gate outcome |
| `execution_result.schema.json` | Canonical execution outcome |
| `trace_entry.schema.json` | Canonical causal audit entry |
| `replay_record.schema.json` | Canonical replay and audit capture |
| `verification_result.schema.json` | Canonical verification closure |
| `learning_admission.schema.json` | Canonical learning admission decision |
| `environment_fingerprint.schema.json` | Canonical environment fingerprint |
| `workflow.schema.json` | Shared workflow definition |
| `plan.schema.json` | Shared plan definition |

## Notes

The schemas stay conservative by keeping canonical meaning in shared docs and future growth in `metadata` or `extensions`. If shared behavior changes, update docs and schemas in the same change.
