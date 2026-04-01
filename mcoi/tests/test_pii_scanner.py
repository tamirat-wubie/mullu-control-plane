"""Phase 3A — PII Scanner & Redaction Engine tests.

Tests: PII detection, redaction modes, dict scanning, built-in patterns,
    custom patterns, edge cases.
"""

import pytest
from mcoi_runtime.core.pii_scanner import (
    BUILTIN_PATTERNS,
    PIICategory,
    PIIMatch,
    PIIPattern,
    PIIScanner,
    RedactionMode,
    ScanResult,
    _apply_redaction,
)


# ═══ Redaction Modes ═══


class TestRedactionModes:
    def test_full_redaction(self):
        result = _apply_redaction("user@example.com", PIICategory.EMAIL, RedactionMode.FULL)
        assert result == "[REDACTED:email]"

    def test_partial_redaction(self):
        result = _apply_redaction("555-123-4567", PIICategory.PHONE, RedactionMode.PARTIAL)
        assert "***" in result or "**" in result
        assert result != "555-123-4567"

    def test_hash_redaction(self):
        result = _apply_redaction("secret", PIICategory.PASSWORD, RedactionMode.HASH, salt="test")
        assert result.startswith("[HASH:password:")
        assert len(result) > 20

    def test_hash_deterministic(self):
        r1 = _apply_redaction("same", PIICategory.EMAIL, RedactionMode.HASH, salt="s")
        r2 = _apply_redaction("same", PIICategory.EMAIL, RedactionMode.HASH, salt="s")
        assert r1 == r2

    def test_none_redaction(self):
        result = _apply_redaction("test", PIICategory.EMAIL, RedactionMode.NONE)
        assert result == "test"

    def test_partial_short_value(self):
        result = _apply_redaction("ab", PIICategory.PHONE, RedactionMode.PARTIAL)
        assert result == "[REDACTED:phone]"


# ═══ Email Detection ═══


class TestEmailDetection:
    def test_detects_email(self):
        scanner = PIIScanner()
        result = scanner.scan("Contact us at admin@company.com for help")
        assert result.pii_detected
        assert result.category_counts.get("email", 0) == 1
        assert "admin@company.com" not in result.redacted_text

    def test_detects_multiple_emails(self):
        scanner = PIIScanner()
        result = scanner.scan("Email alice@test.com or bob@test.com")
        assert result.category_counts.get("email", 0) == 2

    def test_no_email(self):
        scanner = PIIScanner()
        result = scanner.scan("No emails here at all")
        assert not result.pii_detected


# ═══ Phone Detection ═══


class TestPhoneDetection:
    def test_detects_phone(self):
        scanner = PIIScanner()
        result = scanner.scan("Call me at 555-123-4567")
        assert result.pii_detected
        assert result.category_counts.get("phone", 0) >= 1

    def test_detects_phone_with_parens(self):
        scanner = PIIScanner()
        result = scanner.scan("Phone: (555) 123-4567")
        assert result.pii_detected


# ═══ SSN Detection ═══


class TestSSNDetection:
    def test_detects_ssn(self):
        scanner = PIIScanner()
        result = scanner.scan("SSN is 123-45-6789")
        assert result.pii_detected
        assert "123-45-6789" not in result.redacted_text
        assert "[REDACTED:ssn]" in result.redacted_text


# ═══ Credit Card Detection ═══


class TestCreditCardDetection:
    def test_detects_credit_card(self):
        scanner = PIIScanner()
        result = scanner.scan("Card: 4111 1111 1111 1111")
        assert result.pii_detected
        assert result.category_counts.get("credit_card", 0) >= 1


# ═══ IP Address Detection ═══


class TestIPAddressDetection:
    def test_detects_ip(self):
        scanner = PIIScanner()
        result = scanner.scan("Server at 192.168.1.100")
        assert result.pii_detected
        assert "192.168.1.100" not in result.redacted_text


# ═══ API Key Detection ═══


