"""Tests for Phase 226A — Input Validation Framework."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.input_validation import (
    InputSchema, InputValidator, RuleType, ValidationRule,
)


@pytest.fixture
def validator():
    v = InputValidator()
    v.register(InputSchema("user", "User Schema", rules=(
        ValidationRule("name", RuleType.REQUIRED),
        ValidationRule("name", RuleType.TYPE_CHECK, value=str),
        ValidationRule("name", RuleType.MIN_LENGTH, value=2),
        ValidationRule("name", RuleType.MAX_LENGTH, value=50),
        ValidationRule("email", RuleType.REQUIRED),
        ValidationRule("email", RuleType.PATTERN, value=r"^[^@]+@[^@]+\.[^@]+$"),
        ValidationRule("age", RuleType.MIN_VALUE, value=0),
        ValidationRule("age", RuleType.MAX_VALUE, value=150),
        ValidationRule("role", RuleType.ENUM, value=("admin", "user", "viewer")),
    )))
    return v


class TestInputValidator:
    def test_valid_input(self, validator):
        result = validator.validate("user", {
            "name": "Alice", "email": "alice@example.com", "age": 30, "role": "admin",
        })
        assert result.valid
        assert len(result.errors) == 0

    def test_missing_required(self, validator):
        result = validator.validate("user", {"email": "a@b.com"})
        assert not result.valid
        errors = [e for e in result.errors if e.rule == "required"]
        assert any(e.field == "name" for e in errors)

    def test_empty_string_required(self, validator):
        result = validator.validate("user", {"name": "  ", "email": "a@b.com"})
        assert not result.valid

    def test_type_check(self, validator):
        result = validator.validate("user", {"name": 123, "email": "a@b.com"})
        assert not result.valid
        assert any(e.rule == "type_check" for e in result.errors)

    def test_min_length(self, validator):
        result = validator.validate("user", {"name": "A", "email": "a@b.com"})
        assert not result.valid
        assert any(e.rule == "min_length" for e in result.errors)

    def test_max_length(self, validator):
        result = validator.validate("user", {"name": "A" * 51, "email": "a@b.com"})
        assert not result.valid

    def test_pattern(self, validator):
        result = validator.validate("user", {"name": "Bob", "email": "not-an-email"})
        assert not result.valid
        assert any(e.rule == "pattern" for e in result.errors)

    def test_min_value(self, validator):
        result = validator.validate("user", {"name": "Bob", "email": "a@b.com", "age": -1})
        assert not result.valid

    def test_max_value(self, validator):
        result = validator.validate("user", {"name": "Bob", "email": "a@b.com", "age": 200})
        assert not result.valid

    def test_enum(self, validator):
        result = validator.validate("user", {"name": "Bob", "email": "a@b.com", "role": "superadmin"})
        assert not result.valid
        assert any(e.rule == "enum" for e in result.errors)

    def test_custom_validator(self):
        v = InputValidator()
        v.register(InputSchema("test", "Test", rules=(
            ValidationRule("value", RuleType.CUSTOM, custom_fn=lambda x: x % 2 == 0),
        )))
        assert v.validate("test", {"value": 4}).valid
        assert not v.validate("test", {"value": 3}).valid

    def test_unknown_schema(self, validator):
        with pytest.raises(ValueError, match="Unknown schema"):
            validator.validate("nonexistent", {})

    def test_to_dict(self, validator):
        result = validator.validate("user", {})
        d = result.to_dict()
        assert "valid" in d
        assert "errors" in d

    def test_summary(self, validator):
        validator.validate("user", {"name": "Bob", "email": "a@b.com"})
        validator.validate("user", {})
        s = validator.summary()
        assert s["total_validations"] == 2
        assert s["total_failures"] == 1
