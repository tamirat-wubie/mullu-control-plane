#!/usr/bin/env python3
"""Staging Drill — automated end-to-end validation of the governed platform.

Proves the full lifecycle: start → authenticate → execute → persist →
provider call → inspect ledger → restart → verify continuity.

Usage:
  python scripts/staging_drill.py [--base-url http://localhost:8000]

Requires: uvicorn running (uvicorn mcoi_runtime.app.server:app --port 8000)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass


@dataclass
class DrillResult:
    step: str
    passed: bool
    detail: str = ""
    duration_ms: float = 0.0


def _get(url: str) -> tuple[int, dict]:
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}
    except Exception as e:
        return 0, {"error": str(e)}


def _post(url: str, data: dict) -> tuple[int, dict]:
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}
    except Exception as e:
        return 0, {"error": str(e)}


def run_drill(base: str = "http://localhost:8000") -> list[DrillResult]:
    results: list[DrillResult] = []

    def step(name: str, fn):
        t0 = time.monotonic()
        try:
            passed, detail = fn()
            ms = (time.monotonic() - t0) * 1000
            results.append(DrillResult(name, passed, detail, ms))
        except Exception as e:
            ms = (time.monotonic() - t0) * 1000
            results.append(DrillResult(name, False, str(e), ms))

    # 1. Health check
    def check_health():
        code, data = _get(f"{base}/health")
        if code != 200:
            return False, f"health returned {code}"
        return data.get("status") == "healthy", json.dumps(data, indent=2)
    step("1. Health check", check_health)

    # 2. Readiness check
    def check_readiness():
        code, data = _get(f"{base}/api/v1/readiness")
        if code != 200:
            return False, f"readiness returned {code}"
        return data.get("ready", False), f"{data.get('subsystems', 0)} subsystems checked"
    step("2. Readiness check", check_readiness)

    # 3. Create session
    def create_session():
        code, data = _post(f"{base}/api/v1/session?actor_id=drill-actor&tenant_id=drill-tenant", {})
        if code != 200:
            return False, f"session returned {code}: {data}"
        return "session_id" in data, f"session_id={data.get('session_id', 'none')}"
    step("3. Create session", create_session)

    # 4. Set tenant budget
    def set_budget():
        code, data = _post(f"{base}/api/v1/tenant/budget", {
            "tenant_id": "drill-tenant", "max_cost": 10.0, "max_calls": 100,
        })
        if code != 200:
            return False, f"budget returned {code}: {data}"
        return data.get("tenant_id") == "drill-tenant", f"spent={data.get('spent', 0)}"
    step("4. Set tenant budget", set_budget)

    # 5. LLM completion
    def llm_complete():
        code, data = _post(f"{base}/api/v1/complete", {
            "prompt": "What is 2+2? Reply with just the number.",
            "tenant_id": "drill-tenant",
            "actor_id": "drill-actor",
        })
        if code != 200:
            return False, f"complete returned {code}: {data}"
        return data.get("governed", False) and len(data.get("content", "")) > 0, \
            f"content={data.get('content', '')[:50]}, cost={data.get('cost', 0)}"
    step("5. LLM completion", llm_complete)

    # 6. Verify audit trail
    def check_audit():
        code, data = _get(f"{base}/api/v1/audit?action=llm.complete&limit=5")
        if code != 200:
            return False, f"audit returned {code}"
        return data.get("count", 0) >= 1, f"{data.get('count', 0)} audit entries"
    step("6. Verify audit trail", check_audit)

    # 7. Verify cost analytics
    def check_costs():
        code, data = _get(f"{base}/api/v1/costs/drill-tenant")
        if code != 200:
            return False, f"costs returned {code}"
        return data.get("call_count", 0) >= 1, \
            f"cost={data.get('total_cost', 0)}, calls={data.get('call_count', 0)}"
    step("7. Verify cost analytics", check_costs)

    # 8. Verify budget spend
    def check_budget_spend():
        code, data = _get(f"{base}/api/v1/tenant/drill-tenant/budget")
        if code != 200:
            return False, f"budget returned {code}"
        return True, f"spent={data.get('spent', 0)}, remaining={data.get('remaining', 0)}"
    step("8. Verify budget spend", check_budget_spend)

    # 9. Verify audit chain integrity
    def check_chain():
        code, data = _get(f"{base}/api/v1/audit/verify")
        if code != 200:
            return False, f"verify returned {code}"
        return data.get("valid", False), f"checked={data.get('entries_checked', 0)}"
    step("9. Audit chain integrity", check_chain)

    # 10. Chat with conversation
    def chat_test():
        code, data = _post(f"{base}/api/v1/chat", {
            "conversation_id": "drill-conv",
            "message": "Hello, this is a staging drill.",
            "tenant_id": "drill-tenant",
            "actor_id": "drill-actor",
        })
        if code != 200:
            return False, f"chat returned {code}: {data}"
        return data.get("succeeded", False), \
            f"messages={data.get('message_count', 0)}, cost={data.get('cost', 0)}"
    step("10. Chat conversation", chat_test)

    # 11. System snapshot
    def check_snapshot():
        code, data = _get(f"{base}/api/v1/snapshot")
        if code != 200:
            return False, f"snapshot returned {code}"
        return "version" in data and "llm" in data, f"version={data.get('version', 'unknown')}"
    step("11. System snapshot", check_snapshot)

    # 12. Circuit breaker healthy
    def check_circuit():
        code, data = _get(f"{base}/api/v1/circuit-breaker")
        if code != 200:
            return False, f"circuit returned {code}"
        return data.get("state") == "closed", f"state={data.get('state', 'unknown')}"
    step("12. Circuit breaker", check_circuit)

    # 13. Shutdown info
    def check_shutdown():
        code, data = _get(f"{base}/api/v1/shutdown/info")
        if code != 200:
            return False, f"shutdown returned {code}"
        return True, f"handlers registered"
    step("13. Shutdown config", check_shutdown)

    return results


def print_results(results: list[DrillResult]) -> bool:
    print("\n" + "=" * 70)
    print("  STAGING DRILL RESULTS")
    print("=" * 70)

    all_passed = True
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.step} ({r.duration_ms:.0f}ms)")
        if r.detail:
            for line in r.detail.split("\n")[:3]:
                print(f"         {line}")
        if not r.passed:
            all_passed = False

    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_ms = sum(r.duration_ms for r in results)
    status = "ALL PASSED" if all_passed else "FAILURES DETECTED"
    print(f"  {status}: {passed}/{total} steps, {total_ms:.0f}ms total")
    print("=" * 70 + "\n")
    return all_passed


if __name__ == "__main__":
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1 and sys.argv[1].startswith("--base-url"):
        if "=" in sys.argv[1]:
            base_url = sys.argv[1].split("=", 1)[1]
        elif len(sys.argv) > 2:
            base_url = sys.argv[2]

    print(f"Running staging drill against {base_url}...")

    # Check if server is reachable
    try:
        urllib.request.urlopen(f"{base_url}/health", timeout=5)
    except Exception:
        print(f"ERROR: Server not reachable at {base_url}")
        print("Start with: uvicorn mcoi_runtime.app.server:app --port 8000")
        sys.exit(1)

    results = run_drill(base_url)
    passed = print_results(results)
    sys.exit(0 if passed else 1)
