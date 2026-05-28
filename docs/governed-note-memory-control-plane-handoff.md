# Governed Note-Memory Control-Plane Handoff

Purpose: bind temporary execution notes and durable memory anchors to the
canonical `mullu-control-plane` repository.
Governance scope: note capture, retrieval guards, rejected-delta evidence,
promotion receipts, and optional HTTP route mounting.
Dependencies: `mcoi_runtime.core.note_memory_*` modules and
`mcoi_runtime.app.note_memory_integration`.
Invariants: temporary notes require expiry, durable anchors require accepted
promotion receipts, and HTTP mounting is disabled unless explicitly configured.

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
POST /api/v1/notes/retrieve
POST /api/v1/notes/expire
POST /api/v1/notes/promotions
POST /api/v1/notes/anchors
POST /api/v1/notes/index/rebuild
GET  /api/v1/notes/events
GET  /api/v1/console/note-memory
```

The operator console route is read-only. It returns the same stable summary
shape when note memory is disabled, unregistered, unmounted, or mounted without
a configured store path. Rejected deltas, pending promotions, memory anchors,
contradictions, and audit events are separated so rejected evidence is not
counted as active note influence.

## Verification

```text
python -m pytest mcoi/tests/test_note_memory_mesh.py mcoi/tests/test_note_memory_api.py mcoi/tests/test_note_memory_cli.py mcoi/tests/test_note_memory_fastapi_router.py mcoi/tests/test_operator_console.py
python -m pytest tests/test_note_memory_control_plane_integration.py
```

STATUS:
  Completeness: 100%
  Invariants verified: feature flag boundary, store path requirement, append-only note events, promotion receipt gate
  Open issues: none
  Next action: keep the note-memory surface in mullu-control-plane and supersede extracted governed-swarm PRs
