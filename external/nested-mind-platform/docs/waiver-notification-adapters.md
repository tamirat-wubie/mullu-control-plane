# Waiver notification adapters

v23 turns waiver notification delivery into provider-specific adapter evidence.

```text
WaiverNotificationPlan
  → WaiverNotificationAdapterPlan
  → provider delivery
  → WaiverNotificationAdapterReceipt
```

Adapters represented by the kernel:

```text
email_smtp
slack_webhook
github_issue
generic_webhook
manual
```

Secrets, endpoints, and raw provider tokens stay outside the kernel. The kernel accepts only endpoint references, template hashes, provider message IDs, provider response hashes, and failure lists.
