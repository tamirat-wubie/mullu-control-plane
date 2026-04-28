"""Policy engines — definition, enforcement, simulation, versioning.

Modules:
  - ``engine`` — :class:`PolicyEngine`, decision factory,
    policy input/reason/status contracts
  - ``enforcement`` — privilege elevation, session lifecycle,
    revocation, step-up auth
  - ``provider`` — per-provider policy (HTTP, SMTP, process)
    enforced at the connector layer
  - ``sandbox`` — policy simulation sandbox
  - ``simulation`` — policy diff + adoption analysis
  - ``versioning`` — policy version registry + shadow
    evaluation against current policy
  - ``shell`` — shell command policy (used by the shell
    sandbox in pilot/production environments)
"""
