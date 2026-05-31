"""Purpose: redact sensitive values from governed browser observations.
Governance scope: masking of secret-bearing element values, page text, and
URL or metadata values only.
Dependencies: browser contracts and Python regular expressions.
Invariants:
  - Redaction is fail-safe: when in doubt, mask rather than expose.
  - Masking never grows or invents structure; it only replaces values.
  - Selector identity, status, tags, title, URL host/path, and metadata keys are preserved.
  - Redaction is deterministic; same input yields same masked output.
  - No floats and no numeric decisioning; string classification only.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from mcoi_runtime.contracts.browser import (
    PageDescriptor,
    SelectorMatchResult,
)

# Keyword fragments that mark a selector, description, or metadata key as
# secret-bearing. Matched case-insensitively as substrings so names like
# `#password`, `login_pwd`, `name=otp-code`, and `Credit Card Number` classify
# as sensitive.
_DEFAULT_FIELD_KEYWORDS: tuple[str, ...] = (
    "password",
    "passwd",
    "pwd",
    "otp",
    "mfa",
    "2fa",
    "cvv",
    "cvc",
    "card",
    "creditcard",
    "ssn",
    "secret",
    "token",
    "apikey",
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "cookie",
    "set-cookie",
    "pin",
    "passcode",
    "security_code",
    "securitycode",
    "account_number",
    "routing",
    "private_key",
    "privatekey",
)

_SECRET_URL_PARAM_FRAGMENTS: tuple[str, ...] = _DEFAULT_FIELD_KEYWORDS + (
    "auth",
    "code",
    "key",
    "session",
    "sessionid",
    "sid",
    "sig",
    "signature",
)

# Value-shaped patterns scrubbed from free page text regardless of selector.
# Card-like: 13-19 digits in groups separated by space or dash.
_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# US SSN-like: 3-2-4 digit groups separated by dash or space.
_SSN_PATTERN = re.compile(r"\b\d{3}[ -]\d{2}[ -]\d{4}\b")


@dataclass(frozen=True, slots=True)
class SensitivityPolicy:
    """Declarative policy describing which browser values must be masked."""

    field_keywords: tuple[str, ...] = _DEFAULT_FIELD_KEYWORDS
    mask: str = "[REDACTED]"
    scrub_page_text: bool = True

    def __post_init__(self) -> None:
        if not self.mask:
            raise ValueError("mask must be a non-empty string")
        object.__setattr__(
            self,
            "field_keywords",
            tuple(keyword.lower() for keyword in self.field_keywords),
        )


DEFAULT_SENSITIVITY_POLICY = SensitivityPolicy()


def _haystack(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).lower()


def is_sensitive_selector(
    selector_type: str | None,
    selector_value: str | None,
    description: str | None = None,
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> bool:
    """Return True when the selector identity indicates a secret-bearing field."""
    text = _haystack(selector_type, selector_value, description)
    if not text:
        return False
    return any(keyword in text for keyword in policy.field_keywords)


def scrub_text(
    text: str | None,
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> str | None:
    """Replace value-shaped secrets (card / SSN patterns) in free text."""
    if text is None or not policy.scrub_page_text:
        return text
    scrubbed = _CARD_PATTERN.sub(policy.mask, text)
    scrubbed = _SSN_PATTERN.sub(policy.mask, scrubbed)
    return scrubbed


def _is_secret_url_param(name: str) -> bool:
    lowered = name.lower()
    return any(fragment in lowered for fragment in _SECRET_URL_PARAM_FRAGMENTS)


def _redact_url_query(query: str, *, policy: SensitivityPolicy) -> str:
    if "=" not in query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    redacted = [
        (name, policy.mask if _is_secret_url_param(name) else value)
        for name, value in pairs
    ]
    return urlencode(redacted)


def _redact_url_netloc_userinfo(netloc: str, *, policy: SensitivityPolicy) -> str:
    if "@" not in netloc:
        return netloc
    _, host_port = netloc.rsplit("@", 1)
    return f"{quote(policy.mask, safe='')}@{host_port}"


def redact_url(
    url: str,
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> str:
    """Mask URL userinfo and secret-bearing query or fragment parameters."""
    if not url or ("=" not in url and "@" not in url):
        return url
    try:
        scheme, netloc, path, query, fragment = urlsplit(url)
    except ValueError:
        return url
    return urlunsplit((
        scheme,
        _redact_url_netloc_userinfo(netloc, policy=policy),
        path,
        _redact_url_query(query, policy=policy),
        _redact_url_query(fragment, policy=policy),
    ))


def redact_metadata(
    metadata: Mapping[str, Any],
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> Mapping[str, Any]:
    """Return metadata with secret-bearing values masked recursively."""

    return {
        key: _redact_metadata_value(
            value,
            key_hint=str(key),
            policy=policy,
            force_mask=is_sensitive_selector("metadata", str(key), policy=policy),
        )
        for key, value in metadata.items()
    }


def _redact_metadata_value(
    value: Any,
    *,
    key_hint: str,
    policy: SensitivityPolicy,
    force_mask: bool,
) -> Any:
    if isinstance(value, Mapping):
        return {
            item_key: _redact_metadata_value(
                item_value,
                key_hint=str(item_key),
                policy=policy,
                force_mask=force_mask
                or is_sensitive_selector(
                    "metadata",
                    str(item_key),
                    key_hint,
                    policy=policy,
                ),
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(
            _redact_metadata_value(
                item,
                key_hint=key_hint,
                policy=policy,
                force_mask=force_mask,
            )
            for item in value
        )
    if isinstance(value, list):
        return [
            _redact_metadata_value(
                item,
                key_hint=key_hint,
                policy=policy,
                force_mask=force_mask,
            )
            for item in value
        ]
    if force_mask:
        return _mask_scalar(value, policy=policy)
    if isinstance(value, str):
        return scrub_text(value, policy=policy)
    return value


def _mask_scalar(value: Any, *, policy: SensitivityPolicy) -> Any:
    if value is None or value == "":
        return value
    return policy.mask


def redact_selector_match(
    match: SelectorMatchResult,
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> SelectorMatchResult:
    """Mask the value/text of a match when its selector is secret-bearing."""
    selector = match.selector
    if not is_sensitive_selector(
        selector.selector_type,
        selector.selector_value,
        selector.description,
        policy=policy,
    ):
        return match
    return SelectorMatchResult(
        selector=selector,
        status=match.status,
        element_text=policy.mask if match.element_text else match.element_text,
        element_value=policy.mask if match.element_value else match.element_value,
        element_tag=match.element_tag,
    )


def redact_page(
    page: PageDescriptor,
    *,
    policy: SensitivityPolicy = DEFAULT_SENSITIVITY_POLICY,
) -> PageDescriptor:
    """Return a page with secret-bearing element values, text, and metadata masked."""
    redacted_elements = tuple(
        redact_selector_match(element, policy=policy) for element in page.elements
    )
    return PageDescriptor(
        url=redact_url(page.url, policy=policy),
        title=page.title,
        elements=redacted_elements,
        text_content=scrub_text(page.text_content, policy=policy),
        metadata=redact_metadata(page.metadata, policy=policy),
    )
