# Waiver review flow

v20 adds a review queue and certificate for readiness waivers.

```text
ReadinessWaiverProposal
  → WaiverReviewQueueItem
  → WaiverReviewComment[]
  → WaiverReviewCertificate
```

The certificate verifies:

```text
proposal id
review id
blocker ids
required reviewer roles
comment hashes
final status
```

Statuses:

```text
open
changes_requested
approved
rejected
expired
```

This is separate from the multi-operator waiver certificate. The review flow is intended to support operator UX, discussion, and role-specific comments before a waiver is treated as ready for staging.

CLI:

```bash
cargo run -p mind-cli -- waiver-review-demo ./data/readiness-gate.json
```

API:

```text
GET  /system/creative-engineering/waiver-reviews
POST /system/creative-engineering/waiver-reviews
```
