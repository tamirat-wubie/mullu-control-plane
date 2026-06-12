# Physical consensus compaction

v13 modeled consensus compaction as a decision. v14 adds the guarded physical path.

```text
ConsensusLogCompactionDecision
  → BackupVerificationReport
  → ConsensusCompactionBackupGuard
  → ConsensusPhysicalCompactionPlan
  → ConsensusPhysicalCompactionReport
```

The backup guard stores the backup id/hash and the high-watermark hash from the compaction decision. SQLite can apply the plan by deleting compacted consensus certificates. Apply reports are retained by default, preserving idempotency and retry evidence.

Physical deletion should be used only after the backup manifest has been verified and exported to durable storage.
