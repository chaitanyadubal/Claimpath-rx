"""
scripts/load_demo_data.py
Loads realistic medical benefit drug coverage demo data — real drugs,
real J-codes, realistic PA criteria that mirror actual payer policies.

Run: python scripts/load_demo_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console
from rich.table import Table
from backend.graph.neo4j_manager import Neo4jManager
from backend.vector.qdrant_manager import QdrantManager
from backend.core.drug_master import get_normalizer
from backend.core.models import (
    MedBenefitCoverage, CoverageStatus, SiteOfCare,
    PriorAuthCriteria, StepTherapyRequirement, QuantityLimit,
    DiagnosisCriteria, LabCriteria, PresciberRequirement, LineOfTherapy
)
from backend.diff.policy_differ import diff_new_policy
from datetime import datetime

console = Console()
norm = get_normalizer()


def make_coverage(drug: str, payer: str, plan: str, pid: str, ver: str, eff: str,
                  status: CoverageStatus, hcpcs: list, sites: list, indications: list,
                  pa: PriorAuthCriteria, ql: QuantityLimit,
                  buy_and_bill=True) -> MedBenefitCoverage:
    return MedBenefitCoverage(
        canonical_drug_name=norm.normalize(drug),
        hcpcs_codes=hcpcs,
        payer_name=payer,
        plan_name=plan,
        policy_id=pid,
        policy_version=ver,
        effective_date=eff,
        coverage_status=status,
        benefit_type="medical_benefit",
        site_of_care=sites,
        indications=indications,
        prior_auth=pa,
        quantity_limit=ql,
        requires_buy_and_bill=buy_and_bill,
        extracted_at=datetime.utcnow(),
    )


# ─── Demo Coverage Records ────────────────────────────────────────────────────
DEMO_RECORDS: list[MedBenefitCoverage] = [

    # ── Adalimumab (Humira / J0135) ─────────────────────────────────────────

    make_coverage("adalimumab", "Aetna", "Aetna Commercial Medical Benefit",
        "AETNA-MB-BIOLOGIC-001", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_PA, ["J0135"],
        [SiteOfCare.PHYSICIAN_OFFICE, SiteOfCare.HOME_INFUSION],
        ["Rheumatoid Arthritis", "Plaque Psoriasis", "Crohn's Disease", "Ankylosing Spondylitis", "Psoriatic Arthritis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["M05.79","M06.9"], description="Rheumatoid Arthritis", severity="moderate-to-severe"),
                DiagnosisCriteria(icd10_codes=["L40.0"], description="Plaque Psoriasis", severity="moderate-to-severe"),
            ],
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["methotrexate"],
                minimum_duration_weeks=12,
                failure_definition="inadequate response or intolerance at therapeutic dose",
                exceptions=["documented contraindication to conventional DMARDs"],
            ),
            lab_requirements=[LabCriteria(lab_name="TB test (QuantiFERON or PPD)", operator="==", threshold="negative")],
            clinical_scores=["DAS28 > 3.2 for RA", "BSA > 10% or PASI > 10 for psoriasis"],
            prescriber=PresciberRequirement(specialty_required=["rheumatologist","dermatologist"]),
            exclusion_criteria=[
                "Active serious infection or sepsis",
                "Active or latent tuberculosis (untreated)",
                "Current pregnancy or breastfeeding (relative)",
                "History of lymphoma or solid tumor malignancy within 5 years",
            ],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["Documented clinical response (DAS28 reduction ≥ 1.2 or PASI 75 response)"],
            raw_criteria_text=[
                "Diagnosis of moderate-to-severe rheumatoid arthritis confirmed by rheumatologist",
                "Trial and failure of methotrexate at therapeutic dose for minimum 12 weeks unless contraindicated",
                "Negative tuberculosis test within 6 months prior to initiation",
                "No active serious infections at time of authorization",
                "Biosimilar adalimumab must be used unless medical exception documented",
            ],
        ),
        QuantityLimit(applies=True, units_per_dose="40mg/0.4mL", doses_per_period="1 injection", period_days=14, description="40mg every 2 weeks"),
    ),

    make_coverage("adalimumab", "UnitedHealthcare", "UHC Choice Plus",
        "UHC-MB-BIOLOGIC-001", "2024.Q3", "2024-07-01",
        CoverageStatus.COVERED_WITH_PA, ["J0135"],
        [SiteOfCare.PHYSICIAN_OFFICE, SiteOfCare.HOME_INFUSION],
        ["Rheumatoid Arthritis", "Psoriatic Arthritis", "Ulcerative Colitis", "Plaque Psoriasis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["M05.79","M06.9"], description="Rheumatoid Arthritis", severity="moderate-to-severe"),
                DiagnosisCriteria(icd10_codes=["K51.90"], description="Ulcerative Colitis", severity="moderate-to-severe"),
            ],
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["methotrexate","one additional csDMARD"],
                minimum_duration_weeks=12,
                failure_definition="inadequate response defined as HAQ-DI > 0.5 after adequate trial",
            ),
            lab_requirements=[
                LabCriteria(lab_name="TB test", operator="==", threshold="negative"),
                LabCriteria(lab_name="Hepatitis B surface antigen", operator="==", threshold="negative"),
            ],
            clinical_scores=["HAQ-DI > 0.5 for RA", "Mayo Score ≥ 6 for UC"],
            prescriber=PresciberRequirement(specialty_required=["rheumatologist","gastroenterologist"]),
            exclusion_criteria=[
                "Active serious infection",
                "Active TB or positive TB test without treatment",
                "Heart failure NYHA Class III or IV",
            ],
            initial_auth_duration_months=6,
            renewal_required=True,
            renewal_criteria=["Documented clinical improvement", "No new contraindications"],
            raw_criteria_text=[
                "Diagnosis confirmed by board-certified specialist",
                "Inadequate response to methotrexate and one additional csDMARD for minimum 90 days each",
                "Negative TB and Hepatitis B screening within 3 months of initiation",
                "Biosimilar adalimumab (Hadlima, Hyrimoz, or Cyltezo) is preferred — brand Humira requires step through biosimilar first",
                "Prescriber must be rheumatologist or gastroenterologist",
            ],
        ),
        QuantityLimit(applies=True, units_per_dose="40mg/0.4mL", doses_per_period="1 carton (2 pens)", period_days=28, description="2 pens per 28 days"),
    ),

    make_coverage("adalimumab", "Cigna", "Cigna Open Access Plus",
        "CIGNA-MB-BIOLOGIC-001", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_STEP_THERAPY, ["J0135"],
        [SiteOfCare.HOME_INFUSION, SiteOfCare.PHYSICIAN_OFFICE],
        ["Rheumatoid Arthritis", "Ankylosing Spondylitis", "Plaque Psoriasis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["biosimilar adalimumab (Hadlima or Hyrimoz)"],
                minimum_duration_weeks=8,
                failure_definition="inadequate response or intolerance to biosimilar",
                exceptions=["documented allergy to biosimilar excipients"],
            ),
            prescriber=PresciberRequirement(specialty_required=["rheumatologist","dermatologist","gastroenterologist"]),
            exclusion_criteria=["Active serious infection","Malignancy within 5 years"],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["Clinical response documented by prescriber"],
            raw_criteria_text=[
                "Biosimilar adalimumab trial required before brand Humira — must document failure or intolerance",
                "Minimum 8 weeks biosimilar trial at therapeutic dose",
                "Annual re-authorization required with documented clinical response",
            ],
        ),
        QuantityLimit(applies=False),
    ),

    # ── Infliximab (Remicade / J1745) — IV infusion ─────────────────────────

    make_coverage("infliximab", "Aetna", "Aetna Commercial Medical Benefit",
        "AETNA-MB-BIOLOGIC-002", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_PA, ["J1745"],
        [SiteOfCare.OUTPATIENT_INFUSION, SiteOfCare.HOSPITAL_OUTPATIENT],
        ["Rheumatoid Arthritis", "Crohn's Disease", "Ulcerative Colitis", "Ankylosing Spondylitis", "Plaque Psoriasis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["K50.90","K50.91"], description="Crohn's Disease", severity="moderate-to-severe"),
                DiagnosisCriteria(icd10_codes=["K51.90"], description="Ulcerative Colitis", severity="moderate-to-severe"),
            ],
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["azathioprine or 6-mercaptopurine (IBD)", "methotrexate (RA)"],
                minimum_duration_weeks=16,
                failure_definition="inadequate response at therapeutic dose or documented intolerance",
            ),
            lab_requirements=[LabCriteria(lab_name="TB test", operator="==", threshold="negative")],
            prescriber=PresciberRequirement(specialty_required=["gastroenterologist","rheumatologist"]),
            exclusion_criteria=["Active serious infection","Active TB","Heart failure NYHA III/IV"],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["Documentation of clinical response or remission"],
            raw_criteria_text=[
                "IV infusion must be administered in approved outpatient infusion center or hospital outpatient department",
                "Biosimilar infliximab (Inflectra, Renflexis, or Avsola) required — Remicade requires medical exception",
                "Step through conventional immunomodulatory therapy required (16 weeks for IBD)",
                "Negative TB screening required within 6 months of initiation",
            ],
        ),
        QuantityLimit(applies=True, units_per_dose="100mg vial", description="Per weight-based dosing per label"),
        buy_and_bill=True,
    ),

    make_coverage("infliximab", "UnitedHealthcare", "UHC Choice Plus",
        "UHC-MB-BIOLOGIC-002", "2024.Q3", "2024-07-01",
        CoverageStatus.COVERED_SITE_RESTRICTED, ["J1745"],
        [SiteOfCare.OUTPATIENT_INFUSION],   # UHC restricts to infusion center only
        ["Crohn's Disease", "Ulcerative Colitis", "Rheumatoid Arthritis"],
        PriorAuthCriteria(
            required=True,
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["azathioprine","corticosteroids"],
                minimum_duration_weeks=12,
            ),
            prescriber=PresciberRequirement(specialty_required=["gastroenterologist","rheumatologist"]),
            exclusion_criteria=["Active serious infection","Active malignancy"],
            initial_auth_duration_months=6,
            renewal_required=True,
            raw_criteria_text=[
                "Site of care restricted to contracted outpatient infusion center — hospital outpatient not covered",
                "Biosimilar infliximab required (Inflectra preferred on formulary)",
                "Step through azathioprine and corticosteroids for minimum 12 weeks (IBD indication)",
            ],
        ),
        QuantityLimit(applies=True, description="Per weight-based dosing per label"),
    ),

    # ── Ustekinumab (Stelara / J3357) ────────────────────────────────────────

    make_coverage("ustekinumab", "Aetna", "Aetna Commercial Medical Benefit",
        "AETNA-MB-BIOLOGIC-003", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_PA, ["J3357","J3358"],
        [SiteOfCare.OUTPATIENT_INFUSION, SiteOfCare.PHYSICIAN_OFFICE],
        ["Crohn's Disease", "Ulcerative Colitis", "Plaque Psoriasis", "Psoriatic Arthritis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["anti-TNF agent (adalimumab or infliximab)"],
                minimum_duration_weeks=14,
                failure_definition="inadequate response, loss of response, or intolerance",
                exceptions=["Anti-TNF contraindicated — document reason"],
            ),
            prescriber=PresciberRequirement(specialty_required=["gastroenterologist","rheumatologist","dermatologist"]),
            exclusion_criteria=["Active serious infection","Active malignancy"],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["Documented clinical response or remission"],
            raw_criteria_text=[
                "Step therapy through anti-TNF agent required before ustekinumab for IBD indications",
                "Biosimilar ustekinumab (Wezlana) preferred; brand Stelara requires medical exception",
                "IV induction dose must be administered in outpatient infusion center",
                "Maintenance SC doses may be administered at home or physician office after IV induction",
            ],
        ),
        QuantityLimit(applies=False),
    ),

    make_coverage("ustekinumab", "BCBS Federal", "BCBS FEP Standard",
        "BCBS-MB-BIOLOGIC-001", "2024.Q3", "2024-07-01",
        CoverageStatus.COVERED_WITH_PA, ["J3357"],
        [SiteOfCare.OUTPATIENT_INFUSION, SiteOfCare.PHYSICIAN_OFFICE, SiteOfCare.HOME_INFUSION],
        ["Plaque Psoriasis", "Psoriatic Arthritis", "Crohn's Disease"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            step_therapy=StepTherapyRequirement(
                required=False,  # BCBS FEP does NOT require anti-TNF step for psoriasis
                line_of_therapy=LineOfTherapy.ANY,
            ),
            prescriber=PresciberRequirement(specialty_required=["dermatologist","rheumatologist","gastroenterologist"]),
            exclusion_criteria=["Active TB","Active serious infection"],
            initial_auth_duration_months=12,
            renewal_required=True,
            raw_criteria_text=[
                "No anti-TNF step therapy required for psoriasis and psoriatic arthritis indications",
                "Anti-TNF step required for Crohn's Disease indication only",
                "BCBS FEP covers both brand Stelara and biosimilar Wezlana — biosimilar preferred",
            ],
        ),
        QuantityLimit(applies=False),
    ),

    # ── Pembrolizumab (Keytruda / J9271) — Oncology ──────────────────────────

    make_coverage("pembrolizumab", "Aetna", "Aetna Commercial Medical Benefit",
        "AETNA-MB-ONCOLOGY-001", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_PA, ["J9271"],
        [SiteOfCare.HOSPITAL_OUTPATIENT, SiteOfCare.OUTPATIENT_INFUSION],
        ["NSCLC", "Melanoma", "HNSCC", "Classical Hodgkin Lymphoma", "Urothelial Carcinoma",
         "Colorectal Cancer (MSI-H/dMMR)", "TNBC", "Endometrial Carcinoma"],
        PriorAuthCriteria(
            required=True,
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["C34.90","C34.10"], description="Non-Small Cell Lung Cancer"),
                DiagnosisCriteria(icd10_codes=["C43.9"], description="Melanoma"),
            ],
            lab_requirements=[
                LabCriteria(lab_name="PD-L1 TPS (NSCLC 1L monotherapy)", operator=">=", threshold="50", unit="%"),
                LabCriteria(lab_name="MSI-H/dMMR testing (CRC)", operator="==", threshold="positive"),
            ],
            prescriber=PresciberRequirement(specialty_required=["oncologist","hematologist"], board_certification=True),
            exclusion_criteria=[
                "Active autoimmune disease requiring systemic treatment",
                "Use in combination not covered by this policy (see combination regimen policies)",
            ],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["No disease progression per RECIST 1.1", "Tolerating therapy"],
            raw_criteria_text=[
                "FDA-approved indication required — must match labeled indication",
                "PD-L1 testing required for NSCLC first-line monotherapy (TPS ≥ 50%)",
                "MSI-H or dMMR tumor testing required for CRC indication",
                "Prescribed by or in consultation with board-certified oncologist",
                "Combination regimens require separate prior authorization",
            ],
        ),
        QuantityLimit(applies=True, description="Per FDA label weight-based dosing"),
        buy_and_bill=True,
    ),

    # ── Dupilumab (Dupixent / J0223) ─────────────────────────────────────────

    make_coverage("dupilumab", "UnitedHealthcare", "UHC Choice Plus",
        "UHC-MB-BIOLOGIC-003", "2024.Q4", "2024-10-01",
        CoverageStatus.COVERED_WITH_PA, ["J0223"],
        [SiteOfCare.HOME_INFUSION, SiteOfCare.PHYSICIAN_OFFICE],
        ["Atopic Dermatitis", "Asthma (eosinophilic)", "Chronic Rhinosinusitis with Nasal Polyps",
         "Eosinophilic Esophagitis", "Prurigo Nodularis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["L20.89","L20.9"], description="Atopic Dermatitis", severity="moderate-to-severe"),
                DiagnosisCriteria(icd10_codes=["J45.50","J45.51"], description="Asthma", severity="uncontrolled eosinophilic"),
            ],
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["topical corticosteroids (AD)", "ICS/LABA (asthma)"],
                minimum_duration_weeks=4,
                failure_definition="inadequate response or intolerance",
            ),
            lab_requirements=[LabCriteria(lab_name="Blood eosinophil count (asthma)", operator=">=", threshold="300", unit="cells/μL")],
            clinical_scores=["IGA score ≥ 3 for AD", "ACQ-5 ≥ 1.5 for asthma"],
            prescriber=PresciberRequirement(specialty_required=["dermatologist","allergist","pulmonologist"]),
            exclusion_criteria=["Active helminth (parasitic) infection"],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["≥ 50% reduction in IGA or EASI score", "Reduction in asthma exacerbations"],
            raw_criteria_text=[
                "Moderate-to-severe atopic dermatitis with inadequate response to topical corticosteroids for ≥ 4 weeks",
                "Uncontrolled moderate-to-severe eosinophilic asthma with blood eosinophils ≥ 300 cells/μL",
                "Specialist (dermatologist, allergist, or pulmonologist) must prescribe",
                "No active parasitic infection at time of authorization",
            ],
        ),
        QuantityLimit(applies=True, units_per_dose="300mg/2mL", doses_per_period="1 injection", period_days=14, description="300mg every 2 weeks (AD); 200mg q2w (asthma)"),
    ),
]


# ─── Second-version records for diff demo ────────────────────────────────────
# These simulate a quarterly policy update — new version of Aetna adalimumab
# with changes: step therapy duration increased, exclusion criteria added

DEMO_V2_RECORDS: list[MedBenefitCoverage] = [
    make_coverage("adalimumab", "Aetna", "Aetna Commercial Medical Benefit",
        "AETNA-MB-BIOLOGIC-001", "2025.Q1", "2025-01-01",  # NEW VERSION
        CoverageStatus.COVERED_WITH_PA, ["J0135"],
        [SiteOfCare.PHYSICIAN_OFFICE, SiteOfCare.HOME_INFUSION],
        ["Rheumatoid Arthritis", "Plaque Psoriasis", "Crohn's Disease", "Ankylosing Spondylitis", "Psoriatic Arthritis"],
        PriorAuthCriteria(
            required=True,
            severity_requirement="moderate-to-severe",
            diagnoses=[
                DiagnosisCriteria(icd10_codes=["M05.79","M06.9"], description="Rheumatoid Arthritis", severity="moderate-to-severe"),
                DiagnosisCriteria(icd10_codes=["L40.0"], description="Plaque Psoriasis", severity="moderate-to-severe"),
            ],
            step_therapy=StepTherapyRequirement(
                required=True, line_of_therapy=LineOfTherapy.SECOND_LINE,
                required_prior_drugs=["methotrexate", "hydroxychloroquine"],   # CHANGED: added hydroxychloroquine
                minimum_duration_weeks=16,   # CHANGED: was 12, now 16
                failure_definition="inadequate response or intolerance at therapeutic dose",
            ),
            lab_requirements=[LabCriteria(lab_name="TB test (QuantiFERON or PPD)", operator="==", threshold="negative")],
            clinical_scores=["DAS28 > 3.2 for RA", "BSA > 10% or PASI > 10 for psoriasis"],
            prescriber=PresciberRequirement(specialty_required=["rheumatologist","dermatologist"]),
            exclusion_criteria=[
                "Active serious infection or sepsis",
                "Active or latent tuberculosis (untreated)",
                "Current pregnancy or breastfeeding (relative)",
                "History of lymphoma or solid tumor malignancy within 5 years",
                "Demyelinating disease (e.g. multiple sclerosis)",   # ADDED
            ],
            initial_auth_duration_months=12,
            renewal_required=True,
            renewal_criteria=["Documented clinical response (DAS28 reduction ≥ 1.2 or PASI 75 response)"],
            raw_criteria_text=[
                "Diagnosis of moderate-to-severe rheumatoid arthritis confirmed by rheumatologist",
                "Trial and failure of methotrexate AND hydroxychloroquine at therapeutic dose for minimum 16 weeks unless contraindicated",
                "Negative tuberculosis test within 6 months prior to initiation",
                "No active serious infections at time of authorization",
                "Biosimilar adalimumab must be used unless medical exception documented",
                "No history of or current demyelinating disease including multiple sclerosis",
            ],
        ),
        QuantityLimit(applies=True, units_per_dose="40mg/0.4mL", doses_per_period="1 injection", period_days=14, description="40mg every 2 weeks"),
    ),
]


def main():
    console.print("[bold blue]MedBenefit Demo Data Loader[/bold blue]")
    console.print("Loading realistic medical benefit drug coverage records...\n")

    graph = Neo4jManager()
    vector = QdrantManager()
    normalizer = get_normalizer()

    # Load v1 records
    table = Table("Drug (canonical)", "HCPCS", "Payer", "Status", "PA", "Step")
    console.print("[yellow]Loading initial policy versions (v1)...[/yellow]")
    for cov in DEMO_RECORDS:
        graph.upsert_coverage(cov)
        vector.index_coverage(cov)
        new_diff = diff_new_policy(cov)
        graph.store_diff(new_diff)
        table.add_row(
            cov.canonical_drug_name,
            ", ".join(cov.hcpcs_codes),
            cov.payer_name,
            cov.coverage_status.value,
            "Yes" if cov.prior_auth.required else "No",
            "Yes" if cov.prior_auth.step_therapy.required else "No",
        )
    console.print(table)

    # Load v2 records (generates diffs automatically)
    console.print("\n[yellow]Loading updated policy versions (v2) — diffs will be computed...[/yellow]")
    from backend.core.models import CoverageStatus as CS, SiteOfCare as SOC, PriorAuthCriteria as PAC
    from backend.core.models import StepTherapyRequirement as STR, QuantityLimit as QL
    from backend.core.models import LineOfTherapy as LOT, PresciberRequirement as PR

    for new_cov in DEMO_V2_RECORDS:
        prev = graph.get_previous_version(
            new_cov.policy_id, new_cov.canonical_drug_name, new_cov.policy_version
        )
        if prev:
            from backend.diff.policy_differ import diff_coverage
            old_st = STR(
                required=prev.get("step_required", False),
                required_prior_drugs=prev.get("step_drugs") or [],
                minimum_duration_weeks=prev.get("step_weeks"),
                line_of_therapy=LOT(prev.get("step_line", "any")),
            )
            old_pa = PAC(
                required=prev.get("pa_required", False),
                raw_criteria_text=prev.get("pa_raw_criteria") or [],
                exclusion_criteria=prev.get("pa_exclusions") or [],
                clinical_scores=prev.get("pa_clinical_scores") or [],
                severity_requirement=prev.get("pa_severity"),
                initial_auth_duration_months=prev.get("pa_auth_months"),
                renewal_required=prev.get("pa_renewal_required", False),
                renewal_criteria=prev.get("pa_renewal_criteria") or [],
                prescriber=PR(specialty_required=prev.get("pa_specialties") or []),
                step_therapy=old_st,
            )
            old_cov = MedBenefitCoverage(
                canonical_drug_name=prev.get("drug_name", ""),
                payer_name=new_cov.payer_name, plan_name=new_cov.plan_name,
                policy_id=new_cov.policy_id,
                policy_version=prev.get("version", "old"),
                effective_date=prev.get("effective_date"),
                coverage_status=CS(prev.get("coverage_status", "covered")),
                site_of_care=[SOC(s) for s in (prev.get("site_of_care") or ["not_specified"])],
                indications=prev.get("indications") or [],
                quantity_limit=QL(applies=prev.get("ql_applies", False), description=prev.get("ql_description")),
                prior_auth=old_pa,
            )
            diff = diff_coverage(old_cov, new_cov)
            if diff:
                graph.store_diff(diff)
                console.print(f"[green]✓ Diff created:[/green] {diff.summary}")

        graph.upsert_coverage(new_cov)
        vector.index_coverage(new_cov)

    console.print(f"\n[bold green]✅ Demo data loaded successfully![/bold green]")
    console.print(f"  Drugs: {len(set(c.canonical_drug_name for c in DEMO_RECORDS))}")
    console.print(f"  Payers: {len(set(c.payer_name for c in DEMO_RECORDS))}")
    console.print(f"  Coverage records: {len(DEMO_RECORDS) + len(DEMO_V2_RECORDS)}")
    console.print(f"  Change diffs: {len(DEMO_RECORDS) + len(DEMO_V2_RECORDS)}")


if __name__ == "__main__":
    main()
