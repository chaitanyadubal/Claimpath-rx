"""
backend/main.py
FastAPI app — purpose-built for the Medical Benefit Drug Policy Tracker.

Three primary use cases:
  1. GET  /coverage/{drug}         — Which plans cover Drug X?
  2. GET  /pa/{drug}/{payer}       — What PA criteria does Plan Y require for Drug Z?
  3. GET  /changelog               — What changed across payer policies this quarter?

Plus:
  POST /ingest/url                 — Ingest from public payer URL
  POST /ingest/upload              — Upload PDF directly
  POST /compare                   — Side-by-side normalized comparison
  POST /search                    — Semantic search
  GET  /drugs, /payers, /stats    — Discovery endpoints
"""
import asyncio
import logging
import tempfile
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.core.config import get_settings
from backend.core.models import SearchRequest, CompareRequest, ChangelogRequest
from backend.graph.neo4j_manager import Neo4jManager
from backend.vector.qdrant_manager import QdrantManager
from backend.api.query_router import QueryRouter
from backend.ingestion.pdf_parser import PolicyPDFParser
from backend.ingestion.llm_extractor import LLMExtractor
from backend.diff.policy_differ import diff_coverage, diff_new_policy
from backend.crawler.payer_crawler import auto_discover_and_ingest, PAYER_CONFIGS
from backend.core.drug_master import get_normalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

graph_mgr: Neo4jManager = None
vector_mgr: QdrantManager = None
router: QueryRouter = None
parser: PolicyPDFParser = None
extractor: LLMExtractor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_mgr, vector_mgr, router, parser, extractor
    logger.info("Initializing MedBenefit services...")
    graph_mgr = Neo4jManager()
    vector_mgr = QdrantManager()
    router = QueryRouter(graph_mgr, vector_mgr)
    parser = PolicyPDFParser()
    extractor = LLMExtractor()
    logger.info("Ready")
    yield
    graph_mgr.close()


