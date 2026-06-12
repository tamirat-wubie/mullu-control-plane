# Worker daemon

The worker daemon is the always-on operational process for scheduled jobs. It reads from SQLite, claims due jobs through a compare-and-swap update, writes scheduler leases, and records `WorkerDaemonTickReport` objects.

The daemon does not mutate symbolic mind state directly. It only executes operational jobs whose effects must later be represented as receipts, commits, reports, or verified event records.

```bash
export MIND_EVENT_DB=./data/mind-events.sqlite
export MIND_WORKER_ID=worker-a
export MIND_WORKER_MODE=plan
export MIND_WORKER_MAX_TICKS=0
cargo run -p mind-worker
```

Modes:

```text
plan                       claim and record work without marking success
execute                    mark claimed jobs succeeded after receipt-shaped execution
```

Production rule: `execute` mode should be used only after job handlers produce hash-bound receipts for the external side effect.
