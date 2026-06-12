# Lawbook Migration

The lawbook is part of Λ. It defines rules that validate symbolic state Σ.

The base lawbook is deterministic:

```text
id      = 00000000-0000-0000-0000-000000000101
version = 1
```

Each migration creates a `LawbookTransition` embedded in a normal signed commit:

```text
LawbookMigration
  → current lawbook validation
  → next lawbook construction
  → next state metadata patch
  → Commit.lawbook_transition
  → append
  → apply
```

The live lawbook is replaced only after the commit is accepted by the event store.

## Supported operations

```text
AddRule { rule }
RemoveRule { rule }
```

Supported rules:

```text
RequireKey { key }
ForbidKey { key }
ImmutableKey { key }
```

## Safety rules

```text
from_version must equal current lawbook version
to_version must equal current + 1
migration operations must not be empty
foundation rules cannot be removed by default
next state must satisfy the next lawbook before commit creation
replay verifies before_hash, after_hash, and embedded lawbook transition hashes
```

## State metadata

Each migration updates:

```text
lawbook.id
lawbook.version
lawbook.hash
```

These cells make the active lawbook visible through state and replay traces without granting mutation authority.
