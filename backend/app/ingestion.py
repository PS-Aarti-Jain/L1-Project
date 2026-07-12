import os
import hashlib
from pathlib import Path
import logging
from app.config import settings
from app.database import get_vector_store

logger = logging.getLogger("devassist-ingestion")

def calculate_file_hash(filepath: Path) -> str:
    """Calculates the SHA-256 hash of a file's content in binary mode."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def chunk_markdown(content: str, max_chunk_chars: int = 1800, overlap_chars: int = 250) -> list[dict]:
    """
    Recursively chunks a markdown file by headers, and then by paragraphs if needed.
    
    Returns:
        List of dicts: {"text": str, "heading_path": str}
    """
    lines = content.splitlines()
    sections = []
    
    current_headers = {1: "", 2: "", 3: "", 4: "", 5: "", 6: ""}
    current_section_text = []
    current_section_header_path = "Root"
    
    for line in lines:
        stripped = line.strip()
        # Detect markdown headers
        if stripped.startswith("#"):
            # Count the number of hashes to determine level
            level = 0
            for char in stripped:
                if char == "#":
                    level += 1
                else:
                    break
            
            # If it's a valid header (e.g., followed by space)
            if level > 0 and len(stripped) > level and stripped[level] == " ":
                header_text = stripped[level:].strip()
                
                # Save previous section if it has content
                if current_section_text:
                    sections.append({
                        "text": "\n".join(current_section_text).strip(),
                        "heading_path": current_section_header_path
                    })
                    current_section_text = []
                
                # Update header state: clear sub-headers
                current_headers[level] = header_text
                for l in range(level + 1, 7):
                    current_headers[l] = ""
                
                # Construct heading path: e.g. "Security Guidelines > API Key Security"
                active_headers = [current_headers[l] for l in range(1, 7) if current_headers[l]]
                current_section_header_path = " > ".join(active_headers) if active_headers else "Root"
                
                # Keep the header line as part of the section text for context
                current_section_text.append(line)
                continue
        
        current_section_text.append(line)
        
    # Append the last section
    if current_section_text:
        sections.append({
            "text": "\n".join(current_section_text).strip(),
            "heading_path": current_section_header_path
        })
        
    # Now, process sections. If a section is too large, split it by paragraph.
    final_chunks = []
    for sec in sections:
        text = sec["text"]
        heading_path = sec["heading_path"]
        
        if len(text) <= max_chunk_chars:
            if text:
                final_chunks.append({"text": text, "heading_path": heading_path})
        else:
            # Split section by paragraphs
            paragraphs = text.split("\n\n")
            current_chunk = []
            current_len = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If a single paragraph is extremely large, split by sentences or characters
                if len(para) > max_chunk_chars:
                    # Flush current chunk
                    if current_chunk:
                        final_chunks.append({
                            "text": "\n\n".join(current_chunk),
                            "heading_path": heading_path
                        })
                        current_chunk = []
                        current_len = 0
                    
                    # Split giant paragraph by characters with overlap
                    start = 0
                    while start < len(para):
                        end = start + max_chunk_chars
                        chunk_text = para[start:end]
                        final_chunks.append({
                            "text": chunk_text,
                            "heading_path": heading_path
                        })
                        start += max_chunk_chars - overlap_chars
                    continue
                
                # Normal paragraph sizing
                if current_len + len(para) + 2 > max_chunk_chars:
                    # Flush current chunk
                    final_chunks.append({
                        "text": "\n\n".join(current_chunk),
                        "heading_path": heading_path
                    })
                    
                    # Compute overlap: take the last paragraph if it fits within overlap limit
                    if len(current_chunk[-1]) <= overlap_chars:
                        current_chunk = [current_chunk[-1], para]
                        current_len = len(current_chunk[0]) + len(para) + 2
                    else:
                        # Otherwise start fresh
                        current_chunk = [para]
                        current_len = len(para)
                else:
                    current_chunk.append(para)
                    current_len += len(para) + 2
                    
            if current_chunk:
                final_chunks.append({
                    "text": "\n\n".join(current_chunk),
                    "heading_path": heading_path
                })
                
    return final_chunks

def parse_pdf(file_path: Path) -> str:
    """Extracts text page-by-page from a PDF file using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    text_parts = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text_parts.append(f"--- PAGE {i+1} ---\n{page_text}")
    return "\n\n".join(text_parts)

