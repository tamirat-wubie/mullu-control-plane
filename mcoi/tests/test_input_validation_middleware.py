"""Input Validation Middleware Tests — Request validation, injection prevention."""

import pytest
from mcoi_runtime.app.input_validation import (
    COMMON_INJECTION_PATTERNS,
    EndpointValidation,
    InputValidationMiddleware,
    RequestValidator,
    ValidationRule,
    validate_body,
    validate_field,
    validate_json_depth,
)


# ── Field validation ───────────────────────────────────────────

class TestFieldValidation:
    def test_required_present(self):
        assert validate_field("hello", ValidationRule("name", required=True)).valid is True

    def test_required_missing(self):
        r = validate_field(None, ValidationRule("name", required=True))
        assert r.valid is False
        assert "required" in r.error

    def test_required_empty(self):
        assert validate_field("", ValidationRule("name", required=True)).valid is False

    def test_max_length_exceeded(self):
        assert validate_field("x" * 200, ValidationRule("n", max_length=100)).valid is False

    def test_within_max_length(self):
        assert validate_field("hello", ValidationRule("n", max_length=100)).valid is True

    def test_min_length_violated(self):
        assert validate_field("ab", ValidationRule("n", min_length=5)).valid is False

    def test_pattern_match(self):
        assert validate_field("tenant-123", ValidationRule("id", pattern=r"^[a-z0-9-]+$")).valid is True

    def test_pattern_mismatch(self):
        assert validate_field("bad input!", ValidationRule("id", pattern=r"^[a-z0-9-]+$")).valid is False

    def test_forbidden_pattern_caught(self):
        r = validate_field("DROP TABLE users", ValidationRule("q", forbidden_patterns=(r"(?i)drop\s+table",)))
        assert r.valid is False

    def test_optional_none_valid(self):
        assert validate_field(None, ValidationRule("opt")).valid is True


# ── Body validation ────────────────────────────────────────────

class TestBodyValidation:
    def test_all_pass(self):
        rules = (ValidationRule("prompt", required=True), ValidationRule("tid", pattern=r"^[a-z]+$"))
        assert validate_body({"prompt": "hi", "tid": "abc"}, rules).valid is True

    def test_first_failure(self):
        rules = (ValidationRule("a", required=True), ValidationRule("b", required=True))
        r = validate_body({}, rules)
        assert r.field == "a"


# ── JSON depth ─────────────────────────────────────────────────

class TestJsonDepth:
    def test_shallow(self):
        assert validate_json_depth({"a": {"b": 1}}, 5) is True

    def test_too_deep(self):
        assert validate_json_depth({"a": {"b": {"c": {"d": {"e": 1}}}}}, 3) is False

    def test_scalar(self):
        assert validate_json_depth("hi", 0) is True


# ── RequestValidator ───────────────────────────────────────────

class TestRequestValidator:
    def test_valid_request(self):
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("x", required=True),)))
        assert v.validate(path="/api/t", method="POST", body={"x": "ok"}).valid is True

    def test_missing_field(self):
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("x", required=True),)))
        assert v.validate(path="/api/t", method="POST", body={}).valid is False

    def test_body_too_large(self):
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", max_body_size=100))
        assert v.validate(path="/api/t", method="POST", body_size=200).valid is False

    def test_depth_rejected(self):
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", max_json_depth=2))
        assert v.validate(path="/api/t", method="POST", body={"a": {"b": {"c": {"d": 1}}}}).valid is False

    def test_global_forbidden(self):
        v = RequestValidator(global_forbidden_patterns=(r"(?i)drop\s+table",))
        v.register(EndpointValidation(path_prefix="/api"))
        assert v.validate(path="/api/t", method="POST", body={"q": "DROP TABLE x"}).valid is False

    def test_unregistered_passes(self):
        v = RequestValidator()
        assert v.validate(path="/unknown", method="POST", body={"any": "thing"}).valid is True

    def test_counters(self):
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("x", required=True),)))
        v.validate(path="/api/t", method="POST", body={"x": "ok"})
        v.validate(path="/api/t", method="POST", body={})
        assert v.validated_count == 1
        assert v.rejected_count == 1


# ── Injection patterns ─────────────────────────────────────────

class TestInjection:
    def _validator(self):
        v = RequestValidator(global_forbidden_patterns=COMMON_INJECTION_PATTERNS)
        v.register(EndpointValidation(path_prefix="/api"))
        return v

    def test_sql_injection(self):
        v = self._validator()
        assert v.validate(path="/api/t", method="POST", body={"q": "UNION SELECT * FROM users"}).valid is False
        assert v.validate(path="/api/t", method="POST", body={"q": "'; DROP TABLE x; --"}).valid is False

    def test_command_injection(self):
        v = self._validator()
        assert v.validate(path="/api/t", method="POST", body={"c": "ls; rm -rf /"}).valid is False
        assert v.validate(path="/api/t", method="POST", body={"c": "$(cat /etc/passwd)"}).valid is False

    def test_path_traversal(self):
        v = self._validator()
        assert v.validate(path="/api/t", method="POST", body={"p": "../../etc/passwd"}).valid is False

    def test_safe_passes(self):
        v = self._validator()
        assert v.validate(path="/api/t", method="POST", body={"q": "What is the weather?"}).valid is True


# ── Middleware integration ─────────────────────────────────────

class TestMiddleware:
    def _app(self, validator):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        def ep(request):
            return JSONResponse({"ok": True})
        app = Starlette(routes=[
            Route("/api/test", ep, methods=["POST"]),
            Route("/health", ep, methods=["POST"]),
            Route("/api/get", ep),
        ])
        app.add_middleware(InputValidationMiddleware, validator=validator)
        return app

    def test_valid_passes(self):
        from starlette.testclient import TestClient
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("name", required=True),)))
        resp = TestClient(self._app(v)).post("/api/test", json={"name": "ok"})
        assert resp.status_code == 200

    def test_invalid_rejected(self):
        from starlette.testclient import TestClient
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("name", required=True),)))
        resp = TestClient(self._app(v)).post("/api/test", json={})
        assert resp.status_code == 400

    def test_bad_json(self):
        from starlette.testclient import TestClient
        v = RequestValidator()
        resp = TestClient(self._app(v)).post("/api/test", content=b"not json{", headers={"content-type": "application/json"})
        assert resp.status_code == 400

    def test_get_bypasses(self):
        from starlette.testclient import TestClient
        resp = TestClient(self._app(RequestValidator())).get("/api/get")
        assert resp.status_code == 200

    def test_health_exempt(self):
        from starlette.testclient import TestClient
        resp = TestClient(self._app(RequestValidator())).post("/health")
        assert resp.status_code == 200

    def test_no_input_echo(self):
        from starlette.testclient import TestClient
        v = RequestValidator()
        v.register(EndpointValidation(path_prefix="/api", rules=(ValidationRule("name", max_length=5),)))
        evil = "EVIL_" * 100
        resp = TestClient(self._app(v)).post("/api/test", json={"name": evil})
        assert resp.status_code == 400
        assert evil not in resp.text
