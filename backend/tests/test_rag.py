import os
import sys
from pathlib import Path

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

# Mock environment before importing settings
os.environ["GEMINI_API_KEY"] = ""  # Force local ONNX embeddings
os.environ["GITHUB_PAT"] = "fake-pat"
os.environ["GITHUB_REPOSITORY"] = "fake/repo"
os.environ["CHROMA_DB_DIR"] = str(backend_dir / "test_chroma_db")
os.environ["DOCS_DIR"] = str(backend_dir.parent / "docs")

from app.database import get_vector_store
from app.ingestion import ingest_directory

def run_rag_test():
    print("=== RUNNING RAG SUBSYSTEM TEST ===")
    
    # 1. Initialize vector store
    db = get_vector_store()
    db.reset_collection()
    print("Vector database collection reset.")
    
    # 2. Trigger directory ingestion
    print(f"Indexing directory: {os.environ['DOCS_DIR']}")
    stats = ingest_directory()
    print(f"Ingestion results: {stats}")
    
    assert stats["status"] == "success"
    assert stats["files_indexed"] >= 3, "Expected at least 3 files indexed from docs/"
    assert stats["total_chunks_in_db"] > 0, "Expected chunks to be added to db"
    
    # 3. Test semantic queries
    # Query 1: search for PAT security (should match security_guidelines.md)
    query_1 = "least privilege for github token"
    print(f"Querying for: '{query_1}'")
    results = db.query(query_1, n_results=2)
    
    print(f"Query 1 matches:")
    for r in results:
        print(f" - [{r['metadata']['source_file']}] Score: {r['distance']:.4f} | Section: {r['metadata']['heading_path']}")
        
    assert len(results) > 0, "Expected query results"
    assert results[0]["metadata"]["source_file"] == "security_guidelines.md", "Query should rank security guidelines first"
    
    # Query 2: search for uvicorn port (should match developer_setup.md)
    query_2 = "running orchestrator with uvicorn host and port"
    print(f"\nQuerying for: '{query_2}'")
    results_2 = db.query(query_2, n_results=2)
    
    print(f"Query 2 matches:")
    for r in results_2:
        print(f" - [{r['metadata']['source_file']}] Score: {r['distance']:.4f} | Section: {r['metadata']['heading_path']}")
        
    assert len(results_2) > 0, "Expected query results for Query 2"
    assert results_2[0]["metadata"]["source_file"] == "developer_setup.md", "Query should rank developer setup first"

    # Query 3: search for flat-file database schema (should match sample_setup.pdf)
    query_3 = "flat-file database schema in chroma_db/document_store.json"
    print(f"\nQuerying for: '{query_3}'")
    results_3 = db.query(query_3, n_results=2)
    
    print(f"Query 3 matches:")
    for r in results_3:
        print(f" - [{r['metadata']['source_file']}] Score: {r['distance']:.4f} | Section: {r['metadata']['heading_path']}")
        
    assert len(results_3) > 0, "Expected query results for Query 3"
    assert results_3[0]["metadata"]["source_file"] == "sample_setup.pdf", "Query should rank sample setup PDF first"
    
    print("\n[SUCCESS] RAG Subsystem Test Passed! Chunking, indexing, and retrieval are functioning correctly for both markdown and PDF formats.")
    
    # Clean up test database folder
    try:
        import shutil
        shutil.rmtree(os.environ["CHROMA_DB_DIR"])
        print("Cleaned up test Chroma DB directory.")
    except Exception as e:
        print(f"Warning: could not clean up test db dir: {e}")

if __name__ == "__main__":
    run_rag_test()
