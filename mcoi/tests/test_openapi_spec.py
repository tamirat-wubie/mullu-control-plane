"""Phase 219B — OpenAPI spec export and validation tests."""

import pytest
import os
import json

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestOpenAPISpec:
    def test_openapi_available(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["info"]["title"] == "Mullu Platform"
        assert spec["info"]["version"] == "3.10.2"

    def test_openapi_has_paths(self, client):
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
        assert len(paths) >= 50  # We have ~130 endpoints

    def test_health_endpoint_documented(self, client):
        spec = client.get("/openapi.json").json()
        assert "/health" in spec["paths"]

    def test_governed_endpoints_documented(self, client):
        spec = client.get("/openapi.json").json()
        governed = [p for p in spec["paths"] if p.startswith("/api/v1/")]
        assert len(governed) >= 40

    def test_all_methods_have_summary(self, client):
        spec = client.get("/openapi.json").json()
        missing = []
        for path, methods in spec["paths"].items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "delete"):
                    if "summary" not in details and "description" not in details:
                        missing.append(f"{method.upper()} {path}")
        # Allow some without summaries but most should have them
        assert len(missing) < 20, f"Missing summaries: {missing[:5]}"

    def test_spec_is_valid_json(self, client):
        resp = client.get("/openapi.json")
        # Should be parseable and have required OpenAPI fields
        spec = resp.json()
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

    def test_endpoint_count_regression(self, client):
        """Verify we don't lose endpoints between phases."""
        spec = client.get("/openapi.json").json()
        total_ops = sum(
            len([m for m in methods if m in ("get", "post", "put", "delete")])
            for methods in spec["paths"].values()
        )
        assert total_ops >= 60  # Conservative lower bound


class TestK8sManifests:
    """Validate K8s manifest files exist and are well-formed."""

    def test_manifests_exist(self):
        import pathlib
        k8s_dir = pathlib.Path(__file__).parent.parent.parent / "k8s"
        assert k8s_dir.exists(), "k8s/ directory not found"
        yamls = list(k8s_dir.glob("*.yaml"))
        assert len(yamls) >= 3, f"Expected at least 3 YAML files, got {len(yamls)}"

    def test_namespace_manifest(self):
        import pathlib
        ns_file = pathlib.Path(__file__).parent.parent.parent / "k8s" / "namespace.yaml"
        content = ns_file.read_text()
        assert "Namespace" in content
        assert "mullu" in content

    def test_api_manifest(self):
        import pathlib
        api_file = pathlib.Path(__file__).parent.parent.parent / "k8s" / "mullu-api.yaml"
        content = api_file.read_text()
        assert "Deployment" in content
        assert "mullu-api" in content
        assert "readinessProbe" in content
        assert "livenessProbe" in content
        assert "HorizontalPodAutoscaler" in content
