"""Phase 209C — Prompt template engine tests."""

import pytest
from mcoi_runtime.core.prompt_template_engine import (
    PromptTemplate, PromptTemplateEngine, RenderedPrompt,
)


class TestPromptTemplateEngine:
    def _engine(self):
        eng = PromptTemplateEngine()
        eng.register(PromptTemplate(
            template_id="greet", name="Greeting",
            template="Hello {{name}}, welcome to {{place}}!",
            variables=("name", "place"),
        ))
        eng.register(PromptTemplate(
            template_id="summarize", name="Summarize",
            template="Summarize: {{text}}",
            variables=("text",), system_prompt="Be concise.",
            category="analysis",
        ))
        return eng

    def test_render(self):
        eng = self._engine()
        result = eng.render("greet", {"name": "Alice", "place": "Mullu"})
        assert result.prompt == "Hello Alice, welcome to Mullu!"
        assert result.variables_used["name"] == "Alice"

    def test_render_with_system(self):
        eng = self._engine()
        result = eng.render("summarize", {"text": "some content"})
        assert result.system_prompt == "Be concise."
        assert "some content" in result.prompt

    def test_missing_variable(self):
        eng = self._engine()
        with pytest.raises(ValueError, match="missing variables"):
            eng.render("greet", {"name": "Alice"})  # Missing "place"

    def test_unknown_template(self):
        eng = self._engine()
        with pytest.raises(ValueError, match="unknown template"):
            eng.render("nonexistent", {})

    def test_extra_variables_ignored(self):
        eng = self._engine()
        result = eng.render("greet", {"name": "Bob", "place": "here", "extra": "ignored"})
        assert "Bob" in result.prompt

    def test_list_templates(self):
        eng = self._engine()
        assert len(eng.list_templates()) == 2

    def test_list_by_category(self):
        eng = self._engine()
        assert len(eng.list_templates(category="analysis")) == 1

    def test_duplicate_register(self):
        eng = PromptTemplateEngine()
        eng.register(PromptTemplate(template_id="x", name="X", template="t", variables=()))
        with pytest.raises(ValueError):
            eng.register(PromptTemplate(template_id="x", name="X2", template="t2", variables=()))

    def test_summary(self):
        eng = self._engine()
        summary = eng.summary()
        assert summary["total"] == 2

    def test_system_prompt_substitution(self):
        eng = PromptTemplateEngine()
        eng.register(PromptTemplate(
            template_id="t", name="T",
            template="Q: {{q}}", variables=("q",),
            system_prompt="Context: {{q}}",
        ))
        result = eng.render("t", {"q": "test"})
        assert result.system_prompt == "Context: test"