app = FastAPI(
    title="Medical Benefit Drug Policy Tracker",
    description=(
        "AI-powered system that ingests, parses, and normalizes medical policy documents "
        "from multiple health plans to create a searchable, comparable view of medical "
        "benefit drug coverage."
    ),
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Request models ───────────────────────────────────────────────────────────

class IngestURLRequest(BaseModel):
    url: str
    payer_name: str
    plan_name: str
    policy_id: str
    policy_version: str
    policy_number: Optional[str] = None
    effective_date: Optional[str] = None


# ─── Core ingestion pipeline ─────────────────────────────────────────────────

def _run_ingestion(file_path, payer_name, plan_name,
                   policy_id, policy_version, policy_number="", effective_date="") -> dict:
    """
    Full pipeline:
    1. Parse PDF → structured text + tables
    2. Chunk text
    3. LLM extracts normalized MedBenefitCoverage records
    4. For each drug: diff against previous version, store diff
    5. Write coverage to Knowledge Graph
    6. Index normalized chunk + raw chunks in vector store
    """
    from backend.core.drug_master import get_normalizer
    norm = get_normalizer()

    parsed = parser.parse(file_path)
    chunks = parser.chunk_text(parsed["text"])

    coverages = extractor.extract_from_document(
        chunks, payer_name, plan_name, policy_id, policy_version,
        policy_number, effective_date
    )

    diffs_created = 0
    for cov in coverages:
        # Check for previous version — compute diff if exists
        prev = graph_mgr.get_previous_version(policy_id, cov.canonical_drug_name, policy_version)
        if prev:
            # Reconstruct a MedBenefitCoverage-like object from graph data for diffing
            from backend.core.models import (
                MedBenefitCoverage, CoverageStatus, SiteOfCare,
                PriorAuthCriteria, StepTherapyRequirement, QuantityLimit,
                PresciberRequirement, LineOfTherapy
            )
            try:
                old_cov = MedBenefitCoverage(
                    canonical_drug_name=prev.get("drug_name", cov.canonical_drug_name),
                    payer_name=payer_name, plan_name=plan_name,
                    policy_id=policy_id,
                    policy_version=prev.get("version", "unknown"),
                    effective_date=prev.get("effective_date"),
                    coverage_status=CoverageStatus(prev.get("coverage_status", "covered")),
                    site_of_care=[SiteOfCare(s) for s in (prev.get("site_of_care") or ["not_specified"])],
                    indications=prev.get("indications") or [],
                    quantity_limit=QuantityLimit(
                        applies=prev.get("ql_applies", False),
                        description=prev.get("ql_description"),
                    ),
                    prior_auth=PriorAuthCriteria(
                        required=prev.get("pa_required", False),
                        raw_criteria_text=prev.get("pa_raw_criteria") or [],
                        exclusion_criteria=prev.get("pa_exclusions") or [],
                        clinical_scores=prev.get("pa_clinical_scores") or [],
                        severity_requirement=prev.get("pa_severity"),
                        initial_auth_duration_months=prev.get("pa_auth_months"),
                        renewal_required=prev.get("pa_renewal_required", False),
                        renewal_criteria=prev.get("pa_renewal_criteria") or [],
                        prescriber=PresciberRequirement(
                            specialty_required=prev.get("pa_specialties") or []
                        ),
                        step_therapy=StepTherapyRequirement(
                            required=prev.get("step_required", False),
                            required_prior_drugs=prev.get("step_drugs") or [],
                            minimum_duration_weeks=prev.get("step_weeks"),
                            line_of_therapy=LineOfTherapy(prev.get("step_line", "any")),
                        ),
                    ),
                )
                diff = diff_coverage(old_cov, cov)
                if diff:
                    graph_mgr.store_diff(diff)
                    diffs_created += 1
            except Exception as e:
                logger.warning(f"Diff failed for {cov.canonical_drug_name}: {e}")
        else:
            # First time seeing this drug — create a NEW_POLICY diff
            new_diff = diff_new_policy(cov)
            graph_mgr.store_diff(new_diff)
            diffs_created += 1

        # Write to graph
        graph_mgr.upsert_coverage(cov)

        # Index normalized coverage record in vector store
        vector_mgr.index_coverage(cov)

    # Also index raw chunks for full-text fallback
    vector_mgr.index_raw_chunks(chunks, payer_name, plan_name, policy_id, policy_version)

    router.invalidate()

    return {
        "drugs_extracted": len(coverages),
        "chunks_indexed": len(chunks),
        "diffs_created": diffs_created,
        "parser_used": parsed.get("parser", "unknown"),
        "pages": parsed.get("pages", 0),
        "drug_names": [c.canonical_drug_name for c in coverages],
    }


# ─── Ingestion endpoints ──────────────────────────────────────────────────────

@app.post("/ingest/url")
async def ingest_url(req: IngestURLRequest):
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(req.url, follow_redirects=True)
        if resp.status_code != 200:
            raise HTTPException(400, f"Download failed: {resp.status_code}")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        tmp = f.name
    try:
        result = await asyncio.to_thread(
            _run_ingestion, tmp, req.payer_name, req.plan_name,
            req.policy_id, req.policy_version, req.policy_number or "", req.effective_date or ""
        )
        return {"status": "success", **result}
    finally:
        os.unlink(tmp)


@app.post("/ingest/upload")
async def ingest_upload(
    file: UploadFile = File(...),
    payer_name: str = "Unknown",
    plan_name: str = "Unknown Plan",
    policy_id: str = "upload",
    policy_version: str = "1.0",
    policy_number: str = "",
    effective_date: str = "",
):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(await file.read())
        tmp = f.name
    try:
        result = await asyncio.to_thread(
            _run_ingestion, tmp, payer_name, plan_name,
            policy_id, policy_version, policy_number, effective_date
        )
        return {"status": "success", "filename": file.filename, **result}
    finally:
        os.unlink(tmp)


# ─── Use Case 1: Which plans cover Drug X? ───────────────────────────────────

@app.get("/coverage/{drug_name}")
async def coverage_for_drug(
    drug_name: str,
    payers: Optional[str] = Query(None, description="Comma-separated payer names"),
):
    """Which plans cover Drug X? Returns normalized coverage across all payers."""
    payer_list = [p.strip() for p in payers.split(",")] if payers else None
    results = router.coverage_for_drug(drug_name, payer_list)
    if not results:
        raise HTTPException(404, f"No coverage data for '{drug_name}'")
    return {
        "drug": drug_name,
        "total_plans": len(results),
        "coverage": results,
    }


# ─── Use Case 2: What PA criteria does Plan Y require for Drug Z? ────────────

@app.get("/pa/{drug_name}/{payer_name}")
async def pa_criteria(drug_name: str, payer_name: str):
    """Full prior auth criteria for Drug Z at Payer Y — normalized and structured."""
    results = router.pa_criteria(drug_name, payer_name)
    if not results:
        raise HTTPException(404, f"No PA criteria found for {drug_name} / {payer_name}")
    return {
        "drug": drug_name,
        "payer": payer_name,
        "criteria": results,
    }


# ─── Use Case 3: What changed across payer policies this quarter? ─────────────

@app.get("/changelog")
async def policy_changelog(
    payer: Optional[str] = None,
    drug: Optional[str] = None,
    since: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    change_type: Optional[str] = None,
):
    """
    Clause-level policy change log.
    Answers: What changed across payer policies this quarter?
    """
    results = router.policy_changelog(payer, drug, since, change_type)
    return {
        "total_changes": len(results),
        "filters": {"payer": payer, "drug": drug, "since": since, "change_type": change_type},
        "changes": results,
    }


# ─── Comparison endpoint ──────────────────────────────────────────────────────

@app.post("/compare")
async def compare_drug(req: CompareRequest):
    """
    Normalized side-by-side comparison of Drug X coverage across multiple payers.
    All fields use the same schema regardless of source payer.
    """
    results = router.compare(req.drug_name, req.payer_names)
    if not results:
        raise HTTPException(404, f"No comparison data for '{req.drug_name}'")

    # Build normalized comparison matrix
    comparison_matrix = []
    fields = [
        "payer_name", "plan_name", "coverage_status", "hcpcs_codes",
        "pa_required", "pa_severity", "pa_specialties",
        "step_required", "step_drugs", "step_weeks", "step_line",
        "ql_applies", "ql_description",
        "site_of_care", "buy_and_bill",
        "auth_duration_months", "renewal_required",
        "policy_version", "effective_date",
    ]
    for r in results:
        row = {f: r.get(f) for f in fields}
        comparison_matrix.append(row)

    return {
        "drug": req.drug_name,
        "payers_compared": len(results),
        "fields": fields,
        "comparison": comparison_matrix,
    }


# ─── Semantic search ─────────────────────────────────────────────────────────

@app.post("/search")
async def semantic_search(req: SearchRequest):
    results = router.semantic_search(req.query, req.top_k, req.filter_payer, req.filter_drug)
    return {"query": req.query, "results": results}


# ─── Discovery ───────────────────────────────────────────────────────────────

@app.get("/payers")
async def list_payers():
    return {"payers": graph_mgr.get_all_payers()}

@app.get("/drugs")
async def list_drugs():
    return {"drugs": graph_mgr.get_all_drugs()}

@app.get("/drug-classes")
async def list_drug_classes():
    return {"classes": graph_mgr.get_drug_classes()}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}

