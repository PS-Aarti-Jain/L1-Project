import os
import json
import math
import logging
import requests
import uuid
from pathlib import Path
from app.config import settings

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff, PointStruct, Filter, FieldCondition, MatchValue

logger = logging.getLogger("devassist-db")

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes the cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(v1, v2))
    mag1 = math.sqrt(sum(x * x for x in v1))
    mag2 = math.sqrt(sum(x * x for x in v2))
    if mag1 * mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)

def compute_keyword_score(query: str, document: str) -> float:
    """
    Computes a simple TF-IDF-like keyword search score.
    Ranks matching documents higher, normalized by the document length.
    """
    query_tokens = set(query.lower().split())
    doc_tokens = document.lower().split()
    if not query_tokens or not doc_tokens:
        return 0.0
        
    match_count = sum(1 for token in doc_tokens if token in query_tokens)
    # Normalize by log of document word count to avoid biasing long documents
    return match_count / math.log(len(doc_tokens) + 2)

class HybridReranker:
    """
    A lightweight, zero-dependency Hybrid Semantic-Lexical Reranker.
    Combines the semantic Cosine score from Qdrant with keyword correlation
    scores to rerank retrieved documents.
    """
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha  # Weights: alpha * semantic + (1 - alpha) * lexical

    def rerank(self, query: str, candidates: list[dict], n_results: int) -> list[dict]:
        if not candidates:
            return []

        reranked_results = []
        for candidate in candidates:
            # Semantic score is 1.0 - distance (since distance is 1.0 - similarity)
            semantic_score = 1.0 - candidate["distance"]
            
            # Lexical score is based on token frequency overlaps
            lex_score = compute_keyword_score(query, candidate["document"])
            
            # Combine scores (normalize lexical score to max 1.0)
            combined_score = self.alpha * semantic_score + (1.0 - self.alpha) * min(lex_score, 1.0)
            
            # Map back to a distance value where lower is closer
            new_distance = 1.0 - combined_score
            
            reranked_results.append({
                "id": candidate["id"],
                "document": candidate["document"],
                "metadata": candidate["metadata"],
                "distance": new_distance,
                "raw_semantic_score": candidate.get("raw_semantic_score", semantic_score),
                "lexical_score": min(lex_score, 1.0),
                "combined_score": combined_score
            })

        # Sort by distance ascending (closest first)
        reranked_results.sort(key=lambda x: x["distance"])
        return reranked_results[:n_results]

