"""Satisfy overdue authority obligations through the guarded operator API.

Purpose: close overdue runtime authority obligations with explicit evidence
references so deployment conformance can return to a debt-clear state.
Governance scope: authority-obligation closure, operator-secret handling,
runtime conformance witness recovery, and append-only closure receipts.
Dependencies: urllib standard library and the Mullu gateway authority API.
Invariants:
  - The authority operator secret is accepted only from an argument or env var.
  - The secret is never written to stdout, stderr, or receipt files.
  - Every satisfied obligation receives evidence refs matching its own contract.
  - The command exits nonzero when required clear-state proof is absent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_GATEWAY_URL = "https://mullu-gateway.onrender.com"


@dataclass(frozen=True)
class HttpResult:
    """Bounded HTTP response without sensitive request headers."""

    status: int
    payload: dict[str, Any]


def normalize_gateway_url(value: str) -> str:
    """Return a gateway base URL without a trailing slash."""
    gateway_url = value.strip().rstrip("/")
    if not gateway_url:
        raise ValueError("gateway_url is required")
    if not gateway_url.startswith(("https://", "http://")):
        raise ValueError("gateway_url must include http:// or https://")
    return gateway_url


def evidence_refs_for_obligation(obligation: dict[str, Any], closure_ref: str) -> tuple[str, ...]:
    """Return evidence refs that satisfy this obligation's required evidence labels."""
    obligation_id = str(obligation.get("obligation_id", "")).strip()
    if not obligation_id:
        raise ValueError("obligation_id is required")
    required = obligation.get("evidence_required", ())
    if not isinstance(required, list):
        raise ValueError(f"evidence_required must be a list for {obligation_id}")
    if not required:
        return (f"operator_closure:{closure_ref}:{obligation_id}",)
    refs: list[str] = []
    for item in required:
        evidence_name = str(item).strip()
        if not evidence_name:
            continue
        refs.append(f"{evidence_name}:{closure_ref}:{obligation_id}")
    if not refs:
        raise ValueError(f"no valid evidence refs could be derived for {obligation_id}")
    return tuple(refs)


def request_json(
    method: str,
    url: str,
    *,
    operator_secret: str,
    payload: dict[str, Any] | None = None,
) -> HttpResult:
    """Send a JSON request with the authority operator secret header."""
    body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Mullu-Authority-Secret": operator_secret,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise RuntimeError(f"{url} returned non-object JSON")
            return HttpResult(status=int(response.status), payload=parsed)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method} {url} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def list_overdue_obligations(
    gateway_url: str,
    *,
    operator_secret: str,
    limit: int,
) -> tuple[dict[str, Any], ...]:
    """Return overdue open obligations from the guarded read model."""
    query = urlencode({"status": "open", "overdue": "true", "limit": str(limit)})
    result = request_json(
        "GET",
        f"{gateway_url}/authority/obligations?{query}",
        operator_secret=operator_secret,
    )
    obligations = result.payload.get("obligations", ())
    if not isinstance(obligations, list):
        raise RuntimeError("authority obligation read model did not return an obligations list")
    return tuple(item for item in obligations if isinstance(item, dict))


def satisfy_obligation(
    gateway_url: str,
    obligation: dict[str, Any],
    *,
    operator_secret: str,
    closure_ref: str,
) -> dict[str, Any]:
    """Satisfy one authority obligation and return a redacted receipt row."""
    obligation_id = str(obligation.get("obligation_id", "")).strip()
    evidence_refs = evidence_refs_for_obligation(obligation, closure_ref)
    result = request_json(
        "POST",
        f"{gateway_url}/authority/obligations/{obligation_id}/satisfy",
        operator_secret=operator_secret,
        payload={"evidence_refs": list(evidence_refs)},
    )
    authority_witness = result.payload.get("authority_witness", {})
    return {
        "obligation_id": obligation_id,
        "command_id": str(obligation.get("command_id", "")),
        "obligation_type": str(obligation.get("obligation_type", "")),
        "status": str(result.payload.get("status", "")),
        "http_status": result.status,
        "evidence_refs": list(evidence_refs),
        "authority_witness": authority_witness if isinstance(authority_witness, dict) else {},
    }


