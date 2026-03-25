# 27 -- Mfidel Semantic Overlay Layer

Status: Phase 22D
Module: `mcoi_runtime.core.mfidel_semantics`

---

## Purpose

Mfidel provides semantic indexing, clustering, and retrieval over platform
artifacts without replacing the typed operational core.  It adds a meaning layer
that lets the runtime (and its operators) discover relationships between goals,
skills, incidents, lessons, and other artifacts that share conceptual overlap
even when their typed identifiers differ.

## Role -- overlay, not substrate

Mfidel is an **overlay**.  It improves meaning, retrieval, grouping, and
explanation.  It does not define the canonical persistence formats, execution
contracts, or provider protocols.  The typed contracts in
`mcoi_runtime.contracts` remain the single source of truth for operational
semantics; Mfidel annotations sit *alongside* those contracts and enrich them
with discoverable meaning.

Key distinction:

| Operational core              | Mfidel overlay                    |
| ----------------------------- | --------------------------------- |
| Typed contracts & enums       | Semantic tags & embeddings        |
| Deterministic execution       | Approximate similarity & search   |
| Strict validation on write    | Read-only annotations on read     |
| Identity by stable identifier | Grouping by meaning               |

## Indexed artifact types

Mfidel can annotate any artifact that carries a stable identifier and textual
content.  The initial set:

- **Goals** -- intent descriptions, success criteria
- **Workflows** -- step graphs, trigger descriptions
- **Skills** -- skill descriptors, step action types
- **Runbooks** -- procedure text, guard conditions
- **Incidents** -- error context, resolution notes
- **Lessons** -- learned patterns, outcome summaries
- **Knowledge artifacts** -- documentation fragments, policy text

## Capabilities

1. **Semantic similarity** -- compute a 0.0--1.0 similarity score between any
   two annotated artifacts using cosine similarity over embedding vectors.
2. **Family clustering** -- group related annotations into semantic families
   using single-linkage clustering with a configurable threshold.
3. **Explanation generation** -- produce human-readable descriptions of why a
   family of artifacts belongs together, derived from their shared tags.
4. **Multilingual symbolic retrieval** -- because tags and embeddings are
   language-agnostic vectors, retrieval works across naming conventions and
   natural languages (once backed by a real embedding model).

## What Mfidel is NOT for

- **Persistence formats** -- Mfidel does not define how artifacts are stored.
- **Provider protocols** -- adapter IO, model dispatch, and credential handling
  remain outside Mfidel's scope.
- **Deployment configuration** -- infrastructure topology, scaling rules, and
  environment bindings are not semantic concerns.
- **Low-level runtime enforcement** -- precondition checks, policy gates, and
  lifecycle transitions are governed by the typed contract layer.

## Integration

Mfidel reads from existing typed contracts and produces semantic annotations
that sit alongside (not inside) operational artifacts.

```
  Typed contracts          Mfidel overlay
  +-----------------+      +------------------------+
  | SkillDescriptor | ---> | SemanticAnnotation      |
  | GoalRecord      | ---> |   .tags                 |
  | IncidentReport  | ---> |   .embedding            |
  +-----------------+      |   .description           |
                           +------------------------+
                                    |
                           +------------------------+
                           | SemanticFamily          |
                           |   .members (artifact ids)|
                           |   .description           |
                           +------------------------+
```

The `MfidelSemanticIndex` class provides the algorithmic surface:

- `annotate()` -- create a `SemanticAnnotation` for an artifact
- `similarity()` -- cosine similarity between two annotations
- `find_similar()` -- retrieve annotations above a threshold
- `cluster_into_families()` -- group annotations by meaning
- `explain_family()` -- human-readable family description

### Embedding strategy

The initial implementation uses a simplified bag-of-words frequency vector
(top 64 dimensions from a sorted vocabulary).  This is intentionally simple and
serves as a placeholder for future model-backed embeddings provided through the
platform's provider system.

### Clock injection

All timestamp-bearing operations accept an injected clock function for
deterministic replay, consistent with the platform's replay invariants
(docs/03_trace_and_replay.md).
