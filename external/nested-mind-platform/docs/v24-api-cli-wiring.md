# v24 API and CLI wiring

v24 introduced live secret connector, GitHub token exchange worker, Kubernetes audit-log collector, and notification delivery client kernel objects. v25 wires those objects through runtime surfaces.

New wired surfaces:

```text
/system/secrets/live-connectors/plans
/system/secrets/live-connectors/receipts
/system/github/app/token-exchange/plans
/system/github/app/token-exchange/receipts
/system/creative-engineering/kubernetes-audit-log-collectors/plans
/system/creative-engineering/kubernetes-audit-log-collectors/reports
/system/creative-engineering/notification-delivery-clients/plans
/system/creative-engineering/notification-delivery-clients/receipts
```

New CLI rehearsals:

```bash
cargo run -p mind-cli -- live-secret-connector-demo
cargo run -p mind-cli -- github-token-exchange-worker-demo
cargo run -p mind-cli -- kubernetes-audit-log-collector-demo
cargo run -p mind-cli -- notification-delivery-client-demo ./data/waiver-notification-plan.json
```

These routes and commands persist hash-bound evidence when SQLite is configured. In-memory and JSONL stores still behave as ephemeral local surfaces for those operational ledgers.
