# Governed Swarm Staging Activation Runbook

Purpose: activate and prove the governed swarm invoice route in a staging control-plane environment.
Governance scope: feature flag, runtime release pin, audit persistence, invoice-route smoke test, rollback.
Dependencies: `mullu-control-plane`, `tamirat-wubie/mullu-governed-swarm`, persistent staging storage, deployment operator access.
Invariants: disabled by default; no audit store path means no swarm mount; no runtime path containing `mcoi_runtime/swarm` means no external runtime bridge; no activation claim without a staging activation witness.

## Boundary

This runbook activates the governed swarm surface only for staging. It does not declare public production availability.

Runtime release:

```text
Repository: tamirat-wubie/mullu-governed-swarm
Tag: v0.1.0-governed-swarm
Runtime path after checkout: /opt/mullu/mullu-governed-swarm/mcoi
```

Control-plane environment:

```text
MULLU_ENV=pilot
MULLU_GOVERNED_SWARM_ENABLED=true
MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH=/var/lib/mullu/governed-swarm/swarm-runs.jsonl
MULLU_GOVERNED_SWARM_RUNTIME_PATH=/opt/mullu/mullu-governed-swarm/mcoi
```

## Install Runtime

```bash
mkdir -p /opt/mullu
cd /opt/mullu
git clone https://github.com/tamirat-wubie/mullu-governed-swarm.git
cd mullu-governed-swarm
git checkout v0.1.0-governed-swarm
test -d /opt/mullu/mullu-governed-swarm/mcoi/mcoi_runtime/swarm
```

## Configure Control Plane

```bash
export MULLU_ENV=pilot
export MULLU_GOVERNED_SWARM_ENABLED=true
export MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH=/var/lib/mullu/governed-swarm/swarm-runs.jsonl
export MULLU_GOVERNED_SWARM_RUNTIME_PATH=/opt/mullu/mullu-governed-swarm/mcoi
```

Create the audit directory before restart:

```bash
mkdir -p /var/lib/mullu/governed-swarm
touch /var/lib/mullu/governed-swarm/swarm-runs.jsonl
```

Restart the control plane through the staging deployment mechanism. Do not enable this flag in production until the staging witness validates.

## Smoke Test

Set the staging base URL:

```bash
export MULLU_STAGING_URL=https://staging-api.example.com
```

Create an invoice swarm run:

```bash
curl -sS -X POST "$MULLU_STAGING_URL/api/v1/swarm/invoice-runs" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "staging-invoice-001",
    "vendor_id": "vendor-staging-001",
    "amount": 125.50,
    "currency": "USD",
    "submitted_by": "staging.operator@mullusi.com"
  }'
```

Verify the run can be read back:

```bash
curl -sS "$MULLU_STAGING_URL/api/v1/swarm/runs/<run_id>"
curl -sS "$MULLU_STAGING_URL/api/v1/swarm/runs"
```

Verify audit persistence on the staging host or persistent volume:

```bash
test -s /var/lib/mullu/governed-swarm/swarm-runs.jsonl
tail -n 1 /var/lib/mullu/governed-swarm/swarm-runs.jsonl
```

## Witness

Record the activation result as JSON that validates against:

```text
schemas/governed_swarm_staging_activation_witness.schema.json
```

Example:

```text
docs/governed-swarm-staging-activation-witness-example.json
```

Validate the witness:

```bash
python scripts/validate_governed_swarm_staging_activation_witness.py \
  --witness docs/governed-swarm-staging-activation-witness-example.json
```

Collect a live staging witness:

```bash
python scripts/collect_governed_swarm_staging_activation_witness.py \
  --staging-url "$MULLU_STAGING_URL" \
  --control-plane-commit "<deployed-control-plane-commit>" \
  --runtime-path "/opt/mullu/mullu-governed-swarm/mcoi" \
  --audit-store-path "/var/lib/mullu/governed-swarm/swarm-runs.jsonl" \
  --output ".change_assurance/governed_swarm_staging_activation_witness.json"
```

The same collection can be launched from GitHub Actions:

```text
.github/workflows/governed-swarm-staging-witness.yml
```

Use the default `self-hosted` runner label unless the selected runner can both reach the staging control-plane URL and read `MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH`. A hosted runner can probe the route but cannot prove audit persistence unless the audit JSONL is mounted or otherwise present at the configured path.

Before dispatching the workflow, verify the selected runner has the required local surfaces:

```bash
python scripts/preflight_governed_swarm_staging_runner.py \
  --staging-url "$MULLU_STAGING_URL" \
  --control-plane-commit "<deployed-control-plane-commit>" \
  --runtime-path "/opt/mullu/mullu-governed-swarm/mcoi" \
  --audit-store-path "/var/lib/mullu/governed-swarm/swarm-runs.jsonl" \
  --output ".change_assurance/governed_swarm_staging_runner_preflight.json"
curl -sS "$MULLU_STAGING_URL/api/v1/swarm/runs" >/tmp/governed-swarm-route-preflight.json
```

The workflow repeats the runner preflight and uploads `governed-swarm-staging-runner-preflight` before collecting the witness. If any preflight check fails, do not treat the failure as a route failure; fix runner placement, runtime checkout, audit mount, or staging network access first.

Validate a saved runner preflight receipt:

```bash
python scripts/validate_governed_swarm_staging_runner_preflight.py \
  --receipt ".change_assurance/governed_swarm_staging_runner_preflight.json"
```

Bind the runner preflight and activation witness into one governed staging evidence bundle:

```bash
python scripts/validate_governed_swarm_staging_evidence_bundle.py \
  --runner-preflight ".change_assurance/governed_swarm_staging_runner_preflight.json" \
  --activation-witness ".change_assurance/governed_swarm_staging_activation_witness.json" \
  --bundle-output ".change_assurance/governed_swarm_staging_evidence_bundle.json"
```

The bundle validates against:

```text
schemas/governed_swarm_staging_evidence_bundle.schema.json
```

Example:

```text
docs/governed-swarm-staging-evidence-bundle-example.json
```

The workflow uploads `governed-swarm-staging-evidence-bundle` after both source artifacts validate and cross-checks the deployed commit, runtime path, audit path, staging URL, runner readiness, and terminal activation outcome.

For a real staging activation, store the collected witness under `.change_assurance/` or the deployment evidence store, then run the same validator against that file.

## Rollback

Rollback is one environment change and one restart:

```bash
export MULLU_GOVERNED_SWARM_ENABLED=false
```

After restart, verify the route surface is gone or blocked:

```bash
curl -sS -o /tmp/swarm-disabled.out -w "%{http_code}" \
  "$MULLU_STAGING_URL/api/v1/swarm/runs"
```

Expected rollback result:

```text
404 or another governed disabled-route response
```

Do not delete `MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH` during rollback. The audit file is evidence and must remain append-only.

STATUS:
  Completeness: 100%
  Invariants verified: [release pin named, feature flags named, smoke route named, audit receipt required, runner preflight bound, staging evidence bundle bound, rollback preserves audit evidence]
  Open issues: [real staging endpoint must provide the collected witness]
  Next action: execute this runbook in staging and validate the collected witness.
