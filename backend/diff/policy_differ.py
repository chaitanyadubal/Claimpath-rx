"""
backend/diff/policy_differ.py

Clause-level policy diff engine.
Answers: "What changed across payer policies this quarter?"

Compares two MedBenefitCoverage records field-by-field and produces
a structured PolicyDiff with human-readable change summaries.

This is NOT a string diff — it's a semantic diff on the normalized
data model, so it can say:
  "PA criteria added: 'Must fail methotrexate first (12 weeks)'"
  "Coverage status changed: covered → covered_with_pa"
  "Step therapy now requires 2 prior drugs (was 1)"

Gap 3 addition: every change is classified as CLINICAL or COSMETIC.
Clinical = affects coverage decisions, PA approvals, or patient access.
Cosmetic = formatting, references, effective date updates with no criteria change.
"""
from __future__ import annotations
import logging
import re
from backend.core.models import (
    MedBenefitCoverage, PolicyDiff, CriteriaChange, ChangeType
)
from datetime import datetime

logger = logging.getLogger(__name__)


# ─── Clinical Significance Classifier ────────────────────────────────────────
# Fields that directly affect patient access, PA approvals, or coverage decisions
CLINICAL_FIELDS = {
    "coverage_status",
    "prior_auth.required",
    "prior_auth.criteria",
    "prior_auth.step_therapy.required",
    "prior_auth.step_therapy.required_prior_drugs",
    "prior_auth.step_therapy.minimum_duration_weeks",
    "prior_auth.exclusion_criteria",
    "prior_auth.initial_auth_duration_months",
    "prior_auth.renewal_required",
    "prior_auth.renewal_criteria",
    "site_of_care",
    "quantity_limit.applies",
    "quantity_limit.description",
    "indications",
}

# Keywords that signal clinical significance in raw criteria text
CLINICAL_KEYWORDS = {
    "step therapy", "prior authorization", "pa required",
    "must fail", "trial and failure", "contraindicated",
    "diagnosis", "indication", "exclusion", "step through",
    "quantity limit", "site of care", "prescriber", "specialty",
    "clinical criteria", "lab", "score", "renewal",
}

# Keywords that signal cosmetic / administrative changes
COSMETIC_KEYWORDS = {
    "reference", "guideline", "bibliography", "background",
    "formatting", "effective date", "review date", "coding",
    "icd-10", "replaced by", "supersedes", "administrative",
}


def classify_significance(field: str, old_val: str, new_val: str, human_readable: str) -> tuple[str, str]:
    """
    Returns (significance, rationale):
      significance = "clinical" | "cosmetic" | "administrative"
      rationale = one-sentence explanation for the analyst
    """
    # Field-based classification (most reliable)
    if field in CLINICAL_FIELDS:
        return "clinical", f"Directly affects coverage decisions ({field.replace('.',' › ')})"

    # Keyword-based classification on the human-readable description
    text_lower = human_readable.lower()
    clinical_hits = [kw for kw in CLINICAL_KEYWORDS if kw in text_lower]
    cosmetic_hits = [kw for kw in COSMETIC_KEYWORDS if kw in text_lower]

    if clinical_hits:
        return "clinical", f"Contains clinical access terms: {', '.join(clinical_hits[:2])}"
    if cosmetic_hits:
        return "cosmetic", f"Administrative/formatting change: {', '.join(cosmetic_hits[:2])}"

    # Value-based heuristics
    if old_val and new_val:
        # Effective date only change with identical criteria = cosmetic
        if re.match(r'\d{4}-\d{2}-\d{2}', old_val or "") and \
           re.match(r'\d{4}-\d{2}-\d{2}', new_val or ""):
            return "administrative", "Date update — review criteria for other changes"

    return "administrative", "Change requires manual review to confirm clinical impact"


def _make_change(field, change_type, old_value, new_value, human_readable) -> CriteriaChange:
    """Create a CriteriaChange with automatic clinical significance classification."""
    sig, rationale = classify_significance(field, str(old_value or ""), str(new_value or ""), human_readable)
    return CriteriaChange(
        field=field,
        change_type=change_type,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        human_readable=human_readable,
        significance=sig,
        significance_rationale=rationale,
    )


