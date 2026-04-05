"""
backend/vector/qdrant_manager.py
Semantic search over normalized policy chunks using Qdrant + BGE-M3.
"""
import logging
import hashlib
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from backend.core.config import get_settings
from backend.core.models import MedBenefitCoverage

logger = logging.getLogger(__name__)


class QdrantManager:
    def __init__(self):
        s = get_settings()
        self.collection = s.collection_name
        self.dim = s.embedding_dim

        self.client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)
        logger.info("Loading BGE-M3 embedding model...")
        self.encoder = SentenceTransformer(s.embedding_model)
        logger.info("BGE-M3 ready")
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )
            for field in ["payer_name", "drug_name", "policy_id", "drug_class", "hcpcs_code"]:
                self.client.create_payload_index(self.collection, field, "keyword")
            logger.info(f"Created Qdrant collection: {self.collection}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"Represent this medical benefit policy text for retrieval: {t}" for t in texts]
        return self.encoder.encode(prefixed, normalize_embeddings=True).tolist()

    def index_coverage(self, cov: MedBenefitCoverage):
        """
        Index a normalized coverage record as a rich text chunk.
        The chunk is purpose-built for policy retrieval — not raw PDF text.
        """
        # Build a rich, structured text representation
        pa = cov.prior_auth
        st = pa.step_therapy
        chunk = f"""
Medical Benefit Drug Coverage Record
Payer: {cov.payer_name} | Plan: {cov.plan_name}
Drug: {cov.canonical_drug_name} | HCPCS: {', '.join(cov.hcpcs_codes)}
Coverage Status: {cov.coverage_status.value.replace('_', ' ')}
Benefit Type: Medical Benefit (Part B)
Site of Care: {', '.join(s.value.replace('_',' ') for s in cov.site_of_care)}

Indications: {'; '.join(cov.indications) if cov.indications else 'Not specified'}
Non-Covered Indications: {'; '.join(cov.non_covered_indications) if cov.non_covered_indications else 'None'}

Prior Authorization: {'Required' if pa.required else 'Not Required'}
Severity Requirement: {pa.severity_requirement or 'Not specified'}
Prescriber Requirements: {', '.join(pa.prescriber.specialty_required) or 'None'}
Step Therapy: {'Required - must try ' + ', '.join(st.required_prior_drugs) if st.required else 'Not required'}
Step Therapy Duration: {str(st.minimum_duration_weeks) + ' weeks' if st.minimum_duration_weeks else 'Not specified'}
Clinical Criteria: {'; '.join(pa.clinical_scores) if pa.clinical_scores else 'None'}
Exclusion Criteria: {'; '.join(pa.exclusion_criteria) if pa.exclusion_criteria else 'None'}
Auth Duration: {str(pa.initial_auth_duration_months) + ' months' if pa.initial_auth_duration_months else 'Not specified'}
Renewal Required: {'Yes' if pa.renewal_required else 'No'}

PA Criteria (verbatim):
{chr(10).join('• ' + c for c in pa.raw_criteria_text) if pa.raw_criteria_text else 'Not extracted'}

Quantity Limit: {cov.quantity_limit.description or 'None'}
Buy and Bill: {'Yes' if cov.requires_buy_and_bill else 'No'}
Policy Version: {cov.policy_version} | Effective: {cov.effective_date or 'Unknown'}
        """.strip()

        vector = self.embed([chunk])[0]
        chunk_id = hashlib.md5(
            f"{cov.policy_id}:{cov.policy_version}:{cov.canonical_drug_name}".encode()
        ).hexdigest()

        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(
                id=str(uuid.UUID(chunk_id)),
                vector=vector,
                payload={
                    "text": chunk,
                    "payer_name": cov.payer_name,
                    "plan_name": cov.plan_name,
                    "policy_id": cov.policy_id,
                    "policy_version": cov.policy_version,
                    "drug_name": cov.canonical_drug_name,
                    "hcpcs_codes": cov.hcpcs_codes,
                    "drug_class": "",  # filled by caller via drug_master
                    "coverage_status": cov.coverage_status.value,
                    "pa_required": cov.prior_auth.required,
                },
            )]
        )

    def index_raw_chunks(self, chunks: list[str], payer_name: str,
                         plan_name: str, policy_id: str, policy_version: str):
        """Index raw PDF text chunks for full-text fallback search."""
        if not chunks:
            return
        vectors = self.embed(chunks)
        points = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            cid = hashlib.md5(f"{policy_id}:raw:{i}:{chunk[:30]}".encode()).hexdigest()
            points.append(PointStruct(
                id=str(uuid.UUID(cid)),
                vector=vec,
                payload={
                    "text": chunk, "payer_name": payer_name,
                    "plan_name": plan_name, "policy_id": policy_id,
                    "policy_version": policy_version,
                    "drug_name": "", "chunk_type": "raw",
                },
            ))
        for i in range(0, len(points), 50):
            self.client.upsert(collection_name=self.collection, points=points[i:i+50])

    def search(self, query: str, top_k: int = 5,
               filter_payer: str = None, filter_drug: str = None) -> list[dict]:
        vector = self.embed([query])[0]
        conditions = []
        if filter_payer:
            conditions.append(FieldCondition(key="payer_name", match=MatchValue(value=filter_payer)))
        if filter_drug:
            conditions.append(FieldCondition(key="drug_name", match=MatchValue(value=filter_drug)))

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=Filter(must=conditions) if conditions else None,
            limit=top_k,
            with_payload=True,
        )
        return [{"text": r.payload.get("text", ""), **r.payload, "score": r.score} for r in results]

    def stats(self) -> dict:
        info = self.client.get_collection(self.collection)
        return {"total_vectors": info.points_count, "collection": self.collection}