@app.get("/stats")
async def stats():
    return {
        "graph": graph_mgr.graph_stats(),
        "vector": vector_mgr.stats(),
    }


# ─── Gap 1: Automated Policy Retrieval ───────────────────────────────────────

class AutoIngestRequest(BaseModel):
    drug_name: str
    payer_keys: list[str] = []   # empty = all supported payers


@app.post("/auto-ingest")
async def auto_ingest(req: AutoIngestRequest):
    """
    Gap 1 — Automated policy retrieval.
    Discovers and ingests policy PDFs from payer websites automatically.
    No manual URL entry required — the system finds the right documents.
    """
    async def _ingest_bytes(pdf_bytes, payer_name, plan_name, policy_id,
                            policy_version, policy_number, effective_date):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = f.name
        try:
            return await asyncio.to_thread(
                _run_ingestion, tmp, payer_name, plan_name,
                policy_id, policy_version, policy_number, effective_date
            )
        finally:
            os.unlink(tmp)

    summary = await auto_discover_and_ingest(
        drug_name=req.drug_name,
        payer_keys=req.payer_keys or list(PAYER_CONFIGS.keys()),
        ingest_fn=_ingest_bytes,
    )
    return {"status": "complete", **summary}


@app.get("/supported-payers")
async def supported_payers():
    """List all payers the auto-crawler supports."""
    return {
        "payers": [
            {
                "key": k,
                "name": v["name"],
                "plan": v["plan"],
                "strategy": v["strategy"],
                "search_url": v["search_url"],
            }
            for k, v in PAYER_CONFIGS.items()
        ]
    }


# ─── Gap 2: Competitive Position / Category Intelligence ─────────────────────

@app.get("/competitive/{drug_name}")
async def competitive_position(drug_name: str):
    """
    Gap 2 — Drug category competitive position.
    Returns a drug's position within its therapeutic class:
    class size, competitors, biosimilar count, rebate economics context.
    This is the market access intelligence Anton Rx analysts need.
    """
    norm = get_normalizer()
    position = norm.get_competitive_position(drug_name)
    if not position["drug_class"]:
        raise HTTPException(404, f"Drug '{drug_name}' not found in master reference")

    # Enrich with coverage data from graph — how many payers cover this drug?
    coverage_data = graph_mgr.get_coverage_for_drug(drug_name)
    payers_covering = len(set(r["payer_name"] for r in coverage_data))
    pa_required_count = sum(1 for r in coverage_data if r.get("pa_required"))

    return {
        **position,
        "payers_tracking": payers_covering,
        "payers_requiring_pa": pa_required_count,
        "coverage_summary": [
            {
                "payer": r["payer_name"],
                "status": r["coverage_status"],
                "pa_required": r.get("pa_required", False),
            }
            for r in coverage_data
        ],
    }


@app.get("/class-landscape/{drug_class}")
async def class_landscape(drug_class: str):
    """
    Gap 2 — Full therapeutic class landscape.
    Shows all drugs in a class with competitive position data.
    Answers: 'How does Drug X compare to its class peers?'
    """
    norm = get_normalizer()
    landscape = norm.get_class_landscape(drug_class)
    if not landscape:
        raise HTTPException(404, f"No drugs found for class '{drug_class}'")
    return {"drug_class": drug_class, "drugs": landscape, "class_size": len(landscape)}
