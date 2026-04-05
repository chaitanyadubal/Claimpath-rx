"""
backend/ingestion/llm_extractor.py
Extracts NORMALIZED MedBenefitCoverage records from medical policy text.

Key design: the extraction prompt explicitly instructs the LLM to produce
data in our normalized schema — not payer-specific free text.
This is what makes cross-payer comparison possible.
"""
import json
import logging
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.core.config import get_settings
from backend.core.models import (
    MedBenefitCoverage, CoverageStatus, SiteOfCare,
    PriorAuthCriteria, StepTherapyRequirement, QuantityLimit,
    DiagnosisCriteria, LabCriteria, PresciberRequirement, LineOfTherapy
)
from backend.core.drug_master import get_normalizer
from datetime import datetime

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a medical benefit drug policy analyst specializing in 
health plan coverage policies for medical benefit (Part B) drugs — biologics and 
specialty drugs administered by infusion or injection and billed under the medical 
benefit using J-codes/HCPCS codes (NOT pharmacy formulary drugs).

Extract NORMALIZED coverage data. Every field must be semantically consistent 
regardless of which payer's language was used. Return ONLY valid JSON.

For coverage_status use exactly one of:
  "covered" | "not_covered" | "covered_with_pa" | 
  "covered_with_step_therapy" | "covered_with_quantity_limit" | 
  "non_covered_investigational" | "covered_site_restricted"

For site_of_care use: "home_infusion" | "outpatient_infusion_center" | 
  "hospital_outpatient_department" | "physician_office" | "any" | "not_specified"

For line_of_therapy: "first_line" | "second_line" | "third_line_or_later" | "any"

Extract ALL drugs mentioned, including biosimilars as separate entries.
"""

USER_TEMPLATE = """Extract all medical benefit drug coverage information from this policy.

Payer: {payer_name}
Plan: {plan_name}  
Policy ID: {policy_id}
Policy Version: {policy_version}
Policy Number: {policy_number}
Effective Date: {effective_date}

POLICY TEXT:
{text}

