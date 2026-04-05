"""Phase 221C — Workflow template tests."""

import pytest
from mcoi_runtime.core.workflow_templates import WorkflowTemplate, WorkflowTemplateRegistry
from mcoi_runtime.core.agent_chain import ChainStep


def _registry():
    reg = WorkflowTemplateRegistry()
    reg.register(WorkflowTemplate(
        template_id="summarize-refine", name="Summarize & Refine",
        description="Two-step: summarize then refine",
        steps=(
            ChainStep(step_id="s1", name="Summarize", prompt_template="Summarize {{topic}}: {{input}}"),
            ChainStep(step_id="s2", name="Refine", prompt_template="Refine for {{audience}}: {{prev}}"),
        ),
        parameters=("topic", "audience"),
        category="analysis",
    ))
    return reg


class TestWorkflowTemplates:
    def test_register(self):
        reg = _registry()
        assert reg.count == 1

    def test_instantiate(self):
        reg = _registry()
        steps = reg.instantiate("summarize-refine", {"topic": "AI", "audience": "executives"})
        assert len(steps) == 2
        assert "AI" in steps[0].prompt_template
        assert "executives" in steps[1].prompt_template

    def test_missing_param(self):
        reg = _registry()
        with pytest.raises(ValueError, match="^missing required workflow parameters$") as exc_info:
            reg.instantiate("summarize-refine", {"topic": "AI"})
        assert "audience" not in str(exc_info.value)

    def test_unknown_template(self):
        reg = _registry()
        with pytest.raises(ValueError, match="^template unavailable$") as exc_info:
            reg.instantiate("nonexistent", {})
        assert "nonexistent" not in str(exc_info.value)

    def test_duplicate_register(self):
        reg = _registry()
        with pytest.raises(ValueError, match="^template already registered$") as exc_info:
            reg.register(WorkflowTemplate(
                template_id="summarize-refine", name="X", description="X",
                steps=(), parameters=(),
            ))
        assert "summarize-refine" not in str(exc_info.value)

    def test_list_by_category(self):
        reg = _registry()
        assert len(reg.list_templates(category="analysis")) == 1
        assert len(reg.list_templates(category="other")) == 0

    def test_summary(self):
        reg = _registry()
        s = reg.summary()
        assert s["total"] == 1
        assert s["by_category"]["analysis"] == 1
