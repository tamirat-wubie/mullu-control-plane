# 31 — Operational Graph

## Purpose

The operational graph is the single canonical structure that unifies all platform
artifacts into one directed, typed, timestamped graph of operational reality.
Every goal, job, workflow, skill execution, incident, approval, review, runbook,
provider action, verification, communication thread, document, function, person,
and team is a node.  Every causal, dependency, ownership, obligation, decision,
blocking, escalation, production, verification, assignment, and communication
relationship is an edge.

The graph answers: *what happened, why, who was responsible, what depended on
what, and what obligations remain outstanding* — at any point in time.

## Node Types

| Node Type              | Description                                          |
|------------------------|------------------------------------------------------|
| goal                   | A declared objective with success criteria            |
| workflow               | A sequenced set of stages executed toward a goal      |
| skill                  | A reusable operational capability                     |
| job                    | A unit of assigned work with ownership and deadline   |
| incident               | An unplanned disruption requiring response            |
| approval               | A gate requiring human or policy sign-off             |
| review                 | A structured evaluation of an artifact or outcome     |
| runbook                | A documented procedure for a known scenario           |
| provider_action        | An action delegated to an external provider           |
| verification           | A check that a postcondition or invariant holds       |
| communication_thread   | A threaded conversation between participants          |
| document               | A persistent knowledge or policy artifact             |
| function               | An organizational service function                    |
| person                 | An individual human operator or stakeholder           |
| team                   | A group of persons sharing a work queue               |

## Edge Types

| Edge Type          | Semantics                                                |
|--------------------|----------------------------------------------------------|
| caused_by          | Target node was a direct cause of the source node        |
| depends_on         | Source node cannot proceed until target node completes    |
| owns               | Source node has ownership responsibility for target node  |
| obligated_to       | Source node has a formal obligation toward target node    |
| decided_by         | Source node outcome was determined by target node         |
| blocked_by         | Source node is currently blocked by target node           |
| escalated_to       | Source node was escalated to target node for resolution   |
| produced           | Source node produced target node as output                |
| verified_by        | Source node was verified by target node                   |
| assigned_to        | Source node is assigned to target node for execution      |
| communicates_via   | Source node communicates through target node              |

## Graph Properties

1. **Directed** — every edge has a source and a target; direction encodes the
   semantic relationship.
2. **Typed** — every node carries a `NodeType` and every edge carries an
   `EdgeType`; no untyped artifacts exist in the graph.
3. **Timestamped** — every node and every edge carries a `created_at` ISO 8601
   timestamp.  Ordering is derivable from timestamps alone.
4. **Immutable edges (append-only)** — once written, an edge is never modified
   or deleted.  Corrections are expressed by appending new edges, never by
   mutating or removing existing ones.

## Query Model

- **Traverse from any node** — given a node, follow outgoing or incoming edges
  of any type to discover its neighborhood.
- **Filter by edge type** — restrict traversal to a single edge type (e.g.
  "show me only `depends_on` edges from this goal").
- **Find causal paths** — given two nodes, enumerate all paths composed of
  `caused_by` edges connecting them.
- **Find obligations** — traverse `obligated_to` edges to enumerate all
  outstanding obligations anchored at a node.

## Snapshot Model

A `GraphSnapshot` captures the count of nodes and edges at a specific point in
time.  Combined with the append-only edge log, any historical graph state can be
reconstructed by replaying edges up to the snapshot timestamp.  This supports
full audit replay and temporal queries.

## Prohibitions

1. **No edge without both nodes existing** — an edge cannot reference a
   `source_node_id` or `target_node_id` that does not correspond to an existing
   node.
2. **No backdating edges** — an edge's `created_at` must be equal to or later
   than both its source and target node `created_at` values.
3. **No edge deletion** — edges are append-only.  The graph never loses
   information.  Corrections and supersessions are modeled as new edges, not as
   mutations of old ones.
