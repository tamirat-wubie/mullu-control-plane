"""Purpose: canonical provider safety policy contracts.
Governance scope: per-profile provider method/content/size/retry policy typing.
Dependencies: shared contract base helpers.
Invariants:
  - Provider policies are explicit and profile-bound.
  - Unsafe invocations fail closed.
  - Retry is disabled by default.
  - Attachment/expansion is denied by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class ProviderPolicyType(StrEnum):
    HTTP = "http"
    SMTP = "smtp"
    PROCESS = "process"


class PolicyViolationSeverity(StrEnum):
    BLOCKED = "blocked"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class HttpProviderPolicy(ContractRecord):
    """Safety policy for HTTP provider invocations."""

    policy_id: str
    allowed_methods: tuple[str, ...] = ("GET",)
    allowed_content_types: tuple[str, ...] = ("application/json", "text/plain")
    max_response_bytes: int = 1_048_576  # 1 MB
    retry_enabled: bool = False
    max_retries: int = 0
    header_allowlist: tuple[str, ...] = ()
    require_https: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "allowed_methods", freeze_value(list(self.allowed_methods)))
        object.__setattr__(self, "allowed_content_types", freeze_value(list(self.allowed_content_types)))


@dataclass(frozen=True, slots=True)
class SmtpProviderPolicy(ContractRecord):
    """Safety policy for SMTP/email provider invocations."""

    policy_id: str
    allowed_recipient_domains: tuple[str, ...] = ()
    subject_prefix: str | None = None
    max_message_bytes: int = 524_288  # 512 KB
    attachments_enabled: bool = False
    dry_run: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "allowed_recipient_domains", freeze_value(list(self.allowed_recipient_domains)))


@dataclass(frozen=True, slots=True)
class ProcessProviderPolicy(ContractRecord):
    """Safety policy for process/command provider invocations."""

    policy_id: str
    command_allowlist: tuple[str, ...] = ()
    max_output_bytes: int = 1_048_576  # 1 MB
    stderr_capture: bool = True
    env_allowlist: tuple[str, ...] = ()
    cwd_allowed: tuple[str, ...] = ()
    shell_expansion_denied: bool = True
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "command_allowlist", freeze_value(list(self.command_allowlist)))
        object.__setattr__(self, "env_allowlist", freeze_value(list(self.env_allowlist)))
        object.__setattr__(self, "cwd_allowed", freeze_value(list(self.cwd_allowed)))


@dataclass(frozen=True, slots=True)
class ProviderPolicyViolation(ContractRecord):
    """Record of a provider policy violation."""

    violation_id: str
    provider_id: str
    policy_type: ProviderPolicyType
    severity: PolicyViolationSeverity
    field_name: str
    expected: str
    actual: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        if not isinstance(self.policy_type, ProviderPolicyType):
            raise ValueError("policy_type must be a ProviderPolicyType value")
        if not isinstance(self.severity, PolicyViolationSeverity):
            raise ValueError("severity must be a PolicyViolationSeverity value")
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        object.__setattr__(self, "message", require_non_empty_text(self.message, "message"))


@dataclass(frozen=True, slots=True)
class ProviderInvocationCheck(ContractRecord):
    """Result of checking a provider invocation against its policy."""

    provider_id: str
    policy_type: ProviderPolicyType
    allowed: bool
    violations: tuple[ProviderPolicyViolation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        if not isinstance(self.policy_type, ProviderPolicyType):
            raise ValueError("policy_type must be a ProviderPolicyType value")
        object.__setattr__(self, "violations", freeze_value(list(self.violations)))
