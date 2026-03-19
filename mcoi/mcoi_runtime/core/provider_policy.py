"""Purpose: provider policy enforcement — check invocations against safety policies.
Governance scope: provider safety policy evaluation only.
Dependencies: provider policy contracts, invariant helpers.
Invariants:
  - Policy violations fail closed (blocked by default).
  - No hidden retry or fallback.
  - Shell expansion is denied unless explicitly allowed.
  - Every check produces a typed result.
"""

from __future__ import annotations

from mcoi_runtime.contracts.provider_policy import (
    HttpProviderPolicy,
    PolicyViolationSeverity,
    ProcessProviderPolicy,
    ProviderInvocationCheck,
    ProviderPolicyType,
    ProviderPolicyViolation,
    SmtpProviderPolicy,
)
from .invariants import stable_identifier


class ProviderPolicyEnforcer:
    """Checks provider invocations against their safety policies."""

    def check_http(
        self,
        policy: HttpProviderPolicy,
        *,
        provider_id: str,
        method: str,
        url: str,
        content_type: str | None = None,
        response_size: int | None = None,
    ) -> ProviderInvocationCheck:
        violations: list[ProviderPolicyViolation] = []

        if method.upper() not in [m.upper() for m in policy.allowed_methods]:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.HTTP,
                "method", str(policy.allowed_methods), method,
                f"HTTP method {method} not in allowlist",
            ))

        if policy.require_https and not url.startswith("https://"):
            violations.append(self._violation(
                provider_id, ProviderPolicyType.HTTP,
                "url_scheme", "https", url[:8],
                "HTTPS required but URL does not use HTTPS",
            ))

        if content_type and content_type not in policy.allowed_content_types:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.HTTP,
                "content_type", str(policy.allowed_content_types), content_type,
                f"content type {content_type} not in allowlist",
            ))

        if response_size is not None and response_size > policy.max_response_bytes:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.HTTP,
                "response_size", str(policy.max_response_bytes), str(response_size),
                f"response size {response_size} exceeds max {policy.max_response_bytes}",
            ))

        return ProviderInvocationCheck(
            provider_id=provider_id,
            policy_type=ProviderPolicyType.HTTP,
            allowed=len(violations) == 0,
            violations=tuple(violations),
        )

    def check_smtp(
        self,
        policy: SmtpProviderPolicy,
        *,
        provider_id: str,
        recipient: str,
        subject: str = "",
        message_size: int = 0,
        has_attachment: bool = False,
    ) -> ProviderInvocationCheck:
        violations: list[ProviderPolicyViolation] = []

        if policy.allowed_recipient_domains:
            domain = recipient.split("@")[-1] if "@" in recipient else ""
            if domain not in policy.allowed_recipient_domains:
                violations.append(self._violation(
                    provider_id, ProviderPolicyType.SMTP,
                    "recipient_domain", str(policy.allowed_recipient_domains), domain,
                    f"recipient domain {domain} not in allowlist",
                ))

        if policy.subject_prefix and not subject.startswith(policy.subject_prefix):
            violations.append(self._violation(
                provider_id, ProviderPolicyType.SMTP,
                "subject_prefix", policy.subject_prefix, subject[:len(policy.subject_prefix)] if subject else "(empty)",
                f"subject does not start with required prefix '{policy.subject_prefix}'",
            ))

        if message_size > policy.max_message_bytes:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.SMTP,
                "message_size", str(policy.max_message_bytes), str(message_size),
                f"message size {message_size} exceeds max {policy.max_message_bytes}",
            ))

        if has_attachment and not policy.attachments_enabled:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.SMTP,
                "attachments", "disabled", "attachment_present",
                "attachments are not enabled for this provider",
            ))

        return ProviderInvocationCheck(
            provider_id=provider_id,
            policy_type=ProviderPolicyType.SMTP,
            allowed=len(violations) == 0,
            violations=tuple(violations),
        )

    def check_process(
        self,
        policy: ProcessProviderPolicy,
        *,
        provider_id: str,
        command: str,
        cwd: str | None = None,
        env_vars: tuple[str, ...] = (),
        uses_shell_expansion: bool = False,
    ) -> ProviderInvocationCheck:
        violations: list[ProviderPolicyViolation] = []

        if policy.command_allowlist:
            cmd_base = command.split()[0] if command.strip() else ""
            if cmd_base not in policy.command_allowlist:
                violations.append(self._violation(
                    provider_id, ProviderPolicyType.PROCESS,
                    "command", str(policy.command_allowlist), cmd_base,
                    f"command {cmd_base} not in allowlist",
                ))

        if uses_shell_expansion and policy.shell_expansion_denied:
            violations.append(self._violation(
                provider_id, ProviderPolicyType.PROCESS,
                "shell_expansion", "denied", "expansion_used",
                "shell expansion is denied by policy",
            ))

        if cwd and policy.cwd_allowed:
            if not any(cwd.startswith(allowed) for allowed in policy.cwd_allowed):
                violations.append(self._violation(
                    provider_id, ProviderPolicyType.PROCESS,
                    "cwd", str(policy.cwd_allowed), cwd,
                    f"working directory {cwd} not in allowed list",
                ))

        if policy.env_allowlist:
            for var in env_vars:
                if var not in policy.env_allowlist:
                    violations.append(self._violation(
                        provider_id, ProviderPolicyType.PROCESS,
                        "env_var", str(policy.env_allowlist), var,
                        f"environment variable {var} not in allowlist",
                    ))

        return ProviderInvocationCheck(
            provider_id=provider_id,
            policy_type=ProviderPolicyType.PROCESS,
            allowed=len(violations) == 0,
            violations=tuple(violations),
        )

    def _violation(
        self,
        provider_id: str,
        policy_type: ProviderPolicyType,
        field_name: str,
        expected: str,
        actual: str,
        message: str,
    ) -> ProviderPolicyViolation:
        return ProviderPolicyViolation(
            violation_id=stable_identifier("prov-violation", {"provider_id": provider_id, "field": field_name}),
            provider_id=provider_id,
            policy_type=policy_type,
            severity=PolicyViolationSeverity.BLOCKED,
            field_name=field_name,
            expected=expected,
            actual=actual,
            message=message,
        )
