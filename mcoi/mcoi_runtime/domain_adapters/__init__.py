"""Domain adapters — translate domain shapes into the universal causal framework.

Pattern: each adapter implements
  - translate_to_universal(request) -> UniversalRequest
  - translate_from_universal(result, original) -> DomainResult
  - run_with_ucja(request) -> DomainResult  (full UCJA → SCCCE round trip)

Adapters are the ONLY place that hold domain vocabulary. The MUSIA core
runtime knows nothing about "code", "tickets", "patients", or "courses".

Fifteen concrete adapters as of v4.46.0:
  - software_dev (v4.0.0)
  - business_process (v4.2.0)
  - scientific_research (v4.6.0)
  - manufacturing (v4.7.0)
  - healthcare (v4.7.0)
  - education (v4.7.0)
  - finance (v4.46.0)
  - legal (v4.46.0)
  - public_sector (v4.46.0)
  - logistics (v4.46.0)
  - energy (v4.46.0)
  - cybersecurity (v4.46.0)
  - insurance (v4.46.0)
  - environmental (v4.46.0)
  - construction (v4.46.0)
"""
from mcoi_runtime.domain_adapters.business_process import (
    BusinessActionKind,
    BusinessRequest,
    BusinessResult,
    run_with_ucja as business_run_with_ucja,
    translate_from_universal as business_translate_from_universal,
    translate_to_universal as business_translate_to_universal,
)
from mcoi_runtime.domain_adapters.construction import (
    ConstructionActionKind,
    ConstructionRequest,
    ConstructionResult,
    run_with_ucja as construction_run_with_ucja,
    translate_from_universal as construction_translate_from_universal,
    translate_to_universal as construction_translate_to_universal,
)
from mcoi_runtime.domain_adapters.cybersecurity import (
    SecOpsActionKind,
    SecOpsRequest,
    SecOpsResult,
    run_with_ucja as cybersecurity_run_with_ucja,
    translate_from_universal as cybersecurity_translate_from_universal,
    translate_to_universal as cybersecurity_translate_to_universal,
)
from mcoi_runtime.domain_adapters.education import (
    EducationActionKind,
    EducationRequest,
    EducationResult,
    run_with_ucja as education_run_with_ucja,
    translate_from_universal as education_translate_from_universal,
    translate_to_universal as education_translate_to_universal,
)
from mcoi_runtime.domain_adapters.energy import (
    EnergyActionKind,
    EnergyRequest,
    EnergyResult,
    run_with_ucja as energy_run_with_ucja,
    translate_from_universal as energy_translate_from_universal,
    translate_to_universal as energy_translate_to_universal,
)
from mcoi_runtime.domain_adapters.environmental import (
    EnvironmentalActionKind,
    EnvironmentalRequest,
    EnvironmentalResult,
    run_with_ucja as environmental_run_with_ucja,
    translate_from_universal as environmental_translate_from_universal,
    translate_to_universal as environmental_translate_to_universal,
)
from mcoi_runtime.domain_adapters.finance import (
    FinancialActionKind,
    FinancialRequest,
    FinancialResult,
    run_with_ucja as finance_run_with_ucja,
    translate_from_universal as finance_translate_from_universal,
    translate_to_universal as finance_translate_to_universal,
)
from mcoi_runtime.domain_adapters.healthcare import (
    ClinicalActionKind,
    ClinicalRequest,
    ClinicalResult,
    run_with_ucja as healthcare_run_with_ucja,
    translate_from_universal as healthcare_translate_from_universal,
    translate_to_universal as healthcare_translate_to_universal,
)
from mcoi_runtime.domain_adapters.insurance import (
    InsuranceActionKind,
    InsuranceRequest,
    InsuranceResult,
    run_with_ucja as insurance_run_with_ucja,
    translate_from_universal as insurance_translate_from_universal,
    translate_to_universal as insurance_translate_to_universal,
)
from mcoi_runtime.domain_adapters.legal import (
    LegalActionKind,
    LegalRequest,
    LegalResult,
    run_with_ucja as legal_run_with_ucja,
    translate_from_universal as legal_translate_from_universal,
    translate_to_universal as legal_translate_to_universal,
)
from mcoi_runtime.domain_adapters.logistics import (
    LogisticsActionKind,
    LogisticsRequest,
    LogisticsResult,
    run_with_ucja as logistics_run_with_ucja,
    translate_from_universal as logistics_translate_from_universal,
    translate_to_universal as logistics_translate_to_universal,
)
from mcoi_runtime.domain_adapters.manufacturing import (
    ManufacturingActionKind,
    ManufacturingRequest,
    ManufacturingResult,
    run_with_ucja as manufacturing_run_with_ucja,
    translate_from_universal as manufacturing_translate_from_universal,
    translate_to_universal as manufacturing_translate_to_universal,
)
from mcoi_runtime.domain_adapters.public_sector import (
    CivicActionKind,
    CivicRequest,
    CivicResult,
    run_with_ucja as public_sector_run_with_ucja,
    translate_from_universal as public_sector_translate_from_universal,
    translate_to_universal as public_sector_translate_to_universal,
)
from mcoi_runtime.domain_adapters.scientific_research import (
    ResearchActionKind,
    ResearchRequest,
    ResearchResult,
    run_with_ucja as research_run_with_ucja,
    translate_from_universal as research_translate_from_universal,
    translate_to_universal as research_translate_to_universal,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareRequest,
    SoftwareResult,
    SoftwareWorkKind,
    UniversalRequest,
    UniversalResult,
    run_with_cognitive_cycle as software_run_with_cognitive_cycle,
    run_with_ucja as software_run_with_ucja,
    translate_from_universal as software_translate_from_universal,
    translate_to_universal as software_translate_to_universal,
)

