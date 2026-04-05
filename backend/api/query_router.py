"""
backend/api/query_router.py
Routes the three core problem statement queries to the right backend.
"""
import logging
from cachetools import TTLCache
from backend.graph.neo4j_manager import Neo4jManager
from backend.vector.qdrant_manager import QdrantManager
from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class QueryRouter:
    def __init__(self, graph: Neo4jManager, vector: QdrantManager):
        self.graph = graph
        self.vector = vector
        s = get_settings()
        self._cache: TTLCache = TTLCache(maxsize=s.cache_max_size, ttl=s.cache_ttl_seconds)

    def _key(self, *args) -> str:
        return ":".join(str(a) for a in args if a is not None)

    # ── Query 1: Which plans cover Drug X? ─────────────────────────────────
    def coverage_for_drug(self, drug_name: str, payer_names: list[str] = None) -> list[dict]:
        key = self._key("cov", drug_name, *sorted(payer_names or []))
        if key in self._cache:
            return self._cache[key]
        results = self.graph.get_coverage_for_drug(drug_name, payer_names or None)
        # Augment sparse results with vector search
        if len(results) < 2:
            vec = self.vector.search(f"coverage {drug_name} medical benefit", top_k=5, filter_drug=drug_name)
            for v in vec:
                if not any(r["payer_name"] == v.get("payer_name") for r in results):
                    results.append({**v, "source": "vector_fallback"})
        self._cache[key] = results
        return results

    # ── Query 2: What PA criteria does Plan Y require for Drug Z? ──────────
    def pa_criteria(self, drug_name: str, payer_name: str) -> list[dict]:
        key = self._key("pa", drug_name, payer_name)
        if key in self._cache:
            return self._cache[key]
        results = self.graph.get_pa_criteria(drug_name, payer_name)
        if not results:
            results = self.vector.search(
                f"prior authorization criteria {drug_name} {payer_name}",
                top_k=4, filter_payer=payer_name
            )
        self._cache[key] = results
        return results

    # ── Query 3: What changed this quarter? ────────────────────────────────
    def policy_changelog(self, payer_name=None, drug_name=None,
                         since_date=None, change_type=None) -> list[dict]:
        return self.graph.get_policy_changelog(payer_name, drug_name, since_date, change_type)

    # ── Semantic search ─────────────────────────────────────────────────────
    def semantic_search(self, query: str, top_k: int = 5,
                        filter_payer=None, filter_drug=None) -> list[dict]:
        return self.vector.search(query, top_k, filter_payer, filter_drug)

    # ── Cross-payer comparison ──────────────────────────────────────────────
    def compare(self, drug_name: str, payer_names: list[str]) -> list[dict]:
        key = self._key("cmp", drug_name, *sorted(payer_names))
        if key in self._cache:
            return self._cache[key]
        results = self.graph.get_coverage_for_drug(drug_name, payer_names or None)
        self._cache[key] = results
        return results

    def invalidate(self):
        self._cache.clear()
