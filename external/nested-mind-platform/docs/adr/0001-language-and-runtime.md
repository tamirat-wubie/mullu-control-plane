# ADR 0001: Language and Runtime

## Status

Accepted.

## Decision

Use Rust as the primary implementation language for the symbolic kernel and production API.

## Rationale

The platform depends on invariant preservation, causal state transitions, and strict boundaries between proposal, validation, commit, and projection. Rust is a strong fit because the type system and ownership model help make illegal states and unsafe mutation paths harder to express.

## Consequences

Positive:

- strong compile-time guarantees
- clear crate boundaries
- low runtime overhead
- suitable for API, CLI, storage, and embedded execution

Negative:

- slower initial prototyping than Python
- stricter learning curve
- some symbolic experimentation may still need a Python research layer

## Boundary

Python may be added later as an SDK or research adapter. It must not own the kernel or bypass validation.