__all__ = [
    # Universal types (shared)
    "UniversalRequest",
    "UniversalResult",
    # software_dev
    "SoftwareRequest",
    "SoftwareResult",
    "SoftwareWorkKind",
    "software_run_with_cognitive_cycle",
    "software_run_with_ucja",
    "software_translate_from_universal",
    "software_translate_to_universal",
    # business_process
    "BusinessActionKind",
    "BusinessRequest",
    "BusinessResult",
    "business_run_with_ucja",
    "business_translate_from_universal",
    "business_translate_to_universal",
    # construction
    "ConstructionActionKind",
    "ConstructionRequest",
    "ConstructionResult",
    "construction_run_with_ucja",
    "construction_translate_from_universal",
    "construction_translate_to_universal",
    # cybersecurity
    "SecOpsActionKind",
    "SecOpsRequest",
    "SecOpsResult",
    "cybersecurity_run_with_ucja",
    "cybersecurity_translate_from_universal",
    "cybersecurity_translate_to_universal",
    # scientific_research
    "ResearchActionKind",
    "ResearchRequest",
    "ResearchResult",
    "research_run_with_ucja",
    "research_translate_from_universal",
    "research_translate_to_universal",
    # manufacturing
    "ManufacturingActionKind",
    "ManufacturingRequest",
    "ManufacturingResult",
    "manufacturing_run_with_ucja",
    "manufacturing_translate_from_universal",
    "manufacturing_translate_to_universal",
    # healthcare
    "ClinicalActionKind",
    "ClinicalRequest",
    "ClinicalResult",
    "healthcare_run_with_ucja",
    "healthcare_translate_from_universal",
    "healthcare_translate_to_universal",
    # education
    "EducationActionKind",
    "EducationRequest",
    "EducationResult",
    "education_run_with_ucja",
    "education_translate_from_universal",
    "education_translate_to_universal",
    # energy
    "EnergyActionKind",
    "EnergyRequest",
    "EnergyResult",
    "energy_run_with_ucja",
    "energy_translate_from_universal",
    "energy_translate_to_universal",
    # environmental
    "EnvironmentalActionKind",
    "EnvironmentalRequest",
    "EnvironmentalResult",
    "environmental_run_with_ucja",
    "environmental_translate_from_universal",
    "environmental_translate_to_universal",
    # finance
    "FinancialActionKind",
    "FinancialRequest",
    "FinancialResult",
    "finance_run_with_ucja",
    "finance_translate_from_universal",
    "finance_translate_to_universal",
    # insurance
    "InsuranceActionKind",
    "InsuranceRequest",
    "InsuranceResult",
    "insurance_run_with_ucja",
    "insurance_translate_from_universal",
    "insurance_translate_to_universal",
    # legal
    "LegalActionKind",
    "LegalRequest",
    "LegalResult",
    "legal_run_with_ucja",
    "legal_translate_from_universal",
    "legal_translate_to_universal",
    # logistics
    "LogisticsActionKind",
    "LogisticsRequest",
    "LogisticsResult",
    "logistics_run_with_ucja",
    "logistics_translate_from_universal",
    "logistics_translate_to_universal",
    # public_sector
    "CivicActionKind",
    "CivicRequest",
    "CivicResult",
    "public_sector_run_with_ucja",
    "public_sector_translate_from_universal",
    "public_sector_translate_to_universal",
]
