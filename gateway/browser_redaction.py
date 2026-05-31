"""Gateway Browser Redaction - mask secrets in browser worker observations.

Purpose: strip secret-bearing query parameters and value-shaped secrets from
browser observations before they enter signed receipts and worker responses.
Governance scope: redaction of extracted text, observed network/navigation URLs.
Dependencies: gateway.browser_worker contracts; standard library only.
Invariants:
  - Redaction preserves URL scheme, host, and path so domain allowlist checks
    and receipts stay meaningful; only secret query/fragment values are masked.
  - Masking is fail-safe and deterministic; unparseable URLs are returned as-is.
  - No floats and no numeric decisioning — string classification only.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    from gateway.browser_worker import BrowserActionObservation

MASK = "[REDACTED]"

# Query/fragment parameter name fragments that mark a value as secret-bearing.
# Matched case-insensitively as substrings: `access_token`, `X-Api-Key`,
# `oauth_signature`, and `client_secret` all classify as sensitive.
_SECRET_PARAM_FRAGMENTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "session",
    "sessionid",
    "sid",
    "otp",
    "code",
    "pin",
    "sig",
    "signature",
    "credential",
    "account",
    "card",
    "cvv",
    "ssn",
    "key",
)

# Value-shaped secrets scrubbed from extracted page text.
_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}[ -]\d{2}[ -]\d{4}\b")


def _is_secret_param(name: str) -> bool:
    lowered = name.lower()
    return any(fragment in lowered for fragment in _SECRET_PARAM_FRAGMENTS)


def _redact_query(query: str) -> str:
    if "=" not in query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    redacted = [
        (name, MASK if _is_secret_param(name) else value) for name, value in pairs
    ]
    return urlencode(redacted)


def redact_url_query_secrets(url: str) -> str:
    """Mask secret query/fragment values in a URL, preserving host and path."""
    if not url or "=" not in url:
        return url
    try:
        scheme, netloc, path, query, fragment = urlsplit(url)
    except ValueError:
        return url
    new_query = _redact_query(query)
    new_fragment = _redact_query(fragment)
    return urlunsplit((scheme, netloc, path, new_query, new_fragment))


def redact_text_secrets(text: str) -> str:
    """Mask value-shaped secrets (card / SSN patterns) in free text."""
    if not text:
        return text
    scrubbed = _CARD_PATTERN.sub(MASK, text)
    scrubbed = _SSN_PATTERN.sub(MASK, scrubbed)
    return scrubbed


def redact_observation(observation: BrowserActionObservation) -> BrowserActionObservation:
    """Return an observation with secret-bearing URLs and text masked."""
    return replace(
        observation,
        url_before=redact_url_query_secrets(observation.url_before),
        url_after=redact_url_query_secrets(observation.url_after),
        extracted_text=redact_text_secrets(observation.extracted_text),
        network_requests=tuple(
            redact_url_query_secrets(url) for url in observation.network_requests
        ),
    )
