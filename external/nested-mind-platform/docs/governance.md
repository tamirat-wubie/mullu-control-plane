# Governance

## Judgment kernel

```text
Ψ(PS, SE, EFF, SG, PRR, CPM, ERL, PCE, PCB, K) → J
```

The first implementation keeps `J` compact:

```text
Judgment := {
  accepted,
  rationale,
  constructive_delta,
  fracture_delta,
  law_trace
}
```

## Constructive delta

What changed in capability, accuracy, coverage, or system strength.

Examples:

- added a required symbolic cell
- attached a child mind
- improved a rule
- exposed a safer projection

## Fracture delta

What risk, ambiguity, or invariant pressure was introduced.

Examples:

- a rule is too broad
- a projection exposes too much
- a parent/child boundary is unclear
- a patch weakens required state

## No silent failure

Invalid proposals must return explicit rejection causes. The kernel must not partially apply a failed patch.

## Reversibility

A commit is reversible only by a new compensating commit. History is never deleted in production.

## Append-before-apply rule

No runtime gateway may mutate a mind before the corresponding commit has been accepted by the event store.

```text
¬append(commit) ⇒ ¬apply(next_state)
```

## Replayability rule

A mind state that cannot be reconstructed from immutable identity plus causal history is not production-valid.

```text
Σ is valid ⇔ replay(Ι, H) = Σ
```

## Projection rule

No API response may expose state without passing through a projection policy.

```text
response.state ⊆ project(Σ, Γ_policy)
```


## Topology rule

Nested minds must be attached through causal commits, not hidden map mutation.

```text
attach(child, parent) ⇒ commit.topology contains AttachChild(child.identity)
```

## Lawbook migration governance

Changing Λ requires `MigrateLawbook`. Under the default policy `Maintainer` and `Admin` have that permission. The migration is still not trusted merely because an admin requested it; the next lawbook must validate the resulting state and the event must preserve the previous and next lawbook hashes.

## Audit governance

`Auditor` can read events, replay, read snapshots, and audit, but cannot create snapshots, propose patches, attach child minds, or migrate lawbooks.


## Maintenance governance

Schema migration, snapshot compaction, and observability access are separate permissions. Maintainers can run maintenance. Auditors can inspect schema and observability state. Operators cannot compact snapshots or migrate schema by default.