def _build_diff(new: MedBenefitCoverage, changes: list[CriteriaChange],
                old_version: str, old_eff: str) -> PolicyDiff:
    """Assemble a PolicyDiff with significance verdict from classified changes."""
    n_clinical = sum(1 for c in changes if c.significance == "clinical")
    n_cosmetic = sum(1 for c in changes if c.significance == "cosmetic")
    n_admin = sum(1 for c in changes if c.significance == "administrative")

    if n_clinical > 0:
        verdict = f"Clinically significant — {n_clinical} change(s) affect patient access or coverage criteria"
    elif n_admin > 0 and n_cosmetic == 0:
        verdict = "Administrative update — review manually to confirm no clinical impact"
    elif n_cosmetic > 0 and n_clinical == 0:
        verdict = "Cosmetic only — no changes to coverage criteria or PA requirements"
    else:
        verdict = f"Mixed — {n_clinical} clinical, {n_cosmetic} cosmetic, {n_admin} administrative"

    # Build summary
    parts = []
    status_ch = [c for c in changes if c.change_type == ChangeType.STATUS_CHANGED]
    added = [c for c in changes if c.change_type == ChangeType.CRITERIA_ADDED]
    removed = [c for c in changes if c.change_type == ChangeType.CRITERIA_REMOVED]
    modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
    if status_ch:
        parts.append(status_ch[0].human_readable)
    if added:
        parts.append(f"{len(added)} criteria added")
    if removed:
        parts.append(f"{len(removed)} criteria removed")
    if modified:
        parts.append(f"{len(modified)} fields modified")
    summary = "; ".join(parts) or f"{len(changes)} changes detected"

    return PolicyDiff(
        payer_name=new.payer_name,
        plan_name=new.plan_name,
        policy_id=new.policy_id,
        drug_name=new.canonical_drug_name,
        old_version=old_version,
        new_version=new.policy_version,
        old_effective_date=old_eff,
        new_effective_date=new.effective_date,
        change_type=ChangeType.MODIFIED,
        changes=changes,
        summary=summary,
        clinical_changes=n_clinical,
        cosmetic_changes=n_cosmetic,
        administrative_changes=n_admin,
        significance_verdict=verdict,
        detected_at=datetime.utcnow(),
    )


