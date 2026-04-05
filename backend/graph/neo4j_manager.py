"""
backend/graph/neo4j_manager.py
Knowledge Graph schema for medical benefit drug policies.

Nodes:  Drug, Payer, Plan, Policy, PolicyVersion, Criteria
Edges:  COVERED_BY, REQUIRES_PA, SUPERSEDES, PART_OF, GOVERNS, CHANGED_TO

PolicyVersion nodes store each ingested version separately so diffs
are computed against real historical data — not synthetic comparisons.
"""
import json
import logging
from neo4j import GraphDatabase
from backend.core.config import get_settings
from backend.core.models import MedBenefitCoverage, PolicyDiff

logger = logging.getLogger(__name__)


class Neo4jManager:
    def __init__(self):
        s = get_settings()
        self.driver = GraphDatabase.driver(
            s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password)
        )
        self._init_schema()

    def _init_schema(self):
        with self.driver.session() as session:
            for stmt in [
                "CREATE CONSTRAINT drug_name IF NOT EXISTS FOR (d:Drug) REQUIRE d.canonical_name IS UNIQUE",
                "CREATE CONSTRAINT payer_id IF NOT EXISTS FOR (p:Payer) REQUIRE p.name IS UNIQUE",
                "CREATE CONSTRAINT policy_id IF NOT EXISTS FOR (pol:Policy) REQUIRE pol.policy_id IS UNIQUE",
                "CREATE CONSTRAINT pv_key IF NOT EXISTS FOR (pv:PolicyVersion) REQUIRE pv.version_key IS UNIQUE",
                "CREATE INDEX cov_status IF NOT EXISTS FOR ()-[r:COVERED_BY]-() ON (r.coverage_status)",
                "CREATE INDEX cov_drug IF NOT EXISTS FOR ()-[r:COVERED_BY]-() ON (r.canonical_drug_name)",
            ]:
                try:
                    session.run(stmt)
                except Exception as e:
                    logger.debug(f"Schema: {e}")

    # ─── Writes ───────────────────────────────────────────────────────────────

    def upsert_coverage(self, cov: MedBenefitCoverage):
        """Write a normalized coverage record into the graph with versioning."""
        with self.driver.session() as session:
            session.execute_write(self._write_coverage_tx, cov)

    @staticmethod
    def _write_coverage_tx(tx, cov: MedBenefitCoverage):
        # Drug node — canonical name + all known aliases
        from backend.core.drug_master import get_normalizer
        n = get_normalizer()
        all_names = n.get_all_names(cov.canonical_drug_name)
        drug_class = n.get_drug_class(cov.canonical_drug_name)

        tx.run("""
            MERGE (d:Drug {canonical_name: $name})
            SET d.all_names = $all_names,
                d.hcpcs_codes = $hcpcs,
                d.drug_class = $drug_class
        """, name=cov.canonical_drug_name, all_names=all_names,
             hcpcs=cov.hcpcs_codes, drug_class=drug_class)

        # Payer node
        tx.run("MERGE (p:Payer {name: $name})", name=cov.payer_name)

        # Plan node
        tx.run("""
            MERGE (pl:Plan {name: $plan, payer: $payer})
            SET pl.benefit_type = 'medical_benefit'
        """, plan=cov.plan_name, payer=cov.payer_name)

        # Policy node (stable — one per policy_id)
        tx.run("""
            MERGE (pol:Policy {policy_id: $pid})
            SET pol.payer = $payer,
                pol.plan = $plan,
                pol.policy_number = $pnum
        """, pid=cov.policy_id, payer=cov.payer_name,
             plan=cov.plan_name, pnum=cov.policy_number or "")

        # PolicyVersion node — one per (policy_id, version, drug)
        version_key = f"{cov.policy_id}::{cov.policy_version}::{cov.canonical_drug_name}"
        pa = cov.prior_auth
        st = pa.step_therapy

        tx.run("""
            MERGE (pv:PolicyVersion {version_key: $vk})
            SET pv.policy_id = $pid,
                pv.version = $version,
                pv.effective_date = $eff,
                pv.drug_name = $drug,
                pv.coverage_status = $status,
                pv.pa_required = $pa_req,
                pv.pa_raw_criteria = $pa_raw,
                pv.pa_severity = $severity,
                pv.pa_exclusions = $exclusions,
                pv.pa_clinical_scores = $scores,
                pv.pa_specialties = $specialties,
                pv.pa_auth_months = $auth_months,
                pv.pa_renewal_required = $renewal,
                pv.pa_renewal_criteria = $renewal_criteria,
                pv.step_required = $step_req,
                pv.step_line = $step_line,
                pv.step_drugs = $step_drugs,
                pv.step_weeks = $step_weeks,
                pv.step_failure_def = $step_fail,
                pv.ql_applies = $ql_applies,
                pv.ql_description = $ql_desc,
                pv.site_of_care = $sites,
                pv.indications = $indications,
                pv.non_covered_indications = $non_cov,
                pv.buy_and_bill = $bb,
                pv.hcpcs_codes = $hcpcs,
                pv.extracted_at = $ext_at
        """,
            vk=version_key, pid=cov.policy_id, version=cov.policy_version,
            eff=cov.effective_date, drug=cov.canonical_drug_name,
            status=cov.coverage_status.value,
            pa_req=pa.required,
            pa_raw=pa.raw_criteria_text,
            severity=pa.severity_requirement,
            exclusions=pa.exclusion_criteria,
            scores=pa.clinical_scores,
            specialties=pa.prescriber.specialty_required,
            auth_months=pa.initial_auth_duration_months,
            renewal=pa.renewal_required,
            renewal_criteria=pa.renewal_criteria,
            step_req=st.required,
            step_line=st.line_of_therapy.value,
            step_drugs=st.required_prior_drugs,
            step_weeks=st.minimum_duration_weeks,
            step_fail=st.failure_definition,
            ql_applies=cov.quantity_limit.applies,
            ql_desc=cov.quantity_limit.description,
            sites=[s.value for s in cov.site_of_care],
            indications=cov.indications,
            non_cov=cov.non_covered_indications,
            bb=cov.requires_buy_and_bill,
            hcpcs=cov.hcpcs_codes,
            ext_at=str(cov.extracted_at),
        )

        # Relationships
        tx.run("""
            MATCH (pl:Plan {name: $plan, payer: $payer}), (p:Payer {name: $payer})
            MERGE (pl)-[:PART_OF]->(p)
        """, plan=cov.plan_name, payer=cov.payer_name)

        tx.run("""
            MATCH (pol:Policy {policy_id: $pid}), (pl:Plan {name: $plan, payer: $payer})
            MERGE (pol)-[:GOVERNS]->(pl)
        """, pid=cov.policy_id, plan=cov.plan_name, payer=cov.payer_name)

        tx.run("""
            MATCH (d:Drug {canonical_name: $drug}), (pv:PolicyVersion {version_key: $vk})
            MERGE (d)-[r:COVERED_BY]->(pv)
            SET r.coverage_status = $status,
                r.canonical_drug_name = $drug,
                r.pa_required = $pa_req
        """, drug=cov.canonical_drug_name, vk=version_key,
             status=cov.coverage_status.value, pa_req=pa.required)

        tx.run("""
            MATCH (pol:Policy {policy_id: $pid}), (pv:PolicyVersion {version_key: $vk})
            MERGE (pol)-[:HAS_VERSION]->(pv)
        """, pid=cov.policy_id, vk=version_key)

    def store_diff(self, diff: PolicyDiff):
        """Store a PolicyDiff in the graph as a CHANGED_TO edge."""
        with self.driver.session() as session:
            old_key = f"{diff.policy_id}::{diff.old_version}::{diff.drug_name}"
            new_key = f"{diff.policy_id}::{diff.new_version}::{diff.drug_name}"
            changes_json = json.dumps([c.model_dump() for c in diff.changes])
            session.run("""
                MATCH (old:PolicyVersion {version_key: $old_key})
                MATCH (new:PolicyVersion {version_key: $new_key})
                MERGE (old)-[r:CHANGED_TO]->(new)
                SET r.change_type = $ct,
                    r.summary = $summary,
                    r.changes_json = $changes,
                    r.detected_at = $det
            """, old_key=old_key, new_key=new_key,
                 ct=diff.change_type.value, summary=diff.summary,
                 changes=changes_json, det=str(diff.detected_at))

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_coverage_for_drug(self, drug_name: str, payer_names: list[str] = None) -> list[dict]:
        """Which plans cover Drug X? — with all normalized fields."""
        query = """
        MATCH (d:Drug)-[r:COVERED_BY]->(pv:PolicyVersion)<-[:HAS_VERSION]-(pol:Policy)-[:GOVERNS]->(pl:Plan)-[:PART_OF]->(p:Payer)
        WHERE (toLower(d.canonical_name) CONTAINS toLower($drug)
               OR ANY(n IN d.all_names WHERE toLower(n) CONTAINS toLower($drug)))
          AND ($payers IS NULL OR p.name IN $payers)
        WITH d, r, pv, pol, pl, p
        ORDER BY pv.effective_date DESC
        WITH d, p, pl, pol,
             HEAD(COLLECT({pv: pv, r: r})) AS latest
        RETURN
            d.canonical_name    AS canonical_drug_name,
            d.hcpcs_codes       AS hcpcs_codes,
            d.drug_class        AS drug_class,
            p.name              AS payer_name,
            pl.name             AS plan_name,
            pol.policy_id       AS policy_id,
            pol.policy_number   AS policy_number,
            latest.pv.version   AS policy_version,
            latest.pv.effective_date AS effective_date,
            latest.pv.coverage_status AS coverage_status,
            latest.pv.pa_required     AS pa_required,
            latest.pv.pa_raw_criteria AS pa_criteria,
            latest.pv.pa_severity     AS pa_severity,
            latest.pv.pa_exclusions   AS pa_exclusions,
            latest.pv.pa_clinical_scores AS clinical_scores,
            latest.pv.pa_specialties  AS prescriber_specialties,
            latest.pv.pa_auth_months  AS auth_duration_months,
            latest.pv.pa_renewal_required AS renewal_required,
            latest.pv.step_required   AS step_required,
            latest.pv.step_line       AS step_line,
            latest.pv.step_drugs      AS step_drugs,
            latest.pv.step_weeks      AS step_weeks,
            latest.pv.ql_applies      AS ql_applies,
            latest.pv.ql_description  AS ql_description,
            latest.pv.site_of_care    AS site_of_care,
            latest.pv.indications     AS indications,
            latest.pv.buy_and_bill    AS buy_and_bill
        ORDER BY p.name, pl.name
        """
        with self.driver.session() as s:
            res = s.run(query, drug=drug_name, payers=payer_names or None)
            return [dict(r) for r in res]

    def get_pa_criteria(self, drug_name: str, payer_name: str) -> list[dict]:
        """Full PA criteria for Drug X at Payer Y."""
        query = """
        MATCH (d:Drug)-[:COVERED_BY]->(pv:PolicyVersion)<-[:HAS_VERSION]-(pol:Policy)-[:GOVERNS]->(pl:Plan)-[:PART_OF]->(p:Payer)
        WHERE (toLower(d.canonical_name) CONTAINS toLower($drug)
               OR ANY(n IN d.all_names WHERE toLower(n) CONTAINS toLower($drug)))
          AND toLower(p.name) CONTAINS toLower($payer)
          AND pv.pa_required = true
        RETURN
            d.canonical_name      AS drug_name,
            p.name                AS payer_name,
            pl.name               AS plan_name,
            pol.policy_number     AS policy_number,
            pv.version            AS policy_version,
            pv.effective_date     AS effective_date,
            pv.pa_raw_criteria    AS raw_criteria,
            pv.pa_severity        AS severity,
            pv.pa_exclusions      AS exclusions,
            pv.pa_clinical_scores AS clinical_scores,
            pv.pa_specialties     AS prescriber_specialties,
            pv.pa_auth_months     AS auth_duration_months,
            pv.pa_renewal_required AS renewal_required,
            pv.pa_renewal_criteria AS renewal_criteria,
            pv.step_required      AS step_required,
            pv.step_drugs         AS step_drugs,
            pv.step_weeks         AS step_weeks,
            pv.step_line          AS step_line,
            pv.site_of_care       AS site_of_care,
            pv.indications        AS indications
        ORDER BY pv.effective_date DESC
        LIMIT 5
        """
        with self.driver.session() as s:
            res = s.run(query, drug=drug_name, payer=payer_name)
            return [dict(r) for r in res]

    def get_previous_version(self, policy_id: str, drug_name: str, current_version: str) -> dict | None:
        """Retrieve the previous PolicyVersion for diff computation."""
        query = """
        MATCH (pol:Policy {policy_id: $pid})-[:HAS_VERSION]->(pv:PolicyVersion)
        WHERE pv.drug_name = $drug AND pv.version <> $current
        RETURN pv
        ORDER BY pv.effective_date DESC
        LIMIT 1
        """
        with self.driver.session() as s:
            res = s.run(query, pid=policy_id, drug=drug_name, current=current_version)
            records = [dict(r["pv"]) for r in res]
            return records[0] if records else None

    def get_policy_changelog(
        self, payer_name: str = None, drug_name: str = None,
        since_date: str = None, change_type: str = None
    ) -> list[dict]:
        """Structured change log — what changed this quarter?"""
        query = """
        MATCH (old:PolicyVersion)-[c:CHANGED_TO]->(new:PolicyVersion)
              <-[:HAS_VERSION]-(pol:Policy)-[:GOVERNS]->(pl:Plan)-[:PART_OF]->(p:Payer)
        WHERE ($payer IS NULL OR toLower(p.name) CONTAINS toLower($payer))
          AND ($drug IS NULL OR toLower(new.drug_name) CONTAINS toLower($drug))
          AND ($since IS NULL OR c.detected_at >= $since)
          AND ($ctype IS NULL OR c.change_type = $ctype)
        RETURN
            p.name              AS payer_name,
            pl.name             AS plan_name,
            pol.policy_id       AS policy_id,
            new.drug_name       AS drug_name,
            old.version         AS old_version,
            new.version         AS new_version,
            old.effective_date  AS old_effective_date,
            new.effective_date  AS new_effective_date,
            c.change_type       AS change_type,
            c.summary           AS summary,
            c.changes_json      AS changes_json,
            c.detected_at       AS detected_at
        ORDER BY c.detected_at DESC
        LIMIT 200
        """
        with self.driver.session() as s:
            res = s.run(
                query, payer=payer_name, drug=drug_name,
                since=since_date, ctype=change_type
            )
            rows = []
            for r in res:
                row = dict(r)
                try:
                    row["changes"] = json.loads(row.pop("changes_json", "[]"))
                except Exception:
                    row["changes"] = []
                rows.append(row)
            return rows

    def get_all_payers(self) -> list[str]:
        with self.driver.session() as s:
            return [r["name"] for r in s.run("MATCH (p:Payer) RETURN p.name AS name ORDER BY name")]

    def get_all_drugs(self) -> list[str]:
        with self.driver.session() as s:
            return [r["name"] for r in s.run(
                "MATCH (d:Drug) RETURN d.canonical_name AS name ORDER BY name LIMIT 300"
            )]

    def get_drug_classes(self) -> list[str]:
        with self.driver.session() as s:
            return [r["cls"] for r in s.run(
                "MATCH (d:Drug) WHERE d.drug_class IS NOT NULL "
                "RETURN DISTINCT d.drug_class AS cls ORDER BY cls"
            )]

    def graph_stats(self) -> dict:
        with self.driver.session() as s:
            return {
                "drugs": s.run("MATCH (d:Drug) RETURN count(d) AS n").single()["n"],
                "payers": s.run("MATCH (p:Payer) RETURN count(p) AS n").single()["n"],
                "policies": s.run("MATCH (p:Policy) RETURN count(p) AS n").single()["n"],
                "policy_versions": s.run("MATCH (pv:PolicyVersion) RETURN count(pv) AS n").single()["n"],
                "coverage_edges": s.run("MATCH ()-[r:COVERED_BY]->() RETURN count(r) AS n").single()["n"],
                "change_edges": s.run("MATCH ()-[r:CHANGED_TO]->() RETURN count(r) AS n").single()["n"],
            }

    def close(self):
        self.driver.close()
