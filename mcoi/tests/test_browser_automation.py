"""Golden scenario tests for browser/app workflow automation.

Proves governed browser session lifecycle, read-first behavior,
selector mismatch fail-closed, bounded mutations, and verification.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.browser import (
    BrowserAction,
    BrowserActionType,
    BrowserSession,
    BrowserSessionStatus,
    BrowserVerificationStatus,
    ElementSelector,
    PageDescriptor,
    SelectorMatchStatus,
)
from mcoi_runtime.core.browser import BrowserEngine
from mcoi_runtime.adapters.browser_adapter import (
    SimulatedBrowserBackend,
    SimulatedElement,
    SimulatedPage,
)


T0 = "2025-01-15T10:00:00+00:00"


def _selector(sel_type="css", value="#submit"):
    return ElementSelector(selector_type=sel_type, selector_value=value)


def _make_engine():
    backend = SimulatedBrowserBackend()
    backend.register_page(SimulatedPage(
        url="https://app.example.com/login",
        title="Login Page",
        elements=[
            SimulatedElement(selector_type="css", selector_value="#username", tag="input", text="", value=""),
            SimulatedElement(selector_type="css", selector_value="#password", tag="input", text="", value=""),
            SimulatedElement(selector_type="css", selector_value="#submit", tag="button", text="Login"),
        ],
        text_content="Welcome to the login page",
    ))
    backend.register_page(SimulatedPage(
        url="https://app.example.com/dashboard",
        title="Dashboard",
        elements=[
            SimulatedElement(selector_type="css", selector_value="#status", tag="span", text="Active", value="active"),
            SimulatedElement(selector_type="css", selector_value="#logout", tag="button", text="Logout"),
        ],
        text_content="System status: Active",
    ))
    engine = BrowserEngine(clock=lambda: T0, backend=backend)
    return engine, backend


# --- Contracts ---


class TestBrowserContracts:
    def test_session_active(self):
        s = BrowserSession(session_id="s-1", status=BrowserSessionStatus.ACTIVE)
        assert s.is_active

    def test_session_closed(self):
        s = BrowserSession(session_id="s-1", status=BrowserSessionStatus.CLOSED)
        assert not s.is_active

    def test_selector_valid(self):
        s = _selector()
        assert s.selector_type == "css"

    def test_selector_empty_rejected(self):
        with pytest.raises(ValueError):
            ElementSelector(selector_type="", selector_value="#x")

    def test_page_descriptor(self):
        p = PageDescriptor(url="https://x.com", title="Test")
        assert p.url == "https://x.com"

    def test_action_valid(self):
        a = BrowserAction(action_id="a-1", action_type=BrowserActionType.CLICK, selector=_selector())
        assert a.action_type is BrowserActionType.CLICK

    def test_verification_passed(self):
        from mcoi_runtime.contracts.browser import BrowserVerificationResult
        v = BrowserVerificationResult(
            verification_id="v-1", action_id="a-1",
            status=BrowserVerificationStatus.PASS,
        )
        assert v.passed


# --- Session lifecycle ---


class TestSessionLifecycle:
    def test_open_session(self):
        engine, _ = _make_engine()
        session = engine.open_session("https://app.example.com/login")
        assert session.is_active
        assert session.page_title == "Login Page"

    def test_close_session(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        closed = engine.close_session()
        assert closed is not None
        assert closed.status is BrowserSessionStatus.CLOSED

    def test_action_on_closed_session_fails(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        engine.close_session()
        result = engine.execute_action(BrowserAction(
            action_id="a-1", action_type=BrowserActionType.READ,
        ))
        assert not result.succeeded
        assert "no active session" in result.error_message

    def test_observe_on_closed_session_returns_none(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        engine.close_session()
        assert engine.observe() is None


# --- Read-first behavior ---


class TestReadFirst:
    def test_observe_returns_page_state(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        obs = engine.observe()
        assert obs is not None
        assert obs.page.title == "Login Page"

    def test_read_action_succeeds(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-1", action_type=BrowserActionType.READ,
        ))
        assert result.succeeded

    def test_read_element_returns_match(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-2", action_type=BrowserActionType.READ,
            selector=_selector("css", "#username"),
        ))
        assert result.succeeded
        assert result.selector_match is not None
        assert result.selector_match.found


# --- Selector mismatch fail-closed ---


class TestSelectorMismatch:
    def test_click_missing_selector_fails(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="c-1", action_type=BrowserActionType.CLICK,
            selector=_selector("css", "#nonexistent"),
        ))
        assert not result.succeeded
        assert "selector mismatch" in result.error_message

    def test_fill_missing_selector_fails(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="f-1", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#nonexistent"), value="test",
        ))
        assert not result.succeeded

    def test_submit_missing_selector_fails(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="s-1", action_type=BrowserActionType.SUBMIT,
            selector=_selector("css", "#nonexistent"),
        ))
        assert not result.succeeded

    def test_mutation_without_selector_fails(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="m-1", action_type=BrowserActionType.CLICK,
        ))
        assert not result.succeeded
        assert "requires a selector" in result.error_message


# --- Bounded mutations ---


class TestBoundedMutations:
    def test_fill_and_read_back(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")

        # Fill username
        fill_result = engine.execute_action(BrowserAction(
            action_id="f-1", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#username"), value="alice",
        ))
        assert fill_result.succeeded

        # Read back
        read_result = engine.execute_action(BrowserAction(
            action_id="r-1", action_type=BrowserActionType.READ,
            selector=_selector("css", "#username"),
        ))
        assert read_result.succeeded
        assert read_result.selector_match.element_value == "alice"

    def test_click_button(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="c-1", action_type=BrowserActionType.CLICK,
            selector=_selector("css", "#submit"),
        ))
        assert result.succeeded

    def test_submit_records_submission(self):
        engine, backend = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="s-1", action_type=BrowserActionType.SUBMIT,
            selector=_selector("css", "#submit"),
        ))
        assert result.succeeded
        assert len(backend.submissions) == 1

    def test_navigate_to_new_page(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="n-1", action_type=BrowserActionType.NAVIGATE,
            url="https://app.example.com/dashboard",
        ))
        assert result.succeeded
        assert result.page_after.title == "Dashboard"

    def test_navigate_failure_is_bounded(self):
        engine, backend = _make_engine()
        engine.open_session("https://app.example.com/login")
        backend.open_page = lambda url: (_ for _ in ()).throw(RuntimeError("secret backend navigation detail"))
        result = engine.execute_action(BrowserAction(
            action_id="n-2", action_type=BrowserActionType.NAVIGATE,
            url="https://app.example.com/dashboard",
        ))
        assert not result.succeeded
        assert result.error_message == "navigate_error:RuntimeError"
        assert "secret backend navigation detail" not in result.error_message


# --- Verification ---


class TestBrowserVerification:
    def test_verify_title_pass(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        v = engine.verify_state("a-1", expected_title="Login Page")
        assert v.passed

    def test_verify_title_mismatch(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        v = engine.verify_state("a-1", expected_title="Dashboard")
        assert not v.passed
        assert v.status is BrowserVerificationStatus.VALUE_MISMATCH
        assert v.reason == "title mismatch"
        assert v.expected_value is None
        assert v.actual_value is None

    def test_verify_element_exists(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/dashboard")
        v = engine.verify_state("a-1", expected_selector=_selector("css", "#status"))
        assert v.passed

    def test_verify_element_missing(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        v = engine.verify_state("a-1", expected_selector=_selector("css", "#status"))
        assert v.status is BrowserVerificationStatus.ELEMENT_MISSING
        assert v.reason == "expected element not found"
        assert v.expected_selector is None

    def test_verify_element_value(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/dashboard")
        v = engine.verify_state(
            "a-1",
            expected_selector=_selector("css", "#status"),
            expected_value="active",
        )
        assert v.passed

    def test_verify_element_value_mismatch(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/dashboard")
        v = engine.verify_state(
            "a-1",
            expected_selector=_selector("css", "#status"),
            expected_value="inactive",
        )
        assert v.status is BrowserVerificationStatus.VALUE_MISMATCH
        assert v.reason == "value mismatch"
        assert v.expected_selector is None
        assert v.expected_value is None
        assert v.actual_value is None

    def test_verify_no_session(self):
        engine, _ = _make_engine()
        v = engine.verify_state("a-1", expected_title="anything")
        assert not v.passed


# --- Golden scenarios ---


class TestBrowserGoldenScenarios:
    def test_read_only_inspection(self):
        """Open page -> observe -> read elements -> close. No mutations."""
        engine, _ = _make_engine()
        session = engine.open_session("https://app.example.com/dashboard")
        assert session.is_active

        obs = engine.observe()
        assert obs.page.title == "Dashboard"

        read = engine.execute_action(BrowserAction(
            action_id="inspect-1", action_type=BrowserActionType.READ,
            selector=_selector("css", "#status"),
        ))
        assert read.succeeded
        assert read.selector_match.element_text == "Active"

        engine.close_session()
        assert len(engine.list_observations()) == 1
        assert len(engine.list_action_results()) == 1

    def test_fill_form_and_verify(self):
        """Fill form fields -> verify values were set correctly."""
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")

        engine.execute_action(BrowserAction(
            action_id="fill-user", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#username"), value="admin",
        ))
        engine.execute_action(BrowserAction(
            action_id="fill-pass", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#password"), value="secret123",
        ))

        # Verify username was filled
        v = engine.verify_state(
            "fill-user",
            expected_selector=_selector("css", "#username"),
            expected_value="admin",
        )
        assert v.passed

    def test_submit_and_confirm(self):
        """Fill form -> submit -> navigate -> verify dashboard."""
        engine, backend = _make_engine()
        engine.open_session("https://app.example.com/login")

        engine.execute_action(BrowserAction(
            action_id="fill", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#username"), value="alice",
        ))
        engine.execute_action(BrowserAction(
            action_id="submit", action_type=BrowserActionType.SUBMIT,
            selector=_selector("css", "#submit"),
        ))
        assert len(backend.submissions) == 1

        # Navigate to dashboard
        nav = engine.execute_action(BrowserAction(
            action_id="nav", action_type=BrowserActionType.NAVIGATE,
            url="https://app.example.com/dashboard",
        ))
        assert nav.succeeded

        # Verify dashboard loaded
        v = engine.verify_state("nav", expected_title="Dashboard")
        assert v.passed

    def test_blocked_selector_mismatch(self):
        """Attempt to interact with nonexistent element -> fail closed."""
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")

        result = engine.execute_action(BrowserAction(
            action_id="bad-click", action_type=BrowserActionType.CLICK,
            selector=_selector("css", "#nonexistent-button"),
        ))
        assert not result.succeeded
        assert result.selector_match is not None
        assert result.selector_match.status is SelectorMatchStatus.NOT_FOUND

    def test_capture_dashboard_state(self):
        """Open dashboard -> observe -> read multiple elements -> verify state."""
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/dashboard")

        obs = engine.observe()
        assert "Dashboard" in obs.page.title

        status = engine.execute_action(BrowserAction(
            action_id="read-status", action_type=BrowserActionType.READ,
            selector=_selector("css", "#status"),
        ))
        assert status.succeeded
        assert status.selector_match.element_value == "active"

        v = engine.verify_state(
            "read-status",
            expected_selector=_selector("css", "#status"),
            expected_value="active",
        )
        assert v.passed
