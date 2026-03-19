"""Purpose: browser/app workflow core — governed session, actions, and verification.
Governance scope: browser session lifecycle, action execution, and state verification only.
Dependencies: browser contracts, invariant helpers.
Invariants:
  - Sessions are explicitly opened and closed.
  - Read-first: observation must precede mutation.
  - Selector mismatches fail closed — no fallback guessing.
  - Verification compares expected vs actual state deterministically.
  - Actions on closed sessions fail immediately.
"""

from __future__ import annotations

from typing import Callable, Protocol

from mcoi_runtime.contracts.browser import (
    BrowserAction,
    BrowserActionResult,
    BrowserActionType,
    BrowserObservation,
    BrowserSession,
    BrowserSessionStatus,
    BrowserVerificationResult,
    BrowserVerificationStatus,
    ElementSelector,
    PageDescriptor,
    SelectorMatchResult,
    SelectorMatchStatus,
)
from .invariants import ensure_non_empty_text, stable_identifier


class BrowserBackend(Protocol):
    """Protocol for browser backend implementations."""

    def open_page(self, url: str) -> PageDescriptor: ...
    def find_element(self, selector: ElementSelector) -> SelectorMatchResult: ...
    def click_element(self, selector: ElementSelector) -> bool: ...
    def fill_element(self, selector: ElementSelector, value: str) -> bool: ...
    def submit_element(self, selector: ElementSelector) -> bool: ...
    def get_current_page(self) -> PageDescriptor: ...


