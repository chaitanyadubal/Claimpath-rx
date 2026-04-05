"""
backend/core/drug_master.py
Drug normalization engine.

The #1 cross-payer normalization problem: the same drug is referred to as:
  "adalimumab", "Humira", "Hadlima", "Hyrimoz", "Cyltezo", "J0135", "ADA"
  depending on which payer wrote the policy.

This module resolves ALL of those to one canonical name so cross-payer
comparison is actually possible.

Data source: embedded reference built from:
  - FDA Orange/Purple Book (biologics/biosimilars)
  - CMS HCPCS J-code assignments
  - RxNorm CUI mappings
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class DrugEntry:
    canonical: str
    brand_names: list[str] = field(default_factory=list)
    biosimilars: list[str] = field(default_factory=list)
    hcpcs: list[str] = field(default_factory=list)
    drug_class: str = ""
    route: str = ""
    is_biologic: bool = True
    # ── Competitive / market access fields (Gap 2) ─────────────────────────
    # These drive rebate economics — preferred 1-of-2 vs 1-of-3 vs exclusive
    # are completely different rebate situations for Anton Rx clients
    therapeutic_category: str = ""          # broader grouping e.g. "Inflammatory"
    competitors_in_class: list[str] = field(default_factory=list)  # canonical names of competitors
    mechanism_short: str = ""               # "Anti-TNFα", "IL-17A", "PD-1" for grouping


# ─── Medical Benefit Drug Master Reference ────────────────────────────────────
# Covers the most commonly tracked medical benefit (Part B / J-code) biologics
# Source: CMS HCPCS 2024, FDA Purple Book, clinical policy bulletins

DRUG_MASTER: list[DrugEntry] = [
    # ── TNF Inhibitors ──────────────────────────────────────────────────────
    DrugEntry("adalimumab", ["Humira"], ["Hadlima","Hyrimoz","Cyltezo","Yusimry","Hulio","Abrilada","Simlandi"],
              ["J0135"], "TNF Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["infliximab","etanercept","certolizumab pegol","golimumab"], "Anti-TNFα"),
    DrugEntry("infliximab", ["Remicade"], ["Inflectra","Renflexis","Avsola","Ixifi"],
              ["J1745"], "TNF Inhibitor", "Intravenous", True,
              "Inflammatory/Autoimmune", ["adalimumab","etanercept","certolizumab pegol","golimumab"], "Anti-TNFα"),
    DrugEntry("etanercept", ["Enbrel"], ["Erelzi","Eticovo"],
              ["J1438"], "TNF Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["adalimumab","infliximab","certolizumab pegol","golimumab"], "Anti-TNFα"),
    DrugEntry("certolizumab pegol", ["Cimzia"], [],
              ["J0718"], "TNF Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["adalimumab","infliximab","etanercept","golimumab"], "Anti-TNFα"),
    DrugEntry("golimumab", ["Simponi","Simponi Aria"], [],
              ["J0718","J0717"], "TNF Inhibitor", "Subcutaneous/Intravenous", True,
              "Inflammatory/Autoimmune", ["adalimumab","infliximab","etanercept","certolizumab pegol"], "Anti-TNFα"),

    # ── IL Inhibitors ───────────────────────────────────────────────────────
    DrugEntry("ustekinumab", ["Stelara"], ["Wezlana","Otulfi"],
              ["J3357","J3358"], "IL-12/23 Inhibitor", "Subcutaneous/Intravenous", True,
              "Inflammatory/Autoimmune", ["risankizumab","guselkumab","tildrakizumab"], "IL-12/23"),
    DrugEntry("secukinumab", ["Cosentyx"], [],
              ["J3390"], "IL-17A Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["ixekizumab","bimekizumab"], "IL-17A"),
    DrugEntry("ixekizumab", ["Taltz"], [],
              ["J2329"], "IL-17A Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["secukinumab","bimekizumab"], "IL-17A"),
    DrugEntry("bimekizumab", ["Bimzelx"], [],
              ["J0711"], "IL-17A/F Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["secukinumab","ixekizumab"], "IL-17A/F"),
    DrugEntry("guselkumab", ["Tremfya"], [],
              ["J1594"], "IL-23 Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["risankizumab","ustekinumab","tildrakizumab"], "IL-23"),
    DrugEntry("risankizumab", ["Skyrizi"], [],
              ["J3490"], "IL-23 Inhibitor", "Subcutaneous/Intravenous", True,
              "Inflammatory/Autoimmune", ["guselkumab","ustekinumab","tildrakizumab"], "IL-23"),
    DrugEntry("tildrakizumab", ["Ilumya"], [],
              ["J3490"], "IL-23 Inhibitor", "Subcutaneous", True,
              "Inflammatory/Autoimmune", ["risankizumab","guselkumab","ustekinumab"], "IL-23"),

    # ── Type 2 Inflammation / Atopic Dermatitis ─────────────────────────────
    DrugEntry("dupilumab", ["Dupixent"], [],
              ["J0223"], "IL-4/13 Inhibitor", "Subcutaneous", True,
              "Inflammatory/Atopic", ["tralokinumab","lebrikizumab"], "IL-4/13"),
    DrugEntry("tralokinumab", ["Adbry"], [],
              ["J3490"], "IL-13 Inhibitor", "Subcutaneous", True,
              "Inflammatory/Atopic", ["dupilumab","lebrikizumab"], "IL-13"),
    DrugEntry("lebrikizumab", ["Ebglyss"], [],
              ["J3490"], "IL-13 Inhibitor", "Subcutaneous", True,
              "Inflammatory/Atopic", ["dupilumab","tralokinumab"], "IL-13"),

    # ── Oncology (PD-1/PD-L1) ───────────────────────────────────────────────
    DrugEntry("pembrolizumab", ["Keytruda"], [],
              ["J9271"], "PD-1 Inhibitor", "Intravenous", True,
              "Oncology/Immunotherapy", ["nivolumab","atezolizumab","durvalumab"], "Anti-PD-1"),
    DrugEntry("nivolumab", ["Opdivo"], [],
              ["J9299"], "PD-1 Inhibitor", "Intravenous", True,
              "Oncology/Immunotherapy", ["pembrolizumab","atezolizumab","durvalumab"], "Anti-PD-1"),
    DrugEntry("atezolizumab", ["Tecentriq"], [],
              ["J9022"], "PD-L1 Inhibitor", "Intravenous", True,
              "Oncology/Immunotherapy", ["pembrolizumab","nivolumab","durvalumab"], "Anti-PD-L1"),
    DrugEntry("durvalumab", ["Imfinzi"], [],
              ["J0178"], "PD-L1 Inhibitor", "Intravenous", True,
              "Oncology/Immunotherapy", ["pembrolizumab","nivolumab","atezolizumab"], "Anti-PD-L1"),

    # ── Oncology (HER2, VEGF, CD20) ─────────────────────────────────────────
    DrugEntry("trastuzumab", ["Herceptin"], ["Kanjinti","Ogivri","Herzuma","Ontruzant","Trazimera"],
              ["J9355"], "HER2 Inhibitor", "Intravenous", True,
              "Oncology/Targeted", [], "Anti-HER2"),
    DrugEntry("bevacizumab", ["Avastin"], ["Mvasi","Zirabev","Vegzelma","Alymsys"],
              ["J9035"], "VEGF Inhibitor", "Intravenous", True,
              "Oncology/Targeted", [], "Anti-VEGF"),
    DrugEntry("rituximab", ["Rituxan"], ["Truxima","Ruxience","Riabni"],
              ["J9312"], "CD20 Inhibitor", "Intravenous", True,
              "Oncology/Autoimmune", ["ocrelizumab","ofatumumab"], "Anti-CD20"),

    # ── Neurology ───────────────────────────────────────────────────────────
    DrugEntry("natalizumab", ["Tysabri"], [],
              ["J2323"], "Anti-α4 Integrin", "Intravenous", True,
              "Neurology/MS", ["ocrelizumab","ofatumumab"], "Anti-Integrin"),
    DrugEntry("ocrelizumab", ["Ocrevus"], [],
              ["J2350"], "CD20 Inhibitor", "Intravenous", True,
              "Neurology/MS", ["natalizumab","ofatumumab"], "Anti-CD20"),
    DrugEntry("ofatumumab", ["Kesimpta"], [],
              ["J3490"], "CD20 Inhibitor", "Subcutaneous", True,
              "Neurology/MS", ["ocrelizumab","natalizumab"], "Anti-CD20"),
    DrugEntry("erenumab", ["Aimovig"], [],
              ["J3490"], "CGRP Inhibitor", "Subcutaneous", True,
              "Neurology/Migraine", [], "Anti-CGRP"),

    # ── Respiratory / Asthma ────────────────────────────────────────────────
    DrugEntry("mepolizumab", ["Nucala"], [],
              ["J2182"], "IL-5 Inhibitor", "Subcutaneous", True,
              "Respiratory/Asthma", ["benralizumab","tezepelumab"], "Anti-IL-5"),
    DrugEntry("benralizumab", ["Fasenra"], [],
              ["J0517"], "IL-5Rα Inhibitor", "Subcutaneous", True,
              "Respiratory/Asthma", ["mepolizumab","tezepelumab"], "Anti-IL-5Rα"),
    DrugEntry("tezepelumab", ["Tezspire"], [],
              ["J3490"], "TSLP Inhibitor", "Subcutaneous", True,
              "Respiratory/Asthma", ["mepolizumab","benralizumab"], "Anti-TSLP"),

    # ── Ophthalmology ───────────────────────────────────────────────────────
    DrugEntry("ranibizumab", ["Lucentis"], ["Cimerli"],
              ["J2778"], "VEGF Inhibitor", "Intravitreal", True,
              "Ophthalmology/Retinal", ["aflibercept","faricimab"], "Anti-VEGF"),
    DrugEntry("aflibercept", ["Eylea"], ["Yesafili","Opuviz"],
              ["J0178"], "VEGF Inhibitor", "Intravitreal", True,
              "Ophthalmology/Retinal", ["ranibizumab","faricimab"], "Anti-VEGF"),
    DrugEntry("faricimab", ["Vabysmo"], [],
              ["J0179"], "Ang-2/VEGF Inhibitor", "Intravitreal", True,
              "Ophthalmology/Retinal", ["ranibizumab","aflibercept"], "Ang-2/VEGF"),

    # ── Osteoporosis / Bone ─────────────────────────────────────────────────
    DrugEntry("denosumab", ["Prolia","Xgeva"], ["Jubbonti","Wyost"],
              ["J0897"], "RANK Ligand Inhibitor", "Subcutaneous", True,
              "Bone/Osteoporosis", ["romosozumab"], "Anti-RANKL"),
    DrugEntry("romosozumab", ["Evenity"], [],
              ["J3490"], "Sclerostin Inhibitor", "Subcutaneous", True,
              "Bone/Osteoporosis", ["denosumab"], "Anti-Sclerostin"),

    # ── Endocrinology ───────────────────────────────────────────────────────
    DrugEntry("semaglutide", ["Ozempic","Wegovy","Rybelsus"], [],
              ["J3490"], "GLP-1 Agonist", "Subcutaneous", False,
              "Endocrinology/Metabolic", [], "GLP-1"),
    DrugEntry("lanreotide", ["Somatuline"], [],
              ["J1930"], "Somatostatin Analog", "Subcutaneous", False,
              "Endocrinology/Neuroendocrine", ["octreotide"], "Somatostatin"),
    DrugEntry("octreotide", ["Sandostatin","Sandostatin LAR"], [],
              ["J2354","J2353"], "Somatostatin Analog", "Subcutaneous/Intramuscular", False,
              "Endocrinology/Neuroendocrine", ["lanreotide"], "Somatostatin"),
]


class DrugNormalizer:
    """
    Resolves any drug name, brand name, biosimilar name, or J-code
    to the canonical drug name in the master reference.
    """

    def __init__(self):
        # Build lookup index: every known name/code → canonical name
        self._index: dict[str, str] = {}
        self._entries: dict[str, DrugEntry] = {}

        for entry in DRUG_MASTER:
            self._register(entry.canonical, entry.canonical)
            self._entries[entry.canonical] = entry
            for name in entry.brand_names:
                self._register(name, entry.canonical)
            for name in entry.biosimilars:
                self._register(name, entry.canonical)
            for code in entry.hcpcs:
                self._register(code, entry.canonical)

    def _register(self, key: str, canonical: str):
        self._index[key.lower().strip()] = canonical

    def normalize(self, raw_name: str) -> str:
        """
        Returns the canonical drug name for any input.
        Falls back to cleaned input if not in master.
        """
        if not raw_name:
            return raw_name

        # Try exact match first
        key = raw_name.lower().strip()
        if key in self._index:
            return self._index[key]

        # Try stripping parenthetical (e.g. "adalimumab (Humira)")
        stripped = re.sub(r"\s*\(.*?\)", "", raw_name).strip()
        key2 = stripped.lower()
        if key2 in self._index:
            return self._index[key2]

        # Try partial match (for names like "adalimumab-atto")
        for known, canonical in self._index.items():
            if key.startswith(known) or known.startswith(key):
                return canonical

        # Not in master — return cleaned input as-is
        return stripped or raw_name

    def get_entry(self, canonical_name: str) -> DrugEntry | None:
        return self._entries.get(canonical_name.lower())

    def get_hcpcs(self, drug_name: str) -> list[str]:
        canonical = self.normalize(drug_name)
        entry = self.get_entry(canonical)
        return entry.hcpcs if entry else []

    def get_drug_class(self, drug_name: str) -> str:
        canonical = self.normalize(drug_name)
        entry = self.get_entry(canonical)
        return entry.drug_class if entry else "Unknown"

    def get_all_names(self, drug_name: str) -> list[str]:
        """All known names for a drug — for graph alias indexing."""
        canonical = self.normalize(drug_name)
        entry = self.get_entry(canonical)
        if not entry:
            return [canonical]
        return [canonical] + entry.brand_names + entry.biosimilars

    def search_by_class(self, drug_class: str) -> list[str]:
        """Find all drugs in a class — e.g. all 'TNF Inhibitor' drugs."""
        return [
            e.canonical for e in DRUG_MASTER
            if drug_class.lower() in e.drug_class.lower()
        ]

    def get_competitive_position(self, drug_name: str) -> dict:
        """
        Returns the drug's competitive position within its class.
        This drives rebate economics for Anton Rx clients:
          - preferred 1-of-1 (exclusive) = maximum rebate leverage
          - preferred 1-of-2 = strong position
          - preferred 1-of-3+ = weaker position
        """
        canonical = self.normalize(drug_name)
        entry = self.get_entry(canonical)
        if not entry:
            return {"canonical": canonical, "competitors": [], "class_size": 0}

        competitors = entry.competitors_in_class
        class_size = len(competitors) + 1  # including the drug itself

        return {
            "canonical": canonical,
            "drug_class": entry.drug_class,
            "therapeutic_category": entry.therapeutic_category,
            "mechanism": entry.mechanism_short,
            "competitors_in_class": competitors,
            "class_size": class_size,
            "competitive_label": self._position_label(class_size),
            "has_biosimilars": len(entry.biosimilars) > 0,
            "biosimilar_count": len(entry.biosimilars),
            "rebate_context": self._rebate_context(class_size, len(entry.biosimilars)),
        }

    def _position_label(self, class_size: int) -> str:
        if class_size == 1:
            return "Exclusive — no class competitors"
        elif class_size == 2:
            return f"1-of-{class_size} in class"
        elif class_size <= 4:
            return f"1-of-{class_size} in class"
        else:
            return f"1-of-{class_size} in class (crowded)"

    def _rebate_context(self, class_size: int, biosimilar_count: int) -> str:
        parts = []
        if class_size == 1:
            parts.append("Exclusive class positioning — strong rebate leverage")
        elif class_size == 2:
            parts.append("Duopoly — moderate rebate pressure")
        else:
            parts.append(f"Competitive class ({class_size} drugs) — high rebate pressure")
        if biosimilar_count > 0:
            parts.append(f"{biosimilar_count} biosimilar(s) further compress net price")
        return "; ".join(parts)

    def get_class_landscape(self, drug_class: str) -> list[dict]:
        """
        Returns all drugs in a therapeutic class with their competitive data.
        Useful for the analyst answering: 'How does Drug X compare to its class peers?'
        """
        results = []
        for entry in DRUG_MASTER:
            if drug_class.lower() in entry.drug_class.lower() or \
               drug_class.lower() in entry.therapeutic_category.lower():
                results.append({
                    "canonical": entry.canonical,
                    "brand_names": entry.brand_names,
                    "biosimilars": entry.biosimilars,
                    "hcpcs": entry.hcpcs,
                    "drug_class": entry.drug_class,
                    "mechanism": entry.mechanism_short,
                    "route": entry.route,
                    "class_size": len(entry.competitors_in_class) + 1,
                    "biosimilar_count": len(entry.biosimilars),
                })
        return results

    @property
    def all_canonical_names(self) -> list[str]:
        return [e.canonical for e in DRUG_MASTER]


# Singleton
_normalizer: DrugNormalizer | None = None

def get_normalizer() -> DrugNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = DrugNormalizer()
    return _normalizer
