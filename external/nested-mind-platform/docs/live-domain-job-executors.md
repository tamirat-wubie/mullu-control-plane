# Live domain job executors

v16 upgrades generic worker receipts into live domain-executor reports.

```text
ScheduledJob
  → live executor registry
  → domain payload validation
  → JobExecutionReceipt
  → DomainJobExecutionReport
  → LiveDomainJobExecutionReport
  → evidence records
```

The live executor registry does not let job handlers silently mutate kernel state. It binds each job kind to an execution boundary:

```text
local deterministic simulation
provider receipt boundary
external gateway boundary
```

The worker now records both the prior domain report and a live report. The live report contains evidence records keyed by the required evidence declared by the domain handler.

## Runtime endpoints

```text
GET  /system/worker/live-domain-job-reports
POST /system/worker/live-domain-jobs/execute
```

## CLI

```bash
cargo run -p mind-cli -- live-domain-job-execute-json ./data/job.json worker-a plan
cargo run -p mind-cli -- live-domain-job-execute-json ./data/job.json worker-a local
cargo run -p mind-cli -- live-domain-job-execute-json ./data/job.json worker-a receipt
```

## Governance rule

A job executor may produce evidence, but evidence is not equivalent to symbolic state mutation. State mutation still flows through governed commits and append-only event records.