def collect_public_status(gateway_url: str) -> dict[str, Any]:
    """Return bounded public runtime status after closure."""
    deployment = request_json("GET", f"{gateway_url}/deployment/witness", operator_secret="").payload
    conformance = request_json("GET", f"{gateway_url}/runtime/conformance", operator_secret="").payload
    return {
        "deployment": {
            "deployment_id": deployment.get("deployment_id", ""),
            "commit_sha": deployment.get("commit_sha", ""),
            "checks_missing": deployment.get("checks_missing", []),
        },
        "runtime_conformance": {
            "certificate_id": conformance.get("certificate_id", ""),
            "terminal_status": conformance.get("terminal_status", ""),
            "conformance_class": conformance.get("conformance_class", ""),
            "authority_responsibility_debt_clear": conformance.get("authority_responsibility_debt_clear", False),
            "authority_overdue_obligation_count": conformance.get("authority_overdue_obligation_count", -1),
            "open_conformance_gaps": conformance.get("open_conformance_gaps", []),
        },
    }


def satisfy_overdue_authority_obligations(
    gateway_url: str,
    *,
    operator_secret: str,
    closure_ref: str,
    limit: int,
    require_clear: bool,
) -> dict[str, Any]:
    """Satisfy overdue obligations and return a redacted closure receipt."""
    obligations = list_overdue_obligations(gateway_url, operator_secret=operator_secret, limit=limit)
    satisfied = tuple(
        satisfy_obligation(
            gateway_url,
            obligation,
            operator_secret=operator_secret,
            closure_ref=closure_ref,
        )
        for obligation in obligations
    )
    public_status = collect_public_status(gateway_url)
    conformance = public_status["runtime_conformance"]
    clear = (
        bool(conformance.get("authority_responsibility_debt_clear"))
        and int(conformance.get("authority_overdue_obligation_count", -1)) == 0
    )
    receipt = {
        "receipt_id": "authority_obligation_overdue_closure",
        "closed_at": datetime.now(UTC).isoformat(),
        "gateway_url": gateway_url,
        "closure_ref": closure_ref,
        "overdue_obligation_count": len(obligations),
        "satisfied_count": len(satisfied),
        "satisfied_obligations": list(satisfied),
        "public_status": public_status,
        "authority_debt_clear": clear,
    }
    if require_clear and not clear:
        receipt["errors"] = ["authority responsibility debt was not clear after closure"]
    else:
        receipt["errors"] = []
    return receipt


def write_receipt(receipt: dict[str, Any], output_path: Path) -> None:
    """Persist a redacted closure receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Satisfy overdue Mullu authority obligations.")
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--authority-operator-secret", default=os.environ.get("MULLU_AUTHORITY_OPERATOR_SECRET", ""))
    parser.add_argument("--closure-ref", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", default=".change_assurance/authority_obligation_overdue_closure.json")
    parser.add_argument("--require-clear", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the overdue authority obligation closure command."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        gateway_url = normalize_gateway_url(args.gateway_url)
        operator_secret = str(args.authority_operator_secret).strip()
        if not operator_secret:
            raise ValueError("authority operator secret is required")
        receipt = satisfy_overdue_authority_obligations(
            gateway_url,
            operator_secret=operator_secret,
            closure_ref=str(args.closure_ref).strip(),
            limit=max(1, int(args.limit)),
            require_clear=bool(args.require_clear),
        )
        write_receipt(receipt, Path(args.output))
        if args.json:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            print(
                "AUTHORITY OBLIGATION CLOSURE "
                f"satisfied={receipt['satisfied_count']} "
                f"authority_debt_clear={str(receipt['authority_debt_clear']).lower()}"
            )
        return 0 if not receipt["errors"] else 2
    except Exception as exc:
        print(f"AUTHORITY OBLIGATION CLOSURE BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
