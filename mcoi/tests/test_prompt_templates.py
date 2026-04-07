"""Prompt Template Registry Tests — Versioned prompt management."""

import pytest
from mcoi_runtime.core.prompt_templates import (
    PromptTemplate,
    PromptTemplateRegistry,
    extract_variables,
)


def _registry():
    return PromptTemplateRegistry(clock=lambda: "2026-04-07T12:00:00Z")


class TestVariableExtraction:
    def test_extract_variables(self):
        assert extract_variables("Hello {{name}}, your balance is {{balance}}") == {"name", "balance"}

    def test_no_variables(self):
        assert extract_variables("Hello world") == frozenset()

    def test_nested_braces_ignored(self):
        assert extract_variables("{{{bad}}}") == {"bad"}

    def test_empty_content(self):
        assert extract_variables("") == frozenset()


class TestTemplateCreation:
    def test_create(self):
        r = _registry()
        tpl = r.create(tenant_id="t1", name="greeting", content="Hello {{name}}!")
        assert tpl.name == "greeting"
        assert tpl.version == 1
        assert "name" in tpl.variables

    def test_duplicate_name_rejected(self):
        r = _registry()
        r.create(tenant_id="t1", name="greeting", content="Hello")
        with pytest.raises(ValueError, match="already exists"):
            r.create(tenant_id="t1", name="greeting", content="Hi")

    def test_same_name_different_tenant(self):
        r = _registry()
        r.create(tenant_id="t1", name="greeting", content="Hello from T1")
        r.create(tenant_id="t2", name="greeting", content="Hello from T2")
        assert r.get("t1", "greeting").content == "Hello from T1"
        assert r.get("t2", "greeting").content == "Hello from T2"


class TestRendering:
    def test_render_with_variables(self):
        r = _registry()
        r.create(tenant_id="t1", name="welcome", content="Hello {{user}}, welcome to {{company}}!")
        result = r.render("t1", "welcome", {"user": "Alice", "company": "Mullu"})
        assert result == "Hello Alice, welcome to Mullu!"

    def test_render_missing_variable_left_as_is(self):
        r = _registry()
        r.create(tenant_id="t1", name="partial", content="Hello {{name}}, your code is {{code}}")
        result = r.render("t1", "partial", {"name": "Bob"})
        assert "Bob" in result
        assert "{{code}}" in result

    def test_render_nonexistent_template(self):
        r = _registry()
        assert r.render("t1", "nonexistent", {}) is None

    def test_render_prevents_injection(self):
        r = _registry()
        r.create(tenant_id="t1", name="test", content="Result: {{value}}")
        result = r.render("t1", "test", {"value": "{{evil_var}}"})
        assert "{{evil_var}}" not in result
        assert "{ {evil_var} }" in result  # Escaped


class TestVersioning:
    def test_update_creates_new_version(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="Hello v1")
        v2 = r.update("t1", "greet", content="Hello v2")
        assert v2.version == 2
        assert v2.content == "Hello v2"

    def test_get_latest_by_default(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="v1")
        r.update("t1", "greet", content="v2")
        r.update("t1", "greet", content="v3")
        latest = r.get("t1", "greet")
        assert latest.version == 3
        assert latest.content == "v3"

    def test_get_specific_version(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="v1")
        r.update("t1", "greet", content="v2")
        v1 = r.get("t1", "greet", version=1)
        assert v1 is not None
        assert v1.content == "v1"

    def test_get_nonexistent_version(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="v1")
        assert r.get("t1", "greet", version=99) is None

    def test_list_versions(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="v1")
        r.update("t1", "greet", content="v2")
        r.update("t1", "greet", content="v3")
        versions = r.list_versions("t1", "greet")
        assert len(versions) == 3

    def test_version_eviction(self):
        r = _registry()
        r.MAX_VERSIONS_PER_TEMPLATE = 3
        r.create(tenant_id="t1", name="greet", content="v1")
        for i in range(5):
            r.update("t1", "greet", content=f"v{i+2}")
        versions = r.list_versions("t1", "greet")
        assert len(versions) <= 3

    def test_update_nonexistent_rejected(self):
        r = _registry()
        with pytest.raises(ValueError, match="not found"):
            r.update("t1", "nonexistent", content="oops")

    def test_render_specific_version(self):
        r = _registry()
        r.create(tenant_id="t1", name="msg", content="Version 1: {{data}}")
        r.update("t1", "msg", content="Version 2: {{data}}")
        v1_result = r.render("t1", "msg", {"data": "hello"}, version=1)
        v2_result = r.render("t1", "msg", {"data": "hello"}, version=2)
        assert "Version 1" in v1_result
        assert "Version 2" in v2_result


class TestTenantIsolation:
    def test_tenants_isolated(self):
        r = _registry()
        r.create(tenant_id="t1", name="secret", content="T1 secret: {{key}}")
        assert r.get("t2", "secret") is None

    def test_list_templates_by_tenant(self):
        r = _registry()
        r.create(tenant_id="t1", name="a", content="A")
        r.create(tenant_id="t1", name="b", content="B")
        r.create(tenant_id="t2", name="c", content="C")
        assert len(r.list_templates("t1")) == 2
        assert len(r.list_templates("t2")) == 1


class TestDeletion:
    def test_delete(self):
        r = _registry()
        r.create(tenant_id="t1", name="greet", content="Hello")
        assert r.delete("t1", "greet") is True
        assert r.get("t1", "greet") is None

    def test_delete_nonexistent(self):
        r = _registry()
        assert r.delete("t1", "nonexistent") is False


class TestToDict:
    def test_to_dict(self):
        r = _registry()
        tpl = r.create(tenant_id="t1", name="test", content="Hello {{name}}", tags=frozenset({"greeting"}))
        d = tpl.to_dict()
        assert d["name"] == "test"
        assert d["version"] == 1
        assert "name" in d["variables"]
        assert "greeting" in d["tags"]


class TestSummary:
    def test_summary(self):
        r = _registry()
        r.create(tenant_id="t1", name="a", content="A")
        r.create(tenant_id="t1", name="b", content="B")
        r.update("t1", "a", content="A v2")
        s = r.summary()
        assert s["templates"] == 2
        assert s["total_versions"] == 3
        assert s["tenants"] == 1
