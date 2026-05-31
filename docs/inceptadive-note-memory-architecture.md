# InceptaDive Note-Memory Architecture

Purpose: record the applied InceptaDive-M, InceptaDive Sigma, InceptaMesh, and
Mullu control-plane separation for governed note-memory intelligence.
Governance scope: lineage separation, no direct execution from memory,
projection-only Boxes, audited scoring, repair paths, and decision-use receipts.
Dependencies: `mcoi_runtime.core.note_memory_mesh`, Concept Box ledger, axis
traversal, scoring adapter, projection engine, repair queue, action compiler,
decision-use receipts, and temporal/outcome bridges.
Invariants: memory preserves, InceptaDive-M maps, Sigma/Mesh scores, projection
stabilizes, governance decides, execution acts only after approval, and outcome
records teach through governed write paths.

## Applied Stack

```text
user input
-> governed note-memory
-> InceptaDive-M Concept Box mapping
-> InceptaDive Sigma / InceptaMesh scoring
-> note-memory projection
-> contradiction, gap, risk, and opportunity detection
-> candidate workflow actions
-> Mullu governance verdict
-> execution only if approved
-> outcome stored back into note-memory through governed write paths
```

## Lineage Separation

| Layer | Role | Must not do |
| --- | --- | --- |
| InceptaDive-M | Map concepts as Concept Boxes and traverse axes. | Expose proprietary internals, promote truth, or approve execution. |
| InceptaDive Sigma / InceptaMesh | Score findings with resonance, suppression, and true delta. | Run raw unguarded Sigma memory denominators in production. |
| Mullu control plane | Decide approval, block, repair, escalation, promotion, or scheduling. | Treat projection output as source truth. |

Production scoring uses the InceptaMesh denominator guard:

```text
memory_denominator = max(k - j, 1)
```

## Runtime Modules

| Module | Responsibility |
| --- | --- |
| `concept_box_ledger.py` | Stores projection-only Concept Boxes with source note and event lineage. |
| `inceptadive_axis_traversal.py` | Emits vertical, horizontal, circular, diagonal, temporal, intensity, and meta findings. |
| `incepta_scoring_adapter.py` | Scores findings through the audited Sigma/Mesh public line. |
| `note_memory_projection.py` | Builds active claims, inactive claims, blockers, conflicts, candidate actions, and projection receipts. |
| `inceptadive_interrogation_queue.py` | Prioritizes next Concept Box interrogations from blockers, conflicts, repairs, and new notes. |
| `memory_repair_queue.py` | Converts fractures into explicit repair tasks. |
| `memory_action_compiler.py` | Compiles candidate actions without execution authority. |
| `decision_use_receipts.py` | Proves how memory affected a decision. |
| `note_memory_world_state_bridge.py` | Converts projected claims into entity-state facts. |
| `note_memory_temporal_bridge.py` | Emits scheduler-safe checks and reminders only. |
| `outcome_learning_bridge.py` | Records expected-versus-actual outcome learning candidates. |
| `operational_dashboard_intelligence.py` | Exposes read-only operational state, blockers, repairs, actions, confidence, and workflow health. |

## Audit Invariants

1. No direct execution from memory, InceptaDive-M, Sigma, Mesh, projection, or action compiler output.
2. Every insight has lineage.
3. Every promoted claim must have evidence references.
4. Every contradiction creates a repair path.
5. Every candidate action carries source note IDs or repair IDs.
6. Every high-risk action requires a governance verdict.
7. Every decision influenced by memory has a decision-use receipt.
8. Every projected state is rebuildable from append-only note memory.
9. Every summary is a projection, not the source of truth.
10. Expired, superseded, contradicted, or rejected notes cannot silently influence execution.

STATUS:
  Completeness: 100%
  Invariants verified: lineage separation recorded, Mesh denominator guard recorded, projection-only boundary recorded, no direct execution recorded
  Open issues: none
  Next action: verify runtime modules and focused tests
