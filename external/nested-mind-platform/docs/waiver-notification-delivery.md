# Waiver notification delivery

v22 adds notification plans and receipts for waiver-review assignments.

```text
WaiverReviewerAssignmentPlan
  → WaiverNotificationPlan
  → notification connector
  → WaiverNotificationReceipt
```

Supported channel labels:

```text
email
github_issue
slack
webhook
manual
```

The kernel stores the notification body hash, recipients, provider message id, response hash, and delivery status. It does not store provider credentials.

## API

```text
GET  /system/creative-engineering/waiver-notifications/plans
POST /system/creative-engineering/waiver-notifications/plans
GET  /system/creative-engineering/waiver-notifications/receipts
POST /system/creative-engineering/waiver-notifications/receipts
```

## CLI

```bash
cargo run -p mind-cli -- waiver-notification-delivery \
  ./data/waiver-assignment.json
```