class TestAPIKeyDetection:
    def test_detects_api_key(self):
        scanner = PIIScanner()
        result = scanner.scan("Key: sk-abcdefghijklmnopqrstuvwxyz")
        assert result.pii_detected
        assert "sk-abcdefghij" not in result.redacted_text

    def test_detects_various_prefixes(self):
        scanner = PIIScanner()
        for prefix in ("sk-", "pk-", "ak-", "key-"):
            text = f"Token: {prefix}{'a' * 30}"
            result = scanner.scan(text)
            assert result.pii_detected, f"Failed for prefix {prefix}"


# ═══ Password Detection ═══


class TestPasswordDetection:
    def test_detects_password_assignment(self):
        scanner = PIIScanner()
        result = scanner.scan("password=my_secret_pw")
        assert result.pii_detected
        assert "my_secret_pw" not in result.redacted_text

    def test_detects_passwd_colon(self):
        scanner = PIIScanner()
        result = scanner.scan("passwd: hunter2")
        assert result.pii_detected


# ═══ Scanner Behavior ═══


class TestScannerBehavior:
    def test_disabled_scanner(self):
        scanner = PIIScanner(enabled=False)
        result = scanner.scan("admin@test.com 123-45-6789")
        assert not result.pii_detected
        assert result.redacted_text == "admin@test.com 123-45-6789"

    def test_empty_text(self):
        scanner = PIIScanner()
        result = scanner.scan("")
        assert not result.pii_detected
        assert result.redacted_text == ""

    def test_no_pii_text(self):
        scanner = PIIScanner()
        result = scanner.scan("This is perfectly clean text with no PII.")
        assert not result.pii_detected
        assert result.redacted_text == "This is perfectly clean text with no PII."

    def test_multiple_categories(self):
        scanner = PIIScanner()
        result = scanner.scan("Email admin@test.com, SSN 123-45-6789")
        assert result.pii_detected
        assert len(result.matches) >= 2

    def test_has_pii_quick_check(self):
        scanner = PIIScanner()
        assert scanner.has_pii("user@test.com")
        assert not scanner.has_pii("clean text")

    def test_pattern_count(self):
        scanner = PIIScanner()
        assert scanner.pattern_count == len(BUILTIN_PATTERNS)

    def test_custom_patterns(self):
        custom = (PIIPattern(
            category=PIICategory.CUSTOM,
            pattern=r"\bACME-\d{6}\b",
            redaction_mode=RedactionMode.FULL,
            description="ACME account numbers",
        ),)
        scanner = PIIScanner(patterns=custom)
        result = scanner.scan("Account: ACME-123456")
        assert result.pii_detected
        assert "[REDACTED:custom]" in result.redacted_text


# ═══ Dict Scanning ═══


class TestDictScanning:
    def test_scan_flat_dict(self):
        scanner = PIIScanner()
        data = {"name": "John", "email": "john@test.com", "count": 42}
        redacted, matches = scanner.scan_dict(data)
        assert "john@test.com" not in str(redacted)
        assert redacted["count"] == 42
        assert len(matches) >= 1

    def test_scan_nested_dict(self):
        scanner = PIIScanner()
        data = {"user": {"contact": {"email": "a@b.com", "phone": "555-123-4567"}}}
        redacted, matches = scanner.scan_dict(data)
        assert "a@b.com" not in str(redacted)
        assert len(matches) >= 1

    def test_scan_list_values(self):
        scanner = PIIScanner()
        data = {"emails": ["a@b.com", "c@d.com"]}
        redacted, matches = scanner.scan_dict(data)
        assert len(matches) >= 2

    def test_max_depth_limit(self):
        scanner = PIIScanner()
        deep = {"a": {"b": {"c": {"d": {"e": {"f": "user@test.com"}}}}}}
        redacted, matches = scanner.scan_dict(deep, max_depth=3)
        # Beyond max_depth, values are left unchanged
        assert "user@test.com" in str(redacted)

    def test_non_string_values_preserved(self):
        scanner = PIIScanner()
        data = {"count": 42, "active": True, "ratio": 3.14, "items": None}
        redacted, matches = scanner.scan_dict(data)
        assert redacted["count"] == 42
        assert redacted["active"] is True
        assert redacted["ratio"] == 3.14
        assert len(matches) == 0
