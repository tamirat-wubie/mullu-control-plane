# Execution Model

Purpose: reserve the execution boundary for MCOI Runtime.
Governance scope: Milestone 0 structure only.
Dependencies: shared policy, execution, and verification semantics.
Invariants: execution follows policy; adapters do not mutate committed state directly.

## Reserved execution surfaces

- Template validation
- Dispatcher
- Controlled executor adapters
- Execution result capture

## Effect observation paths

Shell templates may declare `effect_observation_paths` when the command is
expected to mutate local files. The governed dispatcher snapshots each declared
path before dispatch, observes the same path after dispatch, and emits a
`file_changed` actual effect only when the path metadata or content hash changes.

If `effect_observation_paths` is present and `declared_effects` is omitted, the
default expected effects are `process_completed` and `file_changed`. A command
that exits successfully but does not produce the declared file delta is therefore
reconciled as incomplete instead of completed.

The observation record stores path hashes, size, timestamps, content hashes, and
error codes. It does not store raw file contents.
