# Governed Swarm Invoice Workflow

Purpose: document the S2 supervisor-led swarm capability for bounded invoice work.
Governance scope: agent identity, task leases, WHQR claims, MIL verification, audit persistence, and closure proof.
Dependencies: `mcoi_runtime.swarm`.
Invariants: specialist agents emit claims only; side effects require MIL verification and human approval.

## Architecture

The governed swarm fabric implements universal work decomposition, not universal authority.

```text
invoice request
  -> InvoiceSwarmRuntime
  -> SupervisorAgent
  -> fixed specialist agents
  -> WHQR claims
  -> conflict and quorum checks
  -> MIL static verification
  -> append-only audit record
  -> closure certificate when proof passes
```

Specialists used by the invoice workflow:

| Agent | Role | Capability |
| --- | --- | --- |
| `document_agent_v1` | document analysis | `invoice.read` |
| `vendor_agent_v1` | vendor analysis | `vendor.verify` |
| `finance_agent_v1` | finance analysis | `ledger.query` |
| `budget_agent_v1` | budget analysis | `budget.check` |
| `policy_agent_v1` | policy analysis | `policy.check` |
| `risk_agent_v1` | risk analysis | `risk.classify` |
| `verifier_agent_v1` | verifier analysis | `proof.verify` |

## Invariants

1. No anonymous swarm agent.
2. No task work without a lease.
3. No specialist receives side-effect authority.
4. No payment dispatch appears unless closure exists and human approval is present.
5. Unknown budget or missing approval escalates instead of closing.
6. Duplicate invoice or unverified vendor fails instead of closing.
7. Every accepted runtime run is persisted as a JSONL audit record.
8. Closed records carry a proof stamp.

## CLI Usage

Run a closed invoice workflow:

```powershell
$env:PYTHONPATH='.;mcoi'
python -m mcoi_runtime.swarm.cli --audit-store .\tmp\swarm-runs.jsonl run-invoice .\examples\governed_swarm\invoice_closed.json
```

After installing the scoped package from `mcoi/`, the same command is available as:

```powershell
mcoi-swarm --audit-store .\tmp\swarm-runs.jsonl run-invoice .\examples\governed_swarm\invoice_closed.json
```

Read one run:

```powershell
$env:PYTHONPATH='.;mcoi'
python -m mcoi_runtime.swarm.cli --audit-store .\tmp\swarm-runs.jsonl get-run run_invoice_closed_001
```

List runs:

```powershell
$env:PYTHONPATH='.;mcoi'
python -m mcoi_runtime.swarm.cli --audit-store .\tmp\swarm-runs.jsonl list-runs
```

## FastAPI Route Contract

`create_fastapi_router(runtime)` is optional and imports FastAPI only when a host app creates the router.

| Method | Path | Handler |
| --- | --- | --- |
| `POST` | `/api/v1/swarm/invoice-runs` | `run_invoice` |
| `GET` | `/api/v1/swarm/runs/{run_id}` | `get_run` |
| `GET` | `/api/v1/swarm/runs` | `list_runs` |

Host wiring:

```python
from pathlib import Path

from fastapi import FastAPI
from mcoi_runtime.swarm import InvoiceSwarmRuntime, create_fastapi_router

app = FastAPI()
runtime = InvoiceSwarmRuntime.from_path(Path("tmp/swarm-runs.jsonl"))
app.include_router(create_fastapi_router(runtime))
```

In the larger control-plane app, the router is mounted only when explicitly enabled:

```powershell
$env:MULLU_GOVERNED_SWARM_ENABLED='true'
$env:MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH='C:\tmp\mullu-control-plane\swarm-runs.jsonl'
$env:MULLU_GOVERNED_SWARM_RUNTIME_PATH='C:\Users\tmrtl\Projects\Agentic framwork and computer uses inteligence\mcoi'
```

## Request Contract

```json
{
  "run_id": "run_invoice_closed_001",
  "goal_id": "goal_invoice_closed_001",
  "tenant_id": "tenant_a",
  "invoice_ref": "invoice_001",
  "invoice_amount_usd": "1250.00",
  "vendor_verified": true,
  "duplicate_found": false,
  "budget_available": true,
  "policy_requires_approval": true,
  "human_approved": true
}
```

## Outcome Patterns

| Input condition | Decision | Closure | MIL payment dispatch |
| --- | --- | --- | --- |
| vendor verified, no duplicate, budget available, approval present | `passed` | `closed` | present |
| approval required but missing | `escalate` | `not_closed` | absent |
| budget unavailable | `escalate` | `not_closed` | absent |
| duplicate found | `failed` | `not_closed` | absent |
| vendor not verified | `failed` | `not_closed` | absent |

## Proof Surface

Each persisted record contains:

1. `decision_verdict`
2. `decision_reason`
3. `verification_passed`
4. `mil_verification_passed`
5. `closure_status`
6. `proof_stamp`
7. `payload.plan`
8. `payload.decision`
9. `payload.receipts`
10. `payload.mil_program`
11. `payload.closure`

Closed records must include a non-empty `proof_stamp`. Escalated or failed records must remain `not_closed`.
