"""Golden scenario tests for sensitive-field redaction in browser automation.

Proves that secret-bearing element values (passwords, OTP, card, token) and
value-shaped secrets in page text are masked in observations and read results,
while non-sensitive values are preserved and verification is unaffected.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.browser import (
    BrowserAction,
    BrowserActionType,
    ElementSelector,
    PageDescriptor,
    SelectorMatchResult,
    SelectorMatchStatus,
)
from mcoi_runtime.core.browser import BrowserEngine
from mcoi_runtime.core.browser_redaction import (
    DEFAULT_SENSITIVITY_POLICY,
    SensitivityPolicy,
    is_sensitive_selector,
    redact_page,
    redact_selector_match,
    scrub_text,
)
from mcoi_runtime.adapters.browser_adapter import (
    SimulatedBrowserBackend,
    SimulatedElement,
    SimulatedPage,
)


T0 = "2025-01-15T10:00:00+00:00"
MASK = DEFAULT_SENSITIVITY_POLICY.mask


def _selector(sel_type="css", value="#submit"):
    return ElementSelector(selector_type=sel_type, selector_value=value)


def _match(selector_value, value, *, status=SelectorMatchStatus.FOUND):
    return SelectorMatchResult(
        selector=_selector("css", selector_value),
        status=status,
        element_text=value,
        element_value=value,
        element_tag="input",
    )


def _make_engine(*, redaction_policy=DEFAULT_SENSITIVITY_POLICY):
    backend = SimulatedBrowserBackend()
    backend.register_page(SimulatedPage(
        url="https://app.example.com/login",
        title="Login Page",
        elements=[
            SimulatedElement("css", "#username", "input", "", "alice"),
            SimulatedElement("css", "#password", "input", "", "hunter2"),
            SimulatedElement("css", "#otp-code", "input", "", "778211"),
            SimulatedElement("css", "#submit", "button", "Login"),
        ],
        text_content="Card on file 4111 1111 1111 1111 — SSN 123-45-6789.",
    ))
    engine = BrowserEngine(
        clock=lambda: T0, backend=backend, redaction_policy=redaction_policy,
    )
    return engine, backend


# --- Policy contract ---


class TestSensitivityPolicy:
    def test_default_keywords_lowercased(self):
        policy = SensitivityPolicy(field_keywords=("PassWord", "TOKEN"))
        assert policy.field_keywords == ("password", "token")

    def test_empty_mask_rejected(self):
        with pytest.raises(ValueError):
            SensitivityPolicy(mask="")


# --- Selector classification ---


class TestSensitiveSelector:
    @pytest.mark.parametrize("value", [
        "#password", "login_pwd", "user-otp", "card-number", "#cvv", "apiKey",
    ])
    def test_sensitive_values(self, value):
        assert is_sensitive_selector("css", value)

    @pytest.mark.parametrize("value", ["#username", "#submit", "#status", "email"])
    def test_non_sensitive_values(self, value):
        assert not is_sensitive_selector("css", value)

    def test_description_triggers_match(self):
        assert is_sensitive_selector("css", "#field-3", "Credit Card Number")

    def test_empty_selector_not_sensitive(self):
        assert not is_sensitive_selector(None, None, None)


# --- Text scrubbing ---


class TestScrubText:
    def test_none_passthrough(self):
        assert scrub_text(None) is None

    def test_card_number_masked(self):
        assert "4111" not in scrub_text("pay 4111 1111 1111 1111 now")

    def test_card_number_dashed_masked(self):
        assert "4111" not in scrub_text("4111-1111-1111-1111")

    def test_ssn_masked(self):
        assert "123-45-6789" not in scrub_text("ssn 123-45-6789")

    def test_plain_text_unchanged(self):
        text = "System status: Active"
        assert scrub_text(text) == text

    def test_scrub_disabled_by_policy(self):
        policy = SensitivityPolicy(scrub_page_text=False)
        text = "4111 1111 1111 1111"
        assert scrub_text(text, policy=policy) == text


# --- Match redaction ---


class TestRedactSelectorMatch:
    def test_sensitive_value_masked(self):
        redacted = redact_selector_match(_match("#password", "hunter2"))
        assert redacted.element_value == MASK
        assert redacted.element_text == MASK

    def test_non_sensitive_value_preserved(self):
        redacted = redact_selector_match(_match("#username", "alice"))
        assert redacted.element_value == "alice"

    def test_empty_value_not_replaced(self):
        redacted = redact_selector_match(_match("#password", ""))
        assert redacted.element_value == ""

    def test_selector_identity_preserved(self):
        redacted = redact_selector_match(_match("#password", "hunter2"))
        assert redacted.selector.selector_value == "#password"
        assert redacted.status is SelectorMatchStatus.FOUND


# --- Page redaction ---


class TestRedactPage:
    def test_text_scrubbed_and_metadata_preserved(self):
        page = PageDescriptor(
            url="https://x.com", title="T",
            elements=(_match("#password", "hunter2"), _match("#name", "bob")),
            text_content="card 4111 1111 1111 1111",
            metadata={"k": "v"},
        )
        redacted = redact_page(page)
        assert "4111" not in redacted.text_content
        assert redacted.url == "https://x.com"
        assert redacted.title == "T"
        assert redacted.metadata["k"] == "v"

    def test_sensitive_element_masked_others_preserved(self):
        page = PageDescriptor(
            url="https://x.com", title="T",
            elements=(_match("#password", "hunter2"), _match("#name", "bob")),
        )
        redacted = redact_page(page)
        by_sel = {e.selector.selector_value: e for e in redacted.elements}
        assert by_sel["#password"].element_value == MASK
        assert by_sel["#name"].element_value == "bob"


# --- Engine integration ---


class TestEngineRedaction:
    def test_read_password_field_is_masked(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-1", action_type=BrowserActionType.READ,
            selector=_selector("css", "#password"),
        ))
        assert result.succeeded
        assert result.selector_match.element_value == MASK

    def test_read_otp_field_is_masked(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-2", action_type=BrowserActionType.READ,
            selector=_selector("css", "#otp-code"),
        ))
        assert result.selector_match.element_value == MASK

    def test_read_username_field_is_preserved(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-3", action_type=BrowserActionType.READ,
            selector=_selector("css", "#username"),
        ))
        assert result.selector_match.element_value == "alice"

    def test_observation_text_is_scrubbed(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        obs = engine.observe()
        assert obs is not None
        assert "4111" not in obs.page.text_content
        assert "123-45-6789" not in obs.page.text_content

    def test_fill_then_read_password_is_masked(self):
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        engine.execute_action(BrowserAction(
            action_id="f-1", action_type=BrowserActionType.FILL,
            selector=_selector("css", "#password"), value="newsecret",
        ))
        read = engine.execute_action(BrowserAction(
            action_id="r-4", action_type=BrowserActionType.READ,
            selector=_selector("css", "#password"),
        ))
        assert read.selector_match.element_value == MASK

    def test_disabled_policy_returns_raw_value(self):
        engine, _ = _make_engine(redaction_policy=None)
        engine.open_session("https://app.example.com/login")
        result = engine.execute_action(BrowserAction(
            action_id="r-5", action_type=BrowserActionType.READ,
            selector=_selector("css", "#password"),
        ))
        assert result.selector_match.element_value == "hunter2"

    def test_verification_unaffected_by_redaction(self):
        # Verification compares against live backend state, not redacted views.
        engine, _ = _make_engine()
        engine.open_session("https://app.example.com/login")
        v = engine.verify_state(
            "a-1",
            expected_selector=_selector("css", "#password"),
            expected_value="hunter2",
        )
        assert v.passed
