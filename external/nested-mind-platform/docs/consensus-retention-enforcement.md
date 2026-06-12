# Consensus Retention Enforcement

v13 modeled consensus compaction decisions. v14 added backup-guarded physical certificate deletion. v15 adds retention policy enforcement for all consensus evidence classes.

```text
ConsensusLogCompactionDecision
  → ConsensusPhysicalCompactionPlan
  → ConsensusRetentionPolicy
  → ConsensusRetentionEnforcementPlan
  → ConsensusRetentionEnforcementReport
```

Evidence classes:

```text
commit_certificate
apply_report
idempotency_decision
compaction_decision
physical_compaction_report
```

Default policy:

```text
require_backup_guard = true
delete_commit_certificates = true
delete_apply_reports = false
preserve_rejected_apply_reports = true
keep_latest_apply_reports = 128
```

Deleting apply reports is possible only through an explicit retention policy. Idempotency decisions, compaction decisions, and physical compaction reports are preserved by default.

## API

```text
GET  /system/consensus/log/retention-enforcements
POST /system/consensus/log/retention/enforce
```

## CLI

```bash
cargo run -p mind-cli -- consensus-retention-enforce \
  ./data/consensus-compaction-decision.json \
  ./data/backup-verification.json \
  ./data/apply-reports.json \
  plan
```
