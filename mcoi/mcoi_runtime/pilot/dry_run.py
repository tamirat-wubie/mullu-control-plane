"""Phase 127D — Dry Run Validation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class DryRunCheck:
    name: str
    passed: bool
    detail: str = ""

@dataclass
class DryRunReport:
    tenant_id: str
    checks: list[DryRunCheck] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(DryRunCheck(name, passed, detail))
        if not passed:
            self.defects.append(f"{name}: {detail}")

    @property
    def go_decision(self) -> str:
        if not self.checks:
            return "no_data"
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        if passed == total:
            return "go"
        elif passed >= total * 0.8:
            return "go_with_caveats"
        else:
            return "no_go"

    def summary(self) -> dict[str, Any]:
        passed = sum(1 for c in self.checks if c.passed)
        return {
            "tenant_id": self.tenant_id,
            "total_checks": len(self.checks),
            "passed": passed,
            "failed": len(self.checks) - passed,
            "defects": len(self.defects),
            "decision": self.go_decision,
        }

class PilotDryRunner:
    """Runs pre-go-live validation checks."""

    def run(self, tenant_id: str, engines: dict[str, Any]) -> DryRunReport:
        report = DryRunReport(tenant_id=tenant_id)

        # Check pack exists
        pack = engines.get("pack")
        if pack and pack.pack_count > 0:
            report.add_check("pack_exists", True, f"packs={pack.pack_count}")
        else:
            report.add_check("pack_exists", False, "No pack deployed")

        # Check connectors
        pilot = engines.get("pilot")
        if pilot and pilot.connector_count >= 5:
            report.add_check("connectors_ready", True, f"connectors={pilot.connector_count}")
        else:
            count = pilot.connector_count if pilot else 0
            report.add_check("connectors_ready", False, f"Only {count} connectors")

        # Check personas
        persona = engines.get("persona")
        if persona and persona.persona_count >= 4:
            report.add_check("personas_configured", True, f"personas={persona.persona_count}")
        else:
            count = persona.persona_count if persona else 0
            report.add_check("personas_configured", False, f"Only {count} personas")

        # Check governance
        gov = engines.get("governance")
        if gov and gov.rule_count >= 3:
            report.add_check("governance_rules", True, f"rules={gov.rule_count}")
        else:
            count = gov.rule_count if gov else 0
            report.add_check("governance_rules", False, f"Only {count} rules")

        # Check copilot ready
        copilot = engines.get("copilot")
        report.add_check("copilot_available", copilot is not None, "Copilot engine present" if copilot else "Missing")

        return report