def chunk_pdf(content: str, max_chunk_chars: int = 1800, overlap_chars: int = 250) -> list[dict]:
    """
    Chunks extracted PDF text by page markings and paragraphs.
    Returns:
        List of dicts: {"text": str, "heading_path": str}
    """
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0
    current_page = "Page 1"
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # Update current page tracking if we hit a page separator
        if para.startswith("--- PAGE "):
            current_page = para.replace("---", "").strip()
            
        # If a paragraph is extremely large, split by characters with overlap
        if len(para) > max_chunk_chars:
            if current_chunk:
                chunks.append({
                    "text": "\n\n".join(current_chunk),
                    "heading_path": current_page
                })
                current_chunk = []
                current_len = 0
                
            start = 0
            while start < len(para):
                end = start + max_chunk_chars
                chunks.append({
                    "text": para[start:end],
                    "heading_path": current_page
                })
                start += max_chunk_chars - overlap_chars
            continue
            
        # Normal paragraph packing
        if current_len + len(para) + 2 > max_chunk_chars:
            chunks.append({
                "text": "\n\n".join(current_chunk),
                "heading_path": current_page
            })
            
            # Compute overlap
            if current_chunk and len(current_chunk[-1]) <= overlap_chars:
                current_chunk = [current_chunk[-1], para]
                current_len = len(current_chunk[0]) + len(para) + 2
            else:
                current_chunk = [para]
                current_len = len(para)
        else:
            current_chunk.append(para)
            current_len += len(para) + 2
            
    if current_chunk:
        chunks.append({
            "text": "\n\n".join(current_chunk),
            "heading_path": current_page
        })
        
    return chunks

def ingest_directory(docs_dir: str = None) -> dict:
    """
    Scans the docs directory, reads markdown files, computes hashes, 
    deletes obsolete vectors, and indexes new/modified files.
    """
    target_dir = Path(docs_dir or settings.DOCS_DIR)
    if not target_dir.exists():
        logger.error(f"Docs directory '{target_dir}' does not exist.")
        return {"status": "error", "message": f"Docs directory '{target_dir}' does not exist.", "files_processed": 0}
        
    logger.info(f"Starting ingestion from directory '{target_dir}'")
    db = get_vector_store()
    
    # 1. Walk directory and find all markdown and PDF files
    md_files = list(target_dir.glob("**/*.md"))
    pdf_files = list(target_dir.glob("**/*.pdf"))
    all_files = md_files + pdf_files
    logger.info(f"Found {len(md_files)} markdown files and {len(pdf_files)} PDF files to check.")
    
    files_indexed = 0
    files_skipped = 0
    total_chunks_added = 0
    
    # Keep track of active source files to identify deletions
    active_source_files = set()
    
    for filepath in all_files:
        # Calculate relative path as source identifier
        rel_path = str(filepath.relative_to(target_dir)).replace("\\", "/")
        active_source_files.add(rel_path)
        
        file_hash = calculate_file_hash(filepath)
        
        # 2. Check if file is already indexed with the same hash
        # Query ChromaDB for this file's chunks to see if hash matches
        existing = db.collection.get(
            where={"source_file": rel_path},
            limit=1
        )
        
        if existing and existing.get("metadatas") and len(existing["metadatas"]) > 0:
            existing_hash = existing["metadatas"][0].get("content_hash")
            if existing_hash == file_hash:
                logger.info(f"File '{rel_path}' is unchanged. Skipping.")
                files_skipped += 1
                continue
                
        # 3. File is new or changed. Delete old chunks first.
        logger.info(f"File '{rel_path}' is new or modified. Re-indexing.")
        db.delete_by_metadata("source_file", rel_path)
        
        # Read and chunk depending on extension
        ext = filepath.suffix.lower()
        if ext == ".md":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            chunks = chunk_markdown(content)
        elif ext == ".pdf":
            try:
                content = parse_pdf(filepath)
                chunks = chunk_pdf(content)
            except Exception as pdf_err:
                logger.error(f"Failed to parse PDF '{rel_path}': {str(pdf_err)}")
                continue
        else:
            continue
        
        ids = []
        documents = []
        metadatas = []
        
        for idx, chunk in enumerate(chunks):
            chunk_text = chunk["text"]
            heading_path = chunk["heading_path"]
            
            chunk_id = f"{rel_path}#chunk-{idx}"
            ids.append(chunk_id)
            documents.append(chunk_text)
            metadatas.append({
                "source_file": rel_path,
                "heading_path": heading_path,
                "content_hash": file_hash,
                "chunk_id": chunk_id
            })
            
        if ids:
            db.add_chunks(ids, documents, metadatas)
            files_indexed += 1
            total_chunks_added += len(ids)
            
    # 4. Handle Deleted Files: purge vectors for files that no longer exist in the directory
    # We query ChromaDB to get all unique source files currently indexed
    all_indexed_docs = db.collection.get(include=["metadatas"])
    indexed_sources = set()
    if all_indexed_docs and all_indexed_docs.get("metadatas"):
        for meta in all_indexed_docs["metadatas"]:
            if meta and meta.get("source_file"):
                indexed_sources.add(meta.get("source_file"))
                
    deleted_files_count = 0
    for idx_source in indexed_sources:
        if idx_source not in active_source_files:
            logger.info(f"Indexed file '{idx_source}' no longer exists in directory. Purging from index.")
            db.delete_by_metadata("source_file", idx_source)
            deleted_files_count += 1

    stats = db.get_stats()
    
    return {
        "status": "success",
        "files_indexed": files_indexed,
        "files_skipped": files_skipped,
        "files_deleted_from_db": deleted_files_count,
        "chunks_added_this_run": total_chunks_added,
        "total_chunks_in_db": stats["total_chunks"]
    }
