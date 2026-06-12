# Notification delivery clients

v24 adds client-level evidence for provider-specific waiver notifications.

```text
WaiverNotificationAdapterPlan
  → NotificationDeliveryClientPlan
  → provider delivery
  → WaiverNotificationAdapterReceipt
  → NotificationDeliveryClientReceipt
```

Supported adapter kinds are inherited from the waiver notification adapter layer:

```text
email_smtp
slack_webhook
github_issue
generic_webhook
manual
```

## Invariants

```text
+ delivery plan binds adapter plan id
+ delivery receipt binds adapter receipt id
+ sent status requires provider message id
+ idempotency key is derived from adapter plan, endpoint, and request template
```

## SQLite ledgers

```text
notification_delivery_client_plans
notification_delivery_client_receipts
```
