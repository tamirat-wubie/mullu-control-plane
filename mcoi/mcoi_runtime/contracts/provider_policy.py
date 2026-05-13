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

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar, cast

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_int

TContract = TypeVar("TContract", bound=ContractRecord)


class ProviderPolicyType(StrEnum):
    HTTP = "http"
    SMTP = "smtp"
    PROCESS = "process"


class PolicyViolationSeverity(StrEnum):
    BLOCKED = "blocked"
    WARNING = "warning"


def _freeze_text_array(values: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[str, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    return frozen


def _freeze_contract_array(
    values: tuple[TContract, ...] | list[TContract],
    field_name: str,
    record_type: type[TContract],
) -> tuple[TContract, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[TContract, ...], freeze_value(list(values)))
    for idx, item in enumerate(frozen):
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return frozen


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
        object.__setattr__(self, "allowed_methods", _freeze_text_array(self.allowed_methods, "allowed_methods"))
        object.__setattr__(
            self,
            "allowed_content_types",
            _freeze_text_array(self.allowed_content_types, "allowed_content_types"),
        )
        require_non_negative_int(self.max_response_bytes, "max_response_bytes")
        require_non_negative_int(self.max_retries, "max_retries")
        if not isinstance(self.retry_enabled, bool):
            raise ValueError("retry_enabled must be a bool")
        if not isinstance(self.require_https, bool):
            raise ValueError("require_https must be a bool")
        object.__setattr__(self, "header_allowlist", _freeze_text_array(self.header_allowlist, "header_allowlist"))


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
        object.__setattr__(
            self,
            "allowed_recipient_domains",
            _freeze_text_array(self.allowed_recipient_domains, "allowed_recipient_domains"),
        )
        require_non_negative_int(self.max_message_bytes, "max_message_bytes")
        if not isinstance(self.attachments_enabled, bool):
            raise ValueError("attachments_enabled must be a bool")
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a bool")


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
        object.__setattr__(self, "command_allowlist", _freeze_text_array(self.command_allowlist, "command_allowlist"))
        object.__setattr__(self, "env_allowlist", _freeze_text_array(self.env_allowlist, "env_allowlist"))
        object.__setattr__(self, "cwd_allowed", _freeze_text_array(self.cwd_allowed, "cwd_allowed"))
        require_non_negative_int(self.max_output_bytes, "max_output_bytes")
        require_non_negative_int(self.timeout_seconds, "timeout_seconds")
        if not isinstance(self.stderr_capture, bool):
            raise ValueError("stderr_capture must be a bool")
        if not isinstance(self.shell_expansion_denied, bool):
            raise ValueError("shell_expansion_denied must be a bool")


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
        if not isinstance(self.expected, str):
            raise ValueError("expected must be a string")
        if not isinstance(self.actual, str):
            raise ValueError("actual must be a string")
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
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a bool")
        object.__setattr__(
            self,
            "violations",
            _freeze_contract_array(self.violations, "violations", ProviderPolicyViolation),
        )