class VectorStore:
    """
    A high-performance Qdrant vector database store.
    Configured with HNSW indices and a Hybrid Semantic-Lexical Reranker.
    """
    def __init__(self):
        self.db_dir = Path(settings.QDRANT_DB_DIR)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize client pointing to local storage folder
        self.client = QdrantClient(path=str(self.db_dir))
        self.collection_name = "docs"
        self._ensure_collection()
        self.reranker = HybridReranker(alpha=0.5)
        
        # Compatibility shim: mock ChromaDB collection attribute
        self.collection = self

    def _get_embedding_dimension(self) -> int:
        """Determines the correct vector embedding dimension for the chosen embedding provider."""
        provider = settings.EMBEDDING_PROVIDER.lower()
        if provider == "fastembed":
            return 384
        elif provider == "sentence-transformers":
            try:
                if not hasattr(self, "_sentence_transformer_model"):
                    from sentence_transformers import SentenceTransformer
                    model_name = settings.EMBEDDING_MODEL or "all-MiniLM-L6-v2"
                    self._sentence_transformer_model = SentenceTransformer(model_name)
                return self._sentence_transformer_model.get_sentence_embedding_dimension()
            except Exception:
                pass
            return 384
        elif provider == "gemini":
            return 768
        elif provider == "ollama":
            try:
                res = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": settings.OLLAMA_MODEL, "prompt": "test"},
                    timeout=2
                )
                if res.status_code == 200:
                    return len(res.json()["embedding"])
            except Exception:
                pass
            return 4096
        return 384

    def _ensure_collection(self):
        """Creates the Qdrant collection with HNSW indexing if it doesn't exist."""
        try:
            if not self.client.collection_exists(collection_name=self.collection_name):
                dim = self._get_embedding_dimension()
                logger.info(f"Creating Qdrant collection '{self.collection_name}' (vector size: {dim}) with HNSW indexing...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=dim,
                        distance=Distance.COSINE
                    ),
                    hnsw_config=HnswConfigDiff(
                        m=16,             # Max links per node in graph
                        ef_construct=100  # Graph construction search budget
                    )
                )
        except Exception as e:
            logger.error(f"Failed to verify or create Qdrant collection: {str(e)}")

    def _get_embedding(self, text: str) -> list[float]:
        """Fetches embedding vector via chosen provider."""
        provider = settings.EMBEDDING_PROVIDER.lower()
        if provider == "fastembed":
            if not hasattr(self, "_fastembed_model"):
                from fastembed import TextEmbedding
                model_name = settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5"
                self._fastembed_model = TextEmbedding(model_name=model_name)
            embeddings = list(self._fastembed_model.embed([text]))
            return [float(x) for x in embeddings[0]]
        elif provider == "sentence-transformers":
            if not hasattr(self, "_sentence_transformer_model"):
                from sentence_transformers import SentenceTransformer
                model_name = settings.EMBEDDING_MODEL or "all-MiniLM-L6-v2"
                self._sentence_transformer_model = SentenceTransformer(model_name)
            embedding = self._sentence_transformer_model.encode(text)
            return [float(x) for x in embedding]
        elif provider == "gemini":
            from google import genai
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not configured but gemini embedding provider is selected.")
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=[text]
            )
            return [float(x) for x in response.embeddings[0].values]
        elif provider == "ollama":
            res = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": settings.OLLAMA_MODEL, "prompt": text},
                timeout=10
            )
            if res.status_code != 200:
                raise RuntimeError(f"Ollama embedding failed: {res.text}")
            return [float(x) for x in res.json()["embedding"]]
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

    def add_chunks(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        """Adds or updates document chunks in Qdrant. Rejects indexing if embedding fails."""
        if not ids:
            return

        expected_dim = self._get_embedding_dimension()
        logger.info(f"Adding {len(ids)} chunks to Qdrant using embedding provider: {settings.EMBEDDING_PROVIDER}")
        
        points = []
        for idx in range(len(ids)):
            chunk_id = ids[idx]
            doc_text = documents[idx]
            meta = metadatas[idx]
            
            try:
                embedding = self._get_embedding(doc_text)
            except Exception as e:
                logger.error(f"Embedding generation failed for chunk {chunk_id}: {str(e)}")
                raise RuntimeError(f"Embedding failed: {str(e)}") from e
            
            if not embedding:
                raise ValueError(f"Embedding generation returned empty vector for chunk {chunk_id}")
                
            if len(embedding) != expected_dim:
                raise ValueError(f"Embedding dimension mismatch: expected {expected_dim}, got {len(embedding)}")

            stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

            points.append(PointStruct(
                id=stable_uuid,
                vector=embedding,
                payload={
                    "id": chunk_id,
                    "document": doc_text,
                    "metadata": meta,
                    "has_real_embedding": True
                }
            ))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        logger.info(f"Successfully upserted {len(points)} chunks into Qdrant docs collection.")

    def delete_by_metadata(self, key: str, value: str):
        """Deletes all chunks matching a specific metadata filter."""
        logger.info(f"Deleting chunks in Qdrant where metadata.{key} == {value}")
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=f"metadata.{key}",
                            match=MatchValue(value=value)
                        )
                    ]
                )
            )
        except Exception as e:
            logger.error(f"Failed to delete chunks from Qdrant: {str(e)}")

    def query(self, query_text: str, n_results: int = 5, source_filter: str = None) -> list[dict]:
        """Queries Qdrant using HNSW vector similarity, then refines with Hybrid Reranking."""
        logger.info(f"Querying Qdrant index for: '{query_text}' (filter: {source_filter})")
        
        provider = settings.EMBEDDING_PROVIDER.lower()
        has_embedding_service = True
        if provider == "gemini" and not settings.GEMINI_API_KEY:
            has_embedding_service = False
            
        results = []

        if has_embedding_service:
            try:
                # 1. Fetch query vector
                query_vector = self._get_embedding(query_text)
                
                # 2. Setup source filter
                filter_obj = None
                if source_filter:
                    filter_obj = Filter(
                        must=[
                            FieldCondition(
                                key="metadata.source_file",
                                match=MatchValue(value=source_filter)
                            )
                        ]
                    )
                
                # 3. Retrieve candidates (n_results * 3, up to 15) for rerank cross-examination
                candidate_limit = max(12, n_results * 3)
                search_results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=filter_obj,
                    limit=candidate_limit,
                    with_payload=True
                )
                
                candidates = []
                for r in search_results.points:
                    candidates.append({
                        "id": r.payload["id"],
                        "document": r.payload["document"],
                        "metadata": r.payload["metadata"],
                        "distance": 1.0 - r.score,
                        "raw_semantic_score": r.score
                    })
                
                # 4. Apply Hybrid Lexical-Semantic Reranker
                results = self.reranker.rerank(query_text, candidates, n_results)
                
            except Exception as e:
                logger.error(f"Vector search failed, falling back to scroll-based keyword search: {str(e)}")
                results = []

        # Fallback keyword matching (scrolling and scoring documents locally)
        if not results:
            logger.info("Using scroll-based keyword search fallback")
            try:
                scroll_filter = None
                if source_filter:
                    scroll_filter = Filter(
                        must=[
                            FieldCondition(
                                key="metadata.source_file",
                                match=MatchValue(value=source_filter)
                            )
                        ]
                    )
                
                scroll_records = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    with_payload=True
                )[0]
                
                candidates = []
                for record in scroll_records:
                    score = compute_keyword_score(query_text, record.payload["document"])
                    if score > 0:
                        candidates.append({
                            "id": record.payload["id"],
                            "document": record.payload["document"],
                            "metadata": record.payload["metadata"],
                            "distance": 1.0 - min(score, 0.99),
                            "raw_semantic_score": 0.0,
                            "lexical_score": min(score, 1.0),
                            "combined_score": min(score, 1.0)
                        })
                candidates.sort(key=lambda x: x["distance"])
                results = candidates[:n_results]
            except Exception as e:
                logger.error(f"Fallback keyword query failed: {str(e)}")

        return results

    def reset_collection(self):
        """Resets the Qdrant docs collection."""
        logger.warning("Resetting Qdrant document collection...")
        try:
            if self.client.collection_exists(collection_name=self.collection_name):
                self.client.delete_collection(collection_name=self.collection_name)
            self._ensure_collection()
        except Exception as e:
            logger.error(f"Failed to reset Qdrant collection: {str(e)}")

    def get_stats(self) -> dict:
        """Returns statistics about the Qdrant storage."""
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "total_chunks": info.points_count,
                "collection_name": self.collection_name,
                "path": str(self.db_dir)
            }
        except Exception:
            return {
                "total_chunks": 0,
                "collection_name": self.collection_name,
                "path": str(self.db_dir)
            }

    # Compatibility methods shimming ChromaDB's collection get APIs
    def get(self, where: dict = None, limit: int = None, include: list = None) -> dict:
        """Shims collection.get for RAG ingestion hash checks."""
        try:
            filter_conditions = []
            if where:
                for k, v in where.items():
                    filter_conditions.append(
                        FieldCondition(
                            key=f"metadata.{k}",
                            match=MatchValue(value=v)
                        )
                    )
            scroll_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            scroll_records = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=limit or 100,
                with_payload=True
            )[0]
            
            return {
                "ids": [p.payload["id"] for p in scroll_records],  # Return original string ID
                "documents": [p.payload["document"] for p in scroll_records],
                "metadatas": [p.payload["metadata"] for p in scroll_records]
            }
        except Exception as e:
            logger.error(f"Error fetching from Qdrant shim: {str(e)}")
            return {"ids": [], "documents": [], "metadatas": []}

    def count(self) -> int:
        """Shims collection.count for health stats."""
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return info.points_count
        except Exception:
            return 0

# Global singleton
vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store