class BrowserEngine:
    """Governed browser session management with read-first behavior.

    Rules:
    - Session must be opened before any action
    - Actions on closed sessions fail immediately
    - Selector mismatch = fail closed (no fallback)
    - Read actions always succeed if session is active
    - Mutation actions require selector to be found first
    - Verification compares expected state against actual
    """

    def __init__(self, *, clock: Callable[[], str], backend: BrowserBackend) -> None:
        self._clock = clock
        self._backend = backend
        self._session: BrowserSession | None = None
        self._observations: list[BrowserObservation] = []
        self._action_results: list[BrowserActionResult] = []

    @property
    def session(self) -> BrowserSession | None:
        return self._session

    def open_session(self, url: str) -> BrowserSession:
        """Open a new browser session at the given URL."""
        ensure_non_empty_text("url", url)
        session_id = stable_identifier("browser-session", {"url": url, "time": self._clock()})

        try:
            page = self._backend.open_page(url)
        except Exception as exc:
            self._session = BrowserSession(
                session_id=session_id,
                status=BrowserSessionStatus.ERROR,
                base_url=url,
                created_at=self._clock(),
            )
            return self._session

        self._session = BrowserSession(
            session_id=session_id,
            status=BrowserSessionStatus.ACTIVE,
            base_url=url,
            current_url=page.url,
            page_title=page.title,
            created_at=self._clock(),
        )
        return self._session

    def close_session(self) -> BrowserSession | None:
        """Close the current session."""
        if self._session is None:
            return None
        closed = BrowserSession(
            session_id=self._session.session_id,
            status=BrowserSessionStatus.CLOSED,
            base_url=self._session.base_url,
            current_url=self._session.current_url,
            page_title=self._session.page_title,
            created_at=self._session.created_at,
        )
        self._session = closed
        return closed

    def observe(self) -> BrowserObservation | None:
        """Read-only observation of current page state."""
        if self._session is None or not self._session.is_active:
            return None

        page = self._backend.get_current_page()
        obs_id = stable_identifier("browser-obs", {
            "session_id": self._session.session_id,
            "obs_count": len(self._observations),
        })
        observation = BrowserObservation(
            observation_id=obs_id,
            session_id=self._session.session_id,
            page=page,
            observed_at=self._clock(),
        )
        self._observations.append(observation)
        return observation

    def execute_action(self, action: BrowserAction) -> BrowserActionResult:
        """Execute a bounded browser action with selector validation."""
        if self._session is None or not self._session.is_active:
            result = BrowserActionResult(
                action_id=action.action_id,
                succeeded=False,
                error_message="no active session",
            )
            self._action_results.append(result)
            return result

        # Navigate — no selector needed
        if action.action_type is BrowserActionType.NAVIGATE:
            if not action.url:
                result = BrowserActionResult(
                    action_id=action.action_id, succeeded=False,
                    error_message="navigate requires url",
                )
                self._action_results.append(result)
                return result
            try:
                page = self._backend.open_page(action.url)
                self._session = BrowserSession(
                    session_id=self._session.session_id,
                    status=BrowserSessionStatus.ACTIVE,
                    base_url=self._session.base_url,
                    current_url=page.url,
                    page_title=page.title,
                    created_at=self._session.created_at,
                )
                result = BrowserActionResult(
                    action_id=action.action_id, succeeded=True, page_after=page,
                )
            except Exception as exc:
                result = BrowserActionResult(
                    action_id=action.action_id, succeeded=False,
                    error_message=f"navigate_error:{exc}",
                )
            self._action_results.append(result)
            return result

        # Read — selector optional
        if action.action_type is BrowserActionType.READ:
            if action.selector:
                match = self._backend.find_element(action.selector)
                result = BrowserActionResult(
                    action_id=action.action_id,
                    succeeded=match.found,
                    selector_match=match,
                    error_message=None if match.found else f"selector not found: {action.selector.selector_value}",
                )
            else:
                page = self._backend.get_current_page()
                result = BrowserActionResult(
                    action_id=action.action_id, succeeded=True, page_after=page,
                )
            self._action_results.append(result)
            return result

        # Mutation actions — require selector
        if action.selector is None:
            result = BrowserActionResult(
                action_id=action.action_id, succeeded=False,
                error_message=f"{action.action_type.value} requires a selector",
            )
            self._action_results.append(result)
            return result

        # Validate selector first (fail-closed)
        match = self._backend.find_element(action.selector)
        if not match.found:
            result = BrowserActionResult(
                action_id=action.action_id, succeeded=False,
                selector_match=match,
                error_message=f"selector mismatch: {match.status.value}",
            )
            self._action_results.append(result)
            return result

        # Execute the mutation
        ok = False
        if action.action_type is BrowserActionType.CLICK:
            ok = self._backend.click_element(action.selector)
        elif action.action_type is BrowserActionType.FILL:
            ok = self._backend.fill_element(action.selector, action.value or "")
        elif action.action_type is BrowserActionType.SUBMIT:
            ok = self._backend.submit_element(action.selector)
        else:
            result = BrowserActionResult(
                action_id=action.action_id, succeeded=False,
                error_message=f"unsupported action type: {action.action_type.value}",
            )
            self._action_results.append(result)
            return result

        page_after = self._backend.get_current_page() if ok else None
        result = BrowserActionResult(
            action_id=action.action_id, succeeded=ok,
            selector_match=match, page_after=page_after,
            error_message=None if ok else f"{action.action_type.value} failed",
        )
        self._action_results.append(result)
        return result

    def verify_state(
        self,
        action_id: str,
        *,
        expected_selector: ElementSelector | None = None,
        expected_value: str | None = None,
        expected_title: str | None = None,
    ) -> BrowserVerificationResult:
        """Verify page state after an action."""
        ensure_non_empty_text("action_id", action_id)
        verification_id = stable_identifier("browser-verify", {
            "action_id": action_id, "time": self._clock(),
        })

        if self._session is None or not self._session.is_active:
            return BrowserVerificationResult(
                verification_id=verification_id, action_id=action_id,
                status=BrowserVerificationStatus.FAIL,
                reason="no active session",
            )

        # Title check
        if expected_title is not None:
            page = self._backend.get_current_page()
            if page.title != expected_title:
                return BrowserVerificationResult(
                    verification_id=verification_id, action_id=action_id,
                    status=BrowserVerificationStatus.VALUE_MISMATCH,
                    expected_value=expected_title, actual_value=page.title,
                    reason=f"title mismatch: expected '{expected_title}', got '{page.title}'",
                )

        # Element check
        if expected_selector is not None:
            match = self._backend.find_element(expected_selector)
            if not match.found:
                return BrowserVerificationResult(
                    verification_id=verification_id, action_id=action_id,
                    status=BrowserVerificationStatus.ELEMENT_MISSING,
                    expected_selector=expected_selector,
                    reason=f"expected element not found: {expected_selector.selector_value}",
                )
            if expected_value is not None:
                actual = match.element_value or match.element_text or ""
                if actual != expected_value:
                    return BrowserVerificationResult(
                        verification_id=verification_id, action_id=action_id,
                        status=BrowserVerificationStatus.VALUE_MISMATCH,
                        expected_selector=expected_selector,
                        expected_value=expected_value, actual_value=actual,
                        reason=f"value mismatch: expected '{expected_value}', got '{actual}'",
                    )

        return BrowserVerificationResult(
            verification_id=verification_id, action_id=action_id,
            status=BrowserVerificationStatus.PASS,
        )

    def list_observations(self) -> tuple[BrowserObservation, ...]:
        return tuple(self._observations)

    def list_action_results(self) -> tuple[BrowserActionResult, ...]:
        return tuple(self._action_results)
