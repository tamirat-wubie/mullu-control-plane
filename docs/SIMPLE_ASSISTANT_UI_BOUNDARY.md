# Simple Assistant UI Boundary

Purpose: define the normal-user projection boundary that keeps governance proof depth internal while exposing simple outcome, approval, and safety states.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: `schemas/simple_assistant_ui_boundary.schema.json`, `examples/simple_assistant_ui_boundary.foundation.json`, `scripts/validate_simple_assistant_ui_boundary.py`.
Invariants: heavy governance remains internal; normal users approve outcomes; auditors inspect proof through explicit detail views; no execution authority is granted by the projection.

## Architecture

| Level | Audience | Visible surface | Hidden by default |
| --- | --- | --- | --- |
| 1 | normal user | simple status, risk label, approval prompt, result label | proof matrices, receipt schemas, protocol counts, lifecycle state, raw witness refs |
| 2 | operator | receipts, blocked reasons, component path, audit detail link | raw secrets and irrelevant implementation internals |
| 3 | auditor/developer | proof matrix, schemas, witnesses, governance traces | nothing needed for authorized audit except secrets |

## Boundary Rule

```text
Heavy governance inside.
Simple experience outside.
```

Normal-user surfaces may show only bounded status language:

```text
Ready
Needs approval
Blocked for safety
Draft created
Sent after approval
Evidence saved
```

The UI can expose `View audit details`, but the detail view must require a higher visibility level. The normal-user surface must not serialize internal terms such as proof matrix, WHQR, lifecycle state, receipt schema, protocol manifest count, operator evidence boundary, or temporal retention certificate hash.

## Email Action Example

```text
Draft ready.

Risk: external message
Approval needed: yes

[Approve Send] [Edit Draft] [Cancel]
```

## Validation

Run:

```powershell
python scripts\validate_simple_assistant_ui_boundary.py
python -m pytest tests\test_validate_simple_assistant_ui_boundary.py -q
```
