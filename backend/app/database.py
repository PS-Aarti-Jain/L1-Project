import os
import json
import math
import logging
from pathlib import Path
from app.config import settings

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

class VectorStore:
    """
    A resilient, pure-Python vector and keyword store.
    Stores chunks in a JSON file to avoid external binary DLL dependencies (like ChromaDB).
    """
    def __init__(self):
        self.db_dir = Path(settings.CHROMA_DB_DIR)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_file = self.db_dir / "document_store.json"
        self._load_data()
        
        # Compatibility shim: mock ChromaDB collection attribute
        self.collection = self
        
    def _load_data(self):
        if self.db_file.exists():
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    self.chunks = json.load(f)
                logger.info(f"Loaded {len(self.chunks)} chunks from local store at {self.db_file}")
            except Exception as e:
                logger.error(f"Failed to load document store: {str(e)}. Starting fresh.")
                self.chunks = []
        else:
            self.chunks = []

    def _save_data(self):
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.chunks, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved database store to {self.db_file}")
        except Exception as e:
            logger.error(f"Failed to save document store: {str(e)}")

    def _get_gemini_embedding(self, text: str) -> list[float]:
        """Fetches embedding for a single text chunk via Google Gemini API."""
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=[text]
        )
        return response.embeddings[0].values

    def add_chunks(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        """Adds or updates document chunks in the store."""
        if not ids:
            return

        has_api_key = bool(settings.GEMINI_API_KEY)
        logger.info(f"Adding {len(ids)} chunks to store (Embedding API Active: {has_api_key})")
        
        # Build index updates
        for idx in range(len(ids)):
            chunk_id = ids[idx]
            doc_text = documents[idx]
            meta = metadatas[idx]
            
            # Remove any existing chunk with same ID to prevent duplication
            self.chunks = [c for c in self.chunks if c["id"] != chunk_id]
            
            # Fetch embedding if API key is present
            embedding = None
            if has_api_key:
                try:
                    embedding = self._get_gemini_embedding(doc_text)
                except Exception as e:
                    logger.error(f"Error fetching embedding for chunk {chunk_id}: {str(e)}")
            
            self.chunks.append({
                "id": chunk_id,
                "document": doc_text,
                "metadata": meta,
                "embedding": embedding
            })
            
        self._save_data()

    def delete_by_metadata(self, key: str, value: str):
        """Deletes all chunks matching a specific metadata filter (e.g. source_file)."""
        initial_count = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["metadata"].get(key) != value]
        if len(self.chunks) != initial_count:
            logger.info(f"Deleted {initial_count - len(self.chunks)} chunks where {key}={value}")
            self._save_data()

    def query(self, query_text: str, n_results: int = 5, source_filter: str = None) -> list[dict]:
        """Queries the local store using cosine similarity (if embeddings exist) or keyword search."""
        logger.info(f"Querying document store for: '{query_text}' (filter: {source_filter})")
        
        # 1. Apply metadata source filter
        filtered_chunks = self.chunks
        if source_filter:
            filtered_chunks = [c for c in self.chunks if c["metadata"].get("source_file") == source_filter]
            
        if not filtered_chunks:
            return []

        # 2. Determine search strategy: Vector search vs Keyword match
        has_api_key = bool(settings.GEMINI_API_KEY)
        has_stored_embeddings = any(c.get("embedding") is not None for c in filtered_chunks)
        
        results = []
        
        if has_api_key and has_stored_embeddings:
            try:
                # Get query vector
                query_vector = self._get_gemini_embedding(query_text)
                
                # Compute scores
                for chunk in filtered_chunks:
                    chunk_vector = chunk.get("embedding")
                    if chunk_vector:
                        score = cosine_similarity(query_vector, chunk_vector)
                        # We convert similarity to a distance-like value or return direct score
                        # For consistent interfaces, we return the raw score as 1 - similarity (distance)
                        results.append({
                            "id": chunk["id"],
                            "document": chunk["document"],
                            "metadata": chunk["metadata"],
                            "distance": 1.0 - score  # lower is closer
                        })
                # Sort by distance ascending (closest first)
                results.sort(key=lambda x: x["distance"])
                
            except Exception as e:
                logger.error(f"Vector search failed, falling back to keyword search: {str(e)}")
                results = []
                
        # Fallback to keyword matching if vector search is unavailable/fails
        if not results:
            logger.info("Using keyword relevance search for ranking")
            for chunk in filtered_chunks:
                score = compute_keyword_score(query_text, chunk["document"])
                if score > 0:
                    results.append({
                        "id": chunk["id"],
                        "document": chunk["document"],
                        "metadata": chunk["metadata"],
                        # Distance inverse of score so sorting matches distance logic
                        "distance": 1.0 / (score + 0.001)
                    })
            # Sort by distance ascending (closest first)
            results.sort(key=lambda x: x["distance"])

        return results[:n_results]

    def reset_collection(self):
        """Resets the collection by clearing the chunks in memory and saving."""
        logger.warning("Resetting local document store...")
        self.chunks = []
        self._save_data()

    def get_stats(self) -> dict:
        """Returns statistics about the store."""
        return {
            "total_chunks": len(self.chunks),
            "collection_name": "local_document_store",
        }

    # Compatibility methods shimming ChromaDB's collection
    def get(self, where: dict = None, limit: int = None, include: list = None) -> dict:
        """Shims collection.get for RAG ingestion hash matching."""
        filtered = self.chunks
        if where:
            for key, val in where.items():
                filtered = [c for c in filtered if c["metadata"].get(key) == val]
        
        if limit:
            filtered = filtered[:limit]
            
        return {
            "ids": [c["id"] for c in filtered],
            "documents": [c["document"] for c in filtered],
            "metadatas": [c["metadata"] for c in filtered],
        }

    def count(self) -> int:
        """Shims collection.count for health stats."""
        return len(self.chunks)

# Global singleton
vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store
