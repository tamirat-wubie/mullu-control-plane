# Notification provider delivery

v25 adds provider delivery receipts on top of v24 notification delivery clients.

Supported provider labels:

```text
smtp
slack_webhook
github_issue
generic_webhook
manual
```

The provider receipt binds:

```text
provider delivery plan id
client receipt id
provider kind
provider message id
provider response hash
failure list
receipt hash
```

A sent provider receipt must include provider message evidence.
