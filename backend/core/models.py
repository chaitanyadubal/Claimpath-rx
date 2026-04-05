"""
backend/core/models.py
Domain models purpose-built for MEDICAL BENEFIT drug policies.

Medical benefit drugs = infused/injected biologics billed under the medical
benefit (Part B), identified by J-codes / HCPCS codes, NOT pharmacy formulary.
Examples: Remicade (infliximab J1745), Keytruda (pembrolizumab J9271),
          Dupixent (dupilumab J0223), Stelara (ustekinumab J3357)

The normalization schema is the central artifact — every payer's policy
maps into this same structure so cross-payer comparison is possible.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ─── Enumerations ─────────────────────────────────────────────────────────────

class CoverageStatus(str, Enum):
    COVERED                   = "covered"
    NOT_COVERED               = "not_covered"
    COVERED_WITH_PA           = "covered_with_pa"
    COVERED_WITH_STEP_THERAPY = "covered_with_step_therapy"
    COVERED_WITH_QL           = "covered_with_quantity_limit"
    NON_COVERED_INVESTIGATIONAL = "non_covered_investigational"
    COVERED_SITE_RESTRICTED   = "covered_site_restricted"


class SiteOfCare(str, Enum):
    HOME_INFUSION          = "home_infusion"
    OUTPATIENT_INFUSION    = "outpatient_infusion_center"
    HOSPITAL_OUTPATIENT    = "hospital_outpatient_department"
    PHYSICIAN_OFFICE       = "physician_office"
    SPECIALTY_PHARMACY     = "specialty_pharmacy"
    ANY                    = "any"
    NOT_SPECIFIED          = "not_specified"


class LineOfTherapy(str, Enum):
    FIRST_LINE  = "first_line"
    SECOND_LINE = "second_line"
    THIRD_LINE  = "third_line_or_later"
    ANY         = "any"


class ChangeType(str, Enum):
    ADDED            = "added"
    REMOVED          = "removed"
    MODIFIED         = "modified"
    STATUS_CHANGED   = "status_changed"
    CRITERIA_ADDED   = "criteria_added"
    CRITERIA_REMOVED = "criteria_removed"
    NEW_POLICY       = "new_policy"


# ─── Drug Master (normalization anchor) ───────────────────────────────────────

class DrugMaster(BaseModel):
    """
    Canonical drug record — the normalization anchor.
    Every payer-specific name/alias maps to one DrugMaster entry.
    RxNorm + HCPCS are the authoritative cross-payer identifiers.
    """
    canonical_name: str                        # e.g. "adalimumab"
    brand_names: list[str] = []               # ["Humira", "Hadlima", "Hyrimoz"]
    biosimilars: list[str] = []               # biosimilar names if biologic
    rxnorm_cui: Optional[str] = None          # RxNorm concept ID
    hcpcs_codes: list[str] = []              # ["J0135"] — medical benefit billing
    ndc_codes: list[str] = []               # NDC11 codes
    drug_class: Optional[str] = None         # "TNF Inhibitor", "IL-17 Inhibitor"
    mechanism: Optional[str] = None          # "Anti-TNFα monoclonal antibody"
    route: Optional[str] = None             # "Subcutaneous", "Intravenous"
    is_biologic: bool = False
    is_biosimilar: bool = False
    reference_biologic: Optional[str] = None # if biosimilar, originator name


# ─── Normalized Clinical Criteria ─────────────────────────────────────────────

class DiagnosisCriteria(BaseModel):
    icd10_codes: list[str] = []
    description: str
    severity: Optional[str] = None           # "moderate-to-severe"


class LabCriteria(BaseModel):
    lab_name: str
    operator: str                            # ">=", "<=", ">"
    threshold: str
    unit: Optional[str] = None


class PresciberRequirement(BaseModel):
    specialty_required: list[str] = []      # ["rheumatologist", "dermatologist"]
    board_certification: bool = False
    notes: Optional[str] = None


class StepTherapyRequirement(BaseModel):
    required: bool = False
    line_of_therapy: LineOfTherapy = LineOfTherapy.ANY
    required_prior_drugs: list[str] = []    # drugs that must be tried first
    minimum_duration_weeks: Optional[int] = None
    failure_definition: Optional[str] = None
    exceptions: list[str] = []             # when step therapy can be bypassed


class QuantityLimit(BaseModel):
    applies: bool = False
    units_per_dose: Optional[str] = None
    doses_per_period: Optional[str] = None
    period_days: Optional[int] = None
    max_dose_mg: Optional[float] = None
    description: Optional[str] = None


class PriorAuthCriteria(BaseModel):
    """
    Fully normalized PA criteria — structured so any two payers'
    requirements for the same drug can be directly compared field-by-field.
    """
    required: bool = False

    # Diagnosis requirements
    diagnoses: list[DiagnosisCriteria] = []
    severity_requirement: Optional[str] = None

    # Trial/failure requirements
    step_therapy: StepTherapyRequirement = Field(default_factory=StepTherapyRequirement)

    # Lab / clinical values
    lab_requirements: list[LabCriteria] = []
    clinical_scores: list[str] = []          # "DAS28 > 3.2", "PASI > 10"

    # Prescriber
    prescriber: PresciberRequirement = Field(default_factory=PresciberRequirement)

    # Contraindications / exclusions
    exclusion_criteria: list[str] = []

    # Renewal
    initial_auth_duration_months: Optional[int] = None
    renewal_required: bool = False
    renewal_criteria: list[str] = []        # may differ from initial

    # Raw extracted criteria (for traceability)
    raw_criteria_text: list[str] = []


# ─── Core Coverage Record ──────────────────────────────────────────────────────

class MedBenefitCoverage(BaseModel):
    """
    The normalized coverage record — one drug × one policy.
    This IS the centralized, standardized view the problem statement demands.
    Every field maps to the same semantic meaning regardless of which payer
    the policy came from.
    """
    # Identity
    canonical_drug_name: str               # normalized via DrugMaster
    hcpcs_codes: list[str] = []           # J-codes for this drug
    payer_name: str
    plan_name: str
    policy_id: str
    policy_number: Optional[str] = None   # payer's own policy number
    policy_version: str
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    next_review_date: Optional[str] = None

    # Coverage
    coverage_status: CoverageStatus
    benefit_type: str = "medical_benefit"  # always medical benefit (not pharmacy)
    site_of_care: list[SiteOfCare] = [SiteOfCare.NOT_SPECIFIED]
    indications: list[str] = []
    non_covered_indications: list[str] = []

    # Normalized criteria
    prior_auth: PriorAuthCriteria = Field(default_factory=PriorAuthCriteria)
    quantity_limit: QuantityLimit = Field(default_factory=QuantityLimit)

    # Billing
    requires_specialty_pharmacy: bool = False
    requires_buy_and_bill: bool = False    # physician purchases & bills payer

    # Traceability
    source_url: Optional[str] = None
    source_page_range: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_confidence: float = 1.0


# ─── Policy Document ──────────────────────────────────────────────────────────

class PolicyDocument(BaseModel):
    """A parsed policy PDF with metadata."""
    payer_name: str
    plan_name: str
    policy_id: str
    policy_number: Optional[str] = None
    policy_version: str
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    coverages: list[MedBenefitCoverage] = []
    raw_text: Optional[str] = None
    pages: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Policy Diff / Change Tracking ────────────────────────────────────────────

class CriteriaChange(BaseModel):
    """A single changed criterion — the atomic unit of a policy diff."""
    field: str                             # "prior_auth.step_therapy.required"
    change_type: ChangeType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    human_readable: str                    # "PA criteria added: 'Must fail methotrexate first'"
    # Gap 3: clinical significance classification
    significance: str = "administrative"  # "clinical" | "cosmetic" | "administrative"
    significance_rationale: str = ""      # why it was classified this way


class PolicyDiff(BaseModel):
    """
    Clause-level diff between two versions of the same policy.
    This answers: "What changed across payer policies this quarter?"
    """
    payer_name: str
    plan_name: str
    policy_id: str
    drug_name: str
    old_version: str
    new_version: str
    old_effective_date: Optional[str]
    new_effective_date: Optional[str]
    change_type: ChangeType
    changes: list[CriteriaChange] = []
    summary: str                           # human-readable 1-line summary
    # Gap 3: significance breakdown counts
    clinical_changes: int = 0             # changes that affect patient access
    cosmetic_changes: int = 0             # formatting / reference updates
    administrative_changes: int = 0       # date changes, coding updates
    significance_verdict: str = ""        # "Significant clinical update" | "Cosmetic only" | "Mixed"
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ─── API Request/Response Models ──────────────────────────────────────────────

class CoverageQueryRequest(BaseModel):
    drug_name: str
    payer_names: list[str] = []
    site_of_care: Optional[str] = None

class PAQueryRequest(BaseModel):
    drug_name: str
    payer_name: str

class CompareRequest(BaseModel):
    drug_name: str
    payer_names: list[str] = []

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    filter_payer: Optional[str] = None
    filter_drug: Optional[str] = None

class ChangelogRequest(BaseModel):
    payer_name: Optional[str] = None
    drug_name: Optional[str] = None
    since_date: Optional[str] = None
    change_type: Optional[str] = None
