"""Phase 212C — Structured output tests."""

import pytest
from mcoi_runtime.core.structured_output import OutputSchema, StructuredOutputEngine


class TestStructuredOutputEngine:
    def _engine(self):
        eng = StructuredOutputEngine()
        eng.register(OutputSchema(
            schema_id="analysis", name="Analysis",
            fields={"summary": "string", "score": "number", "tags": "array"},
            required_fields=("summary",),
        ))
        return eng

    def test_parse_valid_json(self):
        eng = self._engine()
        result = eng.parse("analysis", '{"summary": "test", "score": 0.9, "tags": ["a"]}')
        assert result.valid is True
        assert result.parsed["summary"] == "test"

    def test_parse_missing_required(self):
        eng = self._engine()
        result = eng.parse("analysis", '{"score": 0.5}')
        assert result.valid is False
        assert any("summary" in e for e in result.errors)

    def test_parse_wrong_type(self):
        eng = self._engine()
        result = eng.parse("analysis", '{"summary": 123, "score": 0.5}')
        assert result.valid is False

    def test_parse_markdown_json(self):
        eng = self._engine()
        text = 'Here is the result:\n```json\n{"summary": "test"}\n```'
        result = eng.parse("analysis", text)
        assert result.valid is True

    def test_parse_embedded_json(self):
        eng = self._engine()
        text = 'The analysis shows {"summary": "embedded", "tags": []} in the data.'
        result = eng.parse("analysis", text)
        assert result.valid is True

    def test_parse_no_json(self):
        eng = self._engine()
        result = eng.parse("analysis", "just plain text with no json")
        assert result.valid is False

    def test_unknown_schema(self):
        eng = self._engine()
        result = eng.parse("nonexistent", '{}')
        assert result.valid is False
        assert result.errors == ("schema unavailable",)
        assert "nonexistent" not in result.errors[0]

    def test_register_rejects_unsupported_field_type(self):
        eng = StructuredOutputEngine()
        with pytest.raises(ValueError, match="^unsupported field type$") as exc_info:
            eng.register(OutputSchema(
                schema_id="bad",
                name="Bad",
                fields={"summary": "mystery"},
                required_fields=("summary",),
            ))
        assert "summary" not in str(exc_info.value)
        assert "mystery" not in str(exc_info.value)

    def test_register_rejects_required_field_missing_from_schema(self):
        eng = StructuredOutputEngine()
        with pytest.raises(ValueError, match="^required field not declared in schema fields$") as exc_info:
            eng.register(OutputSchema(
                schema_id="bad-required",
                name="Bad Required",
                fields={"summary": "string"},
                required_fields=("summary", "score"),
            ))
        assert "score" not in str(exc_info.value)

    def test_parse_fails_closed_for_unknown_runtime_field_type(self):
        eng = StructuredOutputEngine()
        eng._schemas["legacy"] = OutputSchema(
            schema_id="legacy",
            name="Legacy",
            fields={"summary": "mystery"},
            required_fields=("summary",),
        )
        result = eng.parse("legacy", '{"summary": "test"}')
        assert result.valid is False
        assert any("expected mystery" in error for error in result.errors)

    def test_duplicate_register_is_bounded(self):
        eng = StructuredOutputEngine()
        eng.register(OutputSchema(
            schema_id="analysis",
            name="Analysis",
            fields={"summary": "string"},
            required_fields=("summary",),
        ))
        with pytest.raises(ValueError, match="^schema already registered$") as exc_info:
            eng.register(OutputSchema(
                schema_id="analysis",
                name="Analysis 2",
                fields={"summary": "string"},
                required_fields=("summary",),
            ))
        assert "analysis" not in str(exc_info.value)

    def test_raw_text_preserved(self):
        eng = self._engine()
        text = '{"summary": "hi"}'
        result = eng.parse("analysis", text)
        assert result.raw_text == text

    def test_list_schemas(self):
        eng = self._engine()
        assert len(eng.list_schemas()) == 1

    def test_summary(self):
        eng = self._engine()
        assert eng.summary()["schemas"] == 1