def diff_coverage(old: MedBenefitCoverage, new: MedBenefitCoverage) -> PolicyDiff | None:
    """
    Produce a clause-level PolicyDiff between two versions of the same
    drug × payer coverage record. Returns None if no changes detected.
    Every change is classified as clinical, cosmetic, or administrative.
    """
    changes: list[CriteriaChange] = []

    # ── Coverage status ─────────────────────────────────────────────────────
    if old.coverage_status != new.coverage_status:
        changes.append(_make_change(
            "coverage_status", ChangeType.STATUS_CHANGED,
            old.coverage_status.value, new.coverage_status.value,
            f"Coverage status changed: {old.coverage_status.value.replace('_',' ')} → {new.coverage_status.value.replace('_',' ')}",
        ))

    # ── Prior auth required flag ─────────────────────────────────────────────
    old_pa, new_pa = old.prior_auth, new.prior_auth
    if old_pa.required != new_pa.required:
        changes.append(_make_change(
            "prior_auth.required", ChangeType.MODIFIED,
            old_pa.required, new_pa.required,
            f"Prior authorization {'added' if new_pa.required else 'removed'}",
        ))

    # ── PA criteria (raw text) ───────────────────────────────────────────────
    old_criteria = set(old_pa.raw_criteria_text)
    new_criteria = set(new_pa.raw_criteria_text)
    for added in (new_criteria - old_criteria):
        changes.append(_make_change(
            "prior_auth.criteria", ChangeType.CRITERIA_ADDED,
            None, added, f"PA criteria added: '{added}'",
        ))
    for removed in (old_criteria - new_criteria):
        changes.append(_make_change(
            "prior_auth.criteria", ChangeType.CRITERIA_REMOVED,
            removed, None, f"PA criteria removed: '{removed}'",
        ))

    # ── Step therapy ─────────────────────────────────────────────────────────
    old_st, new_st = old_pa.step_therapy, new_pa.step_therapy
    if old_st.required != new_st.required:
        changes.append(_make_change(
            "prior_auth.step_therapy.required", ChangeType.MODIFIED,
            old_st.required, new_st.required,
            f"Step therapy {'added' if new_st.required else 'removed'}",
        ))

    old_drugs, new_drugs = set(old_st.required_prior_drugs), set(new_st.required_prior_drugs)
    for drug in (new_drugs - old_drugs):
        changes.append(_make_change(
            "prior_auth.step_therapy.required_prior_drugs", ChangeType.CRITERIA_ADDED,
            None, drug, f"Step therapy now requires prior trial of: {drug}",
        ))
    for drug in (old_drugs - new_drugs):
        changes.append(_make_change(
            "prior_auth.step_therapy.required_prior_drugs", ChangeType.CRITERIA_REMOVED,
            drug, None, f"Step therapy no longer requires prior trial of: {drug}",
        ))

    if old_st.minimum_duration_weeks != new_st.minimum_duration_weeks:
        changes.append(_make_change(
            "prior_auth.step_therapy.minimum_duration_weeks", ChangeType.MODIFIED,
            old_st.minimum_duration_weeks, new_st.minimum_duration_weeks,
            f"Minimum step therapy duration changed: {old_st.minimum_duration_weeks}wk → {new_st.minimum_duration_weeks}wk",
        ))

    # ── Exclusion criteria ───────────────────────────────────────────────────
    old_excl, new_excl = set(old_pa.exclusion_criteria), set(new_pa.exclusion_criteria)
    for added in (new_excl - old_excl):
        changes.append(_make_change(
            "prior_auth.exclusion_criteria", ChangeType.CRITERIA_ADDED,
            None, added, f"Exclusion criterion added: '{added}'",
        ))
    for removed in (old_excl - new_excl):
        changes.append(_make_change(
            "prior_auth.exclusion_criteria", ChangeType.CRITERIA_REMOVED,
            removed, None, f"Exclusion criterion removed: '{removed}'",
        ))

    # ── Auth duration ────────────────────────────────────────────────────────
    if old_pa.initial_auth_duration_months != new_pa.initial_auth_duration_months:
        changes.append(_make_change(
            "prior_auth.initial_auth_duration_months", ChangeType.MODIFIED,
            old_pa.initial_auth_duration_months, new_pa.initial_auth_duration_months,
            f"Auth duration changed: {old_pa.initial_auth_duration_months}mo → {new_pa.initial_auth_duration_months}mo",
        ))

    # ── Renewal ──────────────────────────────────────────────────────────────
    if old_pa.renewal_required != new_pa.renewal_required:
        changes.append(_make_change(
            "prior_auth.renewal_required", ChangeType.MODIFIED,
            old_pa.renewal_required, new_pa.renewal_required,
            f"Renewal requirement {'added' if new_pa.renewal_required else 'removed'}",
        ))

    # ── Site of care ─────────────────────────────────────────────────────────
    old_sites = set(s.value for s in old.site_of_care)
    new_sites = set(s.value for s in new.site_of_care)
    if old_sites != new_sites:
        changes.append(_make_change(
            "site_of_care", ChangeType.MODIFIED,
            ", ".join(sorted(old_sites)), ", ".join(sorted(new_sites)),
            f"Site of care changed: {', '.join(sorted(old_sites))} → {', '.join(sorted(new_sites))}",
        ))

    # ── Quantity limit ───────────────────────────────────────────────────────
    old_ql, new_ql = old.quantity_limit, new.quantity_limit
    if old_ql.applies != new_ql.applies:
        changes.append(_make_change(
            "quantity_limit.applies", ChangeType.MODIFIED,
            old_ql.applies, new_ql.applies,
            f"Quantity limit {'added' if new_ql.applies else 'removed'}",
        ))
    elif old_ql.applies and old_ql.description != new_ql.description:
        changes.append(_make_change(
            "quantity_limit.description", ChangeType.MODIFIED,
            old_ql.description, new_ql.description,
            f"Quantity limit changed: '{old_ql.description}' → '{new_ql.description}'",
        ))

    # ── Indications ──────────────────────────────────────────────────────────
    old_ind, new_ind = set(old.indications), set(new.indications)
    for ind in (new_ind - old_ind):
        changes.append(_make_change(
            "indications", ChangeType.CRITERIA_ADDED,
            None, ind, f"Indication added: {ind}",
        ))
    for ind in (old_ind - new_ind):
        changes.append(_make_change(
            "indications", ChangeType.CRITERIA_REMOVED,
            ind, None, f"Indication removed: {ind}",
        ))

    if not changes:
        return None

    return _build_diff(new, changes, old.policy_version, old.effective_date)


def diff_new_policy(new: MedBenefitCoverage) -> PolicyDiff:
    """Create a 'new policy' diff record for a drug not previously tracked."""
    change = _make_change(
        "policy", ChangeType.NEW_POLICY, None,
        new.coverage_status.value,
        f"New policy: {new.canonical_drug_name} now tracked for {new.payer_name}",
    )
    return PolicyDiff(
        payer_name=new.payer_name,
        plan_name=new.plan_name,
        policy_id=new.policy_id,
        drug_name=new.canonical_drug_name,
        old_version="none",
        new_version=new.policy_version,
        old_effective_date=None,
        new_effective_date=new.effective_date,
        change_type=ChangeType.NEW_POLICY,
        changes=[change],
        summary=f"New policy added: {new.canonical_drug_name} ({new.coverage_status.value.replace('_',' ')})",
        clinical_changes=0,
        cosmetic_changes=0,
        administrative_changes=1,
        significance_verdict="New policy — no prior version to compare",
        detected_at=datetime.utcnow(),
    )
