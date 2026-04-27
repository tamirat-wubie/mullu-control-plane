"""Domain adapters — translate domain shapes into the universal causal framework.

Pattern: each adapter implements
  - translate_to_universal(request) -> UniversalRequest
  - translate_from_universal(result, original) -> DomainResult
  - run_with_ucja(request) -> DomainResult  (full UCJA → SCCCE round trip)

Adapters are the ONLY place that hold domain vocabulary. The MUSIA core
runtime knows nothing about "code", "tickets", "patients", or "courses".

Six concrete adapters as of v4.7.0:
  - software_dev (v4.0.0)
  - business_process (v4.2.0)
  - scientific_research (v4.6.0)
  - manufacturing (v4.7.0)
  - healthcare (v4.7.0)
  - education (v4.7.0)
"""
from mcoi_runtime.domain_adapters.business_process import (
    BusinessActionKind,
    BusinessRequest,
    BusinessResult,
    run_with_ucja as business_run_with_ucja,
    translate_from_universal as business_translate_from_universal,
    translate_to_universal as business_translate_to_universal,
)
from mcoi_runtime.domain_adapters.education import (
    EducationActionKind,
    EducationRequest,
    EducationResult,
    run_with_ucja as education_run_with_ucja,
    translate_from_universal as education_translate_from_universal,
    translate_to_universal as education_translate_to_universal,
)
from mcoi_runtime.domain_adapters.healthcare import (
    ClinicalActionKind,
    ClinicalRequest,
    ClinicalResult,
    run_with_ucja as healthcare_run_with_ucja,
    translate_from_universal as healthcare_translate_from_universal,
    translate_to_universal as healthcare_translate_to_universal,
)
from mcoi_runtime.domain_adapters.manufacturing import (
    ManufacturingActionKind,
    ManufacturingRequest,
    ManufacturingResult,
    run_with_ucja as manufacturing_run_with_ucja,
    translate_from_universal as manufacturing_translate_from_universal,
    translate_to_universal as manufacturing_translate_to_universal,
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
]
