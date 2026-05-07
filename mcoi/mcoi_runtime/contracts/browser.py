"""Purpose: canonical browser/app workflow automation contracts.
Governance scope: browser session, page, selector, action, observation, and verification typing.
Dependencies: shared contract base helpers.
Invariants:
  - Browser actions are bounded and governed by the same autonomy/approval rules.
  - Selector mismatches fail closed — no fallback to guessed elements.
  - Observations are read-only typed snapshots, never mutations.
  - Verification compares expected state against actual after action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class BrowserSessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


class BrowserActionType(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SUBMIT = "submit"
    SELECT = "select"
    WAIT = "wait"
    SCROLL = "scroll"
    READ = "read"


class SelectorMatchStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


class BrowserVerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ELEMENT_MISSING = "element_missing"
    VALUE_MISMATCH = "value_mismatch"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class BrowserSession(ContractRecord):
    """A governed browser session with explicit identity and lifecycle."""

    session_id: str
    status: BrowserSessionStatus
    base_url: str | None = None
    current_url: str | None = None
    page_title: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        if not isinstance(self.status, BrowserSessionStatus):
            raise ValueError("status must be a BrowserSessionStatus value")
        if self.created_at is not None:
            object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))

    @property
    def is_active(self) -> bool:
        return self.status is BrowserSessionStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class ElementSelector(ContractRecord):
    """A typed reference to a page element."""

    selector_type: str
    selector_value: str
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "selector_type", require_non_empty_text(self.selector_type, "selector_type"))
        object.__setattr__(self, "selector_value", require_non_empty_text(self.selector_value, "selector_value"))


@dataclass(frozen=True, slots=True)
class SelectorMatchResult(ContractRecord):
    """Result of attempting to locate an element on the page."""

    selector: ElementSelector
    status: SelectorMatchStatus
    element_text: str | None = None
    element_value: str | None = None
    element_tag: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, ElementSelector):
            raise ValueError("selector must be an ElementSelector instance")
        if not isinstance(self.status, SelectorMatchStatus):
            raise ValueError("status must be a SelectorMatchStatus value")

    @property
    def found(self) -> bool:
        return self.status is SelectorMatchStatus.FOUND


@dataclass(frozen=True, slots=True)
class PageDescriptor(ContractRecord):
    """Typed snapshot of a page's observable state."""

    url: str
    title: str
    elements: tuple[SelectorMatchResult, ...] = ()
    text_content: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", require_non_empty_text(self.url, "url"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "elements", freeze_value(list(self.elements)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class BrowserAction(ContractRecord):
    """A bounded browser action with typed parameters."""

    action_id: str
    action_type: BrowserActionType
    selector: ElementSelector | None = None
    value: str | None = None
    url: str | None = None
    wait_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        if not isinstance(self.action_type, BrowserActionType):
            raise ValueError("action_type must be a BrowserActionType value")


@dataclass(frozen=True, slots=True)
class BrowserActionResult(ContractRecord):
    """Result of executing a browser action."""

    action_id: str
    succeeded: bool
    selector_match: SelectorMatchResult | None = None
    page_after: PageDescriptor | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))


@dataclass(frozen=True, slots=True)
class BrowserObservation(ContractRecord):
    """A read-only observation of browser/page state."""

    observation_id: str
    session_id: str
    page: PageDescriptor
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", require_non_empty_text(self.observation_id, "observation_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        if not isinstance(self.page, PageDescriptor):
            raise ValueError("page must be a PageDescriptor instance")
        require_datetime_text(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class BrowserVerificationResult(ContractRecord):
    """Result of verifying page state after a browser action."""

    verification_id: str
    action_id: str
    status: BrowserVerificationStatus
    expected_selector: ElementSelector | None = None
    expected_value: str | None = None
    actual_value: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        if not isinstance(self.status, BrowserVerificationStatus):
            raise ValueError("status must be a BrowserVerificationStatus value")

    @property
    def passed(self) -> bool:
        return self.status is BrowserVerificationStatus.PASS