Return JSON: {{"drugs": [
  {{
    "drug_name": "exact name from policy",
    "coverage_status": "...",
    "hcpcs_codes": ["J0135"],
    "site_of_care": ["outpatient_infusion_center"],
    "indications": ["Rheumatoid Arthritis", "Plaque Psoriasis"],
    "non_covered_indications": [],
    "prior_auth": {{
      "required": true,
      "diagnoses": [{{"icd10_codes": ["M05.79"], "description": "Seropositive RA", "severity": "moderate-to-severe"}}],
      "severity_requirement": "moderate-to-severe",
      "step_therapy": {{
        "required": true,
        "line_of_therapy": "second_line",
        "required_prior_drugs": ["methotrexate"],
        "minimum_duration_weeks": 12,
        "failure_definition": "inadequate response or intolerance",
        "exceptions": ["contraindication to conventional DMARDs"]
      }},
      "lab_requirements": [{{"lab_name": "TB test", "operator": "==", "threshold": "negative", "unit": null}}],
      "clinical_scores": ["DAS28 > 3.2"],
      "prescriber": {{"specialty_required": ["rheumatologist"], "board_certification": false, "notes": null}},
      "exclusion_criteria": ["active serious infection", "active TB"],
      "initial_auth_duration_months": 12,
      "renewal_required": true,
      "renewal_criteria": ["documented clinical response"],
      "raw_criteria_text": ["verbatim criteria sentences from policy"]
    }},
    "quantity_limit": {{
      "applies": true,
      "units_per_dose": "40mg",
      "doses_per_period": "1",
      "period_days": 14,
      "description": "40mg every 2 weeks"
    }},
    "requires_specialty_pharmacy": false,
    "requires_buy_and_bill": true,
    "source_page_range": "3-7"
  }}
]}}"""


class LLMExtractor:
    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model
        self.normalizer = get_normalizer()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def _call_llm(self, system: str, user: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.05,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    def extract_from_chunk(
        self, text: str, payer_name: str, plan_name: str,
        policy_id: str, policy_version: str,
        policy_number: str = "", effective_date: str = ""
    ) -> list[MedBenefitCoverage]:

        prompt = USER_TEMPLATE.format(
            payer_name=payer_name, plan_name=plan_name,
            policy_id=policy_id, policy_version=policy_version,
            policy_number=policy_number, effective_date=effective_date,
            text=text[:5000]
        )

        try:
            data = self._call_llm(SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []

        coverages = []
        for d in data.get("drugs", []):
            try:
                cov = self._parse_record(
                    d, payer_name, plan_name, policy_id,
                    policy_version, policy_number, effective_date
                )
                coverages.append(cov)
            except Exception as e:
                logger.warning(f"Failed parsing record: {e}")

        return coverages

    def _parse_record(self, d: dict, payer_name, plan_name,
                      policy_id, policy_version, policy_number, effective_date) -> MedBenefitCoverage:

        # Normalize drug name through master reference
        raw_name = d.get("drug_name", "")
        canonical = self.normalizer.normalize(raw_name)
        hcpcs = d.get("hcpcs_codes") or self.normalizer.get_hcpcs(canonical)

        # Parse coverage status
        try:
            status = CoverageStatus(d.get("coverage_status", "covered_with_pa"))
        except ValueError:
            status = CoverageStatus.COVERED_WITH_PA

        # Parse site of care
        soc_raw = d.get("site_of_care", ["not_specified"])
        sites = []
        for s in (soc_raw if isinstance(soc_raw, list) else [soc_raw]):
            try:
                sites.append(SiteOfCare(s))
            except ValueError:
                sites.append(SiteOfCare.NOT_SPECIFIED)

        # Parse prior auth
        pa_data = d.get("prior_auth", {})
        st_data = pa_data.get("step_therapy", {})
        try:
            lot = LineOfTherapy(st_data.get("line_of_therapy", "any"))
        except ValueError:
            lot = LineOfTherapy.ANY

        step = StepTherapyRequirement(
            required=st_data.get("required", False),
            line_of_therapy=lot,
            required_prior_drugs=st_data.get("required_prior_drugs", []),
            minimum_duration_weeks=st_data.get("minimum_duration_weeks"),
            failure_definition=st_data.get("failure_definition"),
            exceptions=st_data.get("exceptions", []),
        )

        diagnoses = [
            DiagnosisCriteria(
                icd10_codes=dx.get("icd10_codes", []),
                description=dx.get("description", ""),
                severity=dx.get("severity"),
            )
            for dx in pa_data.get("diagnoses", [])
        ]

        labs = [
            LabCriteria(
                lab_name=lb.get("lab_name", ""),
                operator=lb.get("operator", "=="),
                threshold=lb.get("threshold", ""),
                unit=lb.get("unit"),
            )
            for lb in pa_data.get("lab_requirements", [])
        ]

        prx_data = pa_data.get("prescriber", {})
        prescriber = PresciberRequirement(
            specialty_required=prx_data.get("specialty_required", []),
            board_certification=prx_data.get("board_certification", False),
            notes=prx_data.get("notes"),
        )

        prior_auth = PriorAuthCriteria(
            required=pa_data.get("required", False),
            diagnoses=diagnoses,
            severity_requirement=pa_data.get("severity_requirement"),
            step_therapy=step,
            lab_requirements=labs,
            clinical_scores=pa_data.get("clinical_scores", []),
            prescriber=prescriber,
            exclusion_criteria=pa_data.get("exclusion_criteria", []),
            initial_auth_duration_months=pa_data.get("initial_auth_duration_months"),
            renewal_required=pa_data.get("renewal_required", False),
            renewal_criteria=pa_data.get("renewal_criteria", []),
            raw_criteria_text=pa_data.get("raw_criteria_text", []),
        )

        # Parse quantity limit
        ql_data = d.get("quantity_limit", {})
        quantity_limit = QuantityLimit(
            applies=ql_data.get("applies", False),
            units_per_dose=ql_data.get("units_per_dose"),
            doses_per_period=ql_data.get("doses_per_period"),
            period_days=ql_data.get("period_days"),
            description=ql_data.get("description"),
        )

        return MedBenefitCoverage(
            canonical_drug_name=canonical,
            hcpcs_codes=hcpcs,
            payer_name=payer_name,
            plan_name=plan_name,
            policy_id=policy_id,
            policy_number=policy_number or None,
            policy_version=policy_version,
            effective_date=effective_date or None,
            coverage_status=status,
            site_of_care=sites,
            indications=d.get("indications", []),
            non_covered_indications=d.get("non_covered_indications", []),
            prior_auth=prior_auth,
            quantity_limit=quantity_limit,
            requires_specialty_pharmacy=d.get("requires_specialty_pharmacy", False),
            requires_buy_and_bill=d.get("requires_buy_and_bill", True),
            source_page_range=d.get("source_page_range"),
            extracted_at=datetime.utcnow(),
        )

    def extract_from_document(
        self, chunks: list[str], payer_name: str, plan_name: str,
        policy_id: str, policy_version: str,
        policy_number: str = "", effective_date: str = ""
    ) -> list[MedBenefitCoverage]:
        """Process all chunks and merge by canonical drug name."""
        merged: dict[str, MedBenefitCoverage] = {}

        for i, chunk in enumerate(chunks):
            logger.info(f"Extracting chunk {i+1}/{len(chunks)} for {payer_name}/{policy_id}")
            results = self.extract_from_chunk(
                chunk, payer_name, plan_name, policy_id,
                policy_version, policy_number, effective_date
            )
            for cov in results:
                key = cov.canonical_drug_name
                if key not in merged:
                    merged[key] = cov
                else:
                    # Merge: richer criteria wins
                    existing = merged[key]
                    if len(cov.prior_auth.raw_criteria_text) > len(existing.prior_auth.raw_criteria_text):
                        merged[key] = cov

        return list(merged.values())
