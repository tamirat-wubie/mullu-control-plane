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
