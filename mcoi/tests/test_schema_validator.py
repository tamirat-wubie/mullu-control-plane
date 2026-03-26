"""Phase 208D — Schema validation engine tests."""

import pytest
from mcoi_runtime.core.schema_validator import (
    SchemaDefinition, SchemaRule, SchemaValidator, ValidationResult,
)


class TestSchemaValidator:
    def _validator(self):
        v = SchemaValidator()
        v.register(SchemaDefinition(
            schema_id="user", name="User",
            rules=(
                SchemaRule(field="name", rule_type="required", value=True),
                SchemaRule(field="name", rule_type="type", value="str"),
                SchemaRule(field="name", rule_type="min_length", value=2),
                SchemaRule(field="age", rule_type="type", value="int"),
                SchemaRule(field="age", rule_type="min_value", value=0),
                SchemaRule(field="age", rule_type="max_value", value=200),
                SchemaRule(field="role", rule_type="enum", value=["admin", "user", "guest"]),
            ),
        ))
        return v

    def test_valid_data(self):
        v = self._validator()
        result = v.validate("user", {"name": "Alice", "age": 30, "role": "admin"})
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_required(self):
        v = self._validator()
        result = v.validate("user", {"age": 30})
        assert result.valid is False
        assert any(e.rule_type == "required" for e in result.errors)

    def test_wrong_type(self):
        v = self._validator()
        result = v.validate("user", {"name": "Alice", "age": "thirty"})
        assert result.valid is False
        assert any(e.field == "age" and e.rule_type == "type" for e in result.errors)

    def test_min_length(self):
        v = self._validator()
        result = v.validate("user", {"name": "A"})  # Too short
        assert result.valid is False
        assert any(e.rule_type == "min_length" for e in result.errors)

    def test_min_value(self):
        v = self._validator()
        result = v.validate("user", {"name": "Alice", "age": -1})
        assert result.valid is False
        assert any(e.rule_type == "min_value" for e in result.errors)

    def test_max_value(self):
        v = self._validator()
        result = v.validate("user", {"name": "Alice", "age": 999})
        assert result.valid is False

    def test_enum(self):
        v = self._validator()
        result = v.validate("user", {"name": "Alice", "role": "superadmin"})
        assert result.valid is False
        assert any(e.rule_type == "enum" for e in result.errors)

    def test_unknown_schema(self):
        v = SchemaValidator()
        result = v.validate("nonexistent", {})
        assert result.valid is False

    def test_duplicate_register(self):
        v = SchemaValidator()
        v.register(SchemaDefinition(schema_id="x", name="X", rules=()))
        with pytest.raises(ValueError):
            v.register(SchemaDefinition(schema_id="x", name="X2", rules=()))

    def test_max_length(self):
        v = SchemaValidator()
        v.register(SchemaDefinition(
            schema_id="short", name="Short",
            rules=(SchemaRule(field="val", rule_type="max_length", value=5),),
        ))
        result = v.validate("short", {"val": "toolong"})
        assert result.valid is False

    def test_list_schemas(self):
        v = self._validator()
        schemas = v.list_schemas()
        assert len(schemas) == 1

    def test_summary(self):
        v = self._validator()
        summary = v.summary()
        assert summary["schemas"] == 1
        assert "user" in summary["schema_ids"]
