# Governed Note-Memory Control-Plane Handoff

Purpose: bind temporary execution notes and durable memory anchors to the
canonical `mullu-control-plane` repository.
Governance scope: note capture, episode capsules, deterministic claim
contradiction evidence, retrieval guards, retrieval receipts, rejected-delta
evidence, promotion receipts, and optional HTTP route mounting.
Dependencies: `mcoi_runtime.core.note_memory_*` modules and
`mcoi_runtime.app.note_memory_integration`.
Invariants: temporary notes require expiry, episode capsules require evidence,
durable anchors require accepted promotion receipts, and HTTP mounting is
disabled unless explicitly configured.

## Boundary

The governed note-memory surface is part of the control-plane project, not a
separate governed-swarm repository boundary.

```text
MULLU_NOTE_MEMORY_ENABLED=true
MULLU_NOTE_MEMORY_STORE_PATH=<append-only note memory directory>
```

Disabled startup mounts no note routes. Enabled startup without
`MULLU_NOTE_MEMORY_STORE_PATH` fails closed.

## Routes

```text
POST /api/v1/notes/events
POST /api/v1/notes/rejected-deltas
POST /api/v1/notes/episodes
POST /api/v1/notes/retrieve
POST /api/v1/notes/expire
POST /api/v1/notes/promotions
POST /api/v1/notes/anchors
POST /api/v1/notes/index/rebuild
GET  /api/v1/notes/dashboard
GET  /api/v1/notes/events
GET  /api/v1/console/note-memory
GET  /api/v1/console/note-memory/view
```

The `/api/v1/notes/dashboard`, `/api/v1/console/note-memory`, and CLI
`dashboard` surfaces are read-only projections over the same runtime snapshot.
Mounted dashboard snapshots carry `snapshot_id`, `snapshot_hash`, and
`assessed_at` witness fields so downstream dashboards can correlate the exact
bounded read model they rendered without reading the append-only store
directly.
The operator console route returns the same stable summary shape when note
memory is disabled, unregistered, unmounted, or mounted without a configured
store path. Rejected deltas, pending promotions, memory anchors,
contradictions, and audit events are separated so rejected evidence is not
counted as active note influence. Explicit `claim_key`/`claim_value` pairs are
checked only against prior active notes with the same claim key. A conflicting
value emits a governed `DecisionRecord` with action `contradict`; prose is not
interpreted as a claim.

Retrieval surfaces are read-only but return a deterministic `receipt` with
`receipt_id`, `snapshot_hash`, query terms, guard fields, returned note IDs,
returned event IDs, and event/materialized counts. The receipt lets downstream
actions prove which notes influenced a decision without writing a retrieval
event into the append-only store. Later captured notes can cite those witnesses
through `retrieval_receipt_refs`, preserving the difference between read-only
retrieval and append-only decision capture. Retrieval receipt references are
validated as bounded `note-retrieval-*` identifiers; arbitrary text is rejected
before persistence. Dashboard and console snapshots derive a read-only
`retrieval_influence` graph from captured events so operators can see which
note event cited which retrieval receipt without adding retrieval events to the
append-only log. The dashboard, CLI dashboard, FastAPI dashboard, and operator
console accept a read-only `retrieval_receipt_ref` filter for narrowing that
graph to one retrieval witness. The filter uses the same bounded
`note-retrieval-*` validation and does not mutate note memory. Filtered
snapshots report `retrieval_influence_count` for the current view and
`retrieval_influence_total_count` for the full unfiltered graph.

Episode capsules write a structured sidecar under the configured note-memory
store and append one `EpisodeCapsule` lineage event. Capsules with
`ProofState.Pass` require verification references, and every capsule requires
evidence references.

The browser-facing `/api/v1/console/note-memory/view` surface renders only the
bounded console read model. It escapes row content and does not expose raw
store paths or mutation controls.

## Dashboard Contract

The canonical operator dashboard contract carries note-memory posture through
`DashboardSnapshot.note_memory`. The typed projection is
`NoteMemorySummary`, derived from the console read model. It carries only
bounded counters and posture fields:

```text
status
extension_state
event_count
active_note_count
rejected_delta_count
expiring_note_count
pending_promotion_count
memory_anchor_count
episode_capsule_count
contradiction_count
retrieval_influence_count
retrieval_influence_total_count
index_proof_state
assessed_at
```

`DashboardEngine.build_note_memory_summary(...)` accepts the console snapshot
shape and rejects negative or non-integer counters before constructing the
dashboard contract.

`mcoi_runtime.app.console.render_note_memory_summary(...)` renders the same
typed summary for text/operator-console surfaces without issuing note-memory
mutations or reading raw storage paths.

## Verification

```text
python -m pytest mcoi/tests/test_note_memory_mesh.py mcoi/tests/test_note_memory_api.py mcoi/tests/test_note_memory_cli.py mcoi/tests/test_note_memory_fastapi_router.py mcoi/tests/test_operator_console.py
python -m pytest mcoi/tests/test_console.py
python -m pytest mcoi/tests/test_dashboard_contracts.py mcoi/tests/test_dashboard_engine.py mcoi/tests/test_dashboard_integration.py
python -m pytest tests/test_note_memory_control_plane_integration.py
```

STATUS:
  Completeness: 100%
  Invariants verified: feature flag boundary, store path requirement, append-only note events, explicit claim contradiction evidence, episode capsule evidence gate, retrieval receipt witness, promotion receipt gate, dashboard snapshot witness, dashboard contract projection, CLI dashboard projection, optional FastAPI dashboard projection, text renderer projection, escaped browser view projection, episode capsule counter projection
  Open issues: none
  Next action: keep the note-memory surface in mullu-control-plane and render DashboardSnapshot.note_memory in any future browser dashboard shell
