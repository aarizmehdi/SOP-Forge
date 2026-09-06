"""
SOP Forge — SOP service (MongoDB).
Handles SOP document ingestion, text chunking, embedding generation, 
and pure Python vector similarity search for RAG retrieval.
"""

import re
import math
import logging
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.models.sop import SOPChunk, SOPDocument

logger = logging.getLogger(__name__)
settings = get_settings()


def chunk_text(content: str, chunk_size: int = 800, overlap: int = 0) -> list[str]:
    """Split SOP text into section-aware chunks for embedding."""
    import re

    section_pattern = re.compile(r'^(#{2,3}\s+.+)$', re.MULTILINE)
    
    sections = []
    current_title = ""
    current_body = []
    
    for line in content.split('\n'):
        if section_pattern.match(line.strip()):
            if current_body or current_title:
                body_text = '\n'.join(current_body).strip()
                if body_text or current_title:
                    sections.append((current_title, body_text))
            current_title = line.strip()
            current_body = []
        else:
            current_body.append(line)
    
    if current_body or current_title:
        body_text = '\n'.join(current_body).strip()
        if body_text or current_title:
            sections.append((current_title, body_text))
    
    if not sections or (len(sections) == 1 and not sections[0][0]):
        return _chunk_flat_paragraphs(content, chunk_size)
    
    chunks: list[str] = []
    for title, body in sections:
        if not body and not title:
            continue
        full_section = f"{title}\n\n{body}" if title and body else (title or body)
        if len(full_section) <= chunk_size:
            chunks.append(full_section.strip())
        else:
            paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
            current_chunk = title if title else ""
            for para in paragraphs:
                test = f"{current_chunk}\n\n{para}" if current_chunk else para
                if len(test) > chunk_size and current_chunk and current_chunk != title:
                    chunks.append(current_chunk.strip())
                    current_chunk = f"{title}\n\n{para}" if title else para
                else:
                    current_chunk = test
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
    
    return [c for c in chunks if len(c.strip()) > 20]


def _chunk_flat_paragraphs(content: str, chunk_size: int = 800) -> list[str]:
    """Fallback: split by paragraphs when no markdown headers exist."""
    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return [c for c in chunks if len(c.strip()) > 20]


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of text chunks using OpenAI; empty vectors explicitly signal degraded retrieval."""
    if settings.openai_api_key:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.embedding_model,
                        "input": texts,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                vectors = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
                if len(vectors) != len(texts) or any(not vector or not all(math.isfinite(v) for v in vector) for vector in vectors):
                    raise ValueError("Invalid embedding response")
                return vectors
        except Exception as e:
            logger.warning("Embedding provider unavailable; retrieval_mode=degraded_keyword")

    logger.warning("Real embeddings unavailable; retrieval_mode=degraded_keyword. No semantic fallback.")
    return [[] for _ in texts]


async def ingest_sop_document(
    db: AsyncIOMotorDatabase,
    *,
    title: str,
    category: str,
    content_text: str,
    created_by: str | None = None,
) -> SOPDocument:
    """Ingest a new SOP document: store text, chunk it, generate embeddings."""
    doc = SOPDocument(
        id=str(uuid.uuid4()),
        title=title,
        category=category,
        content_text=content_text,
        version=1,
        is_active=True,
        created_by=created_by,
    )
    await db.sop_documents.insert_one(doc.model_dump(mode="json"))

    chunks = chunk_text(content_text)
    logger.info(f"SOP '{title}' split into {len(chunks)} chunks")

    embeddings = await generate_embeddings(chunks)

    chunk_docs = []
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        sop_chunk = SOPChunk(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            chunk_text=chunk,
            chunk_index=idx,
            embedding=embedding,
            metadata={
                "document_title": title,
                "category": category,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "embedding_provider": "openai" if embedding else "none",
                "embedding_model": settings.embedding_model if embedding else None,
            },
        )
        chunk_docs.append(sop_chunk.model_dump(mode="json"))

    if chunk_docs:
        await db.sop_chunks.insert_many(chunk_docs)

    logger.info(f"SOP '{title}' ingested with {len(chunks)} embedded chunks")
    return doc


async def update_sop_document(
    db: AsyncIOMotorDatabase,
    document_id: str,
    *,
    title: str | None = None,
    category: str | None = None,
    content_text: str | None = None,
) -> SOPDocument:
    """Update an SOP document."""
    doc_dict = await db.sop_documents.find_one({"id": document_id})
    if not doc_dict:
        raise ValueError(f"SOP document {document_id} not found")
    
    doc = SOPDocument(**doc_dict)

    if title:
        doc.title = title
    if category:
        doc.category = category

    if content_text and content_text != doc.content_text:
        doc.content_text = content_text
        doc.version += 1

        # Delete old chunks
        await db.sop_chunks.delete_many({"document_id": document_id})

        chunks = chunk_text(content_text)
        embeddings = await generate_embeddings(chunks)

        chunk_docs = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            sop_chunk = SOPChunk(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding=embedding,
                metadata={
                    "document_title": doc.title,
                    "category": doc.category,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                "embedding_provider": "openai" if embedding else "none",
                "embedding_model": settings.embedding_model if embedding else None,
                    "version": doc.version,
                },
            )
            chunk_docs.append(sop_chunk.model_dump(mode="json"))

        if chunk_docs:
            await db.sop_chunks.insert_many(chunk_docs)

    doc.updated_at = datetime.now(timezone.utc)
    await db.sop_documents.update_one({"id": document_id}, {"$set": doc.model_dump(mode="json")})
    return doc


def compute_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


async def search_policy(
    db: AsyncIOMotorDatabase,
    query: str,
    top_k: int = 5,
    category: str | None = None,
    min_threshold: float = 0.35,
) -> list[dict]:
    """
    Search SOP policy chunks using pure Python vector similarity math with minimum relevance threshold.
    """
    query_embeddings = await generate_embeddings([query])
    query_embedding = query_embeddings[0]

    # Fetch all chunks of active documents
    doc_query = {"is_active": True}
    if category:
        doc_query["category"] = category
        
    active_docs = await db.sop_documents.find(doc_query).to_list(length=1000)
    active_doc_ids = [doc["id"] for doc in active_docs]
    
    if not active_doc_ids:
        return []
        
    chunks = await db.sop_chunks.find({"document_id": {"$in": active_doc_ids}}).to_list(length=10000)

    scored = []
    stop = {"the", "and", "for", "what", "does", "with", "this", "that", "policy", "policies", "request", "need", "can", "how", "are", "our", "company", "about", "have", "take"}
    def words(text):
        return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2 and word not in stop}
    query_words = words(query)
    
    for chunk in chunks:
        emb = chunk.get("embedding", [])
        metadata = chunk.get("metadata", {})
        semantic = bool(query_embedding and isinstance(emb, list) and len(emb) == len(query_embedding)
                        and metadata.get("embedding_provider") == "openai"
                        and metadata.get("embedding_model") == settings.embedding_model)
        base_score = compute_cosine_similarity(query_embedding, emb) if semantic else 0.0
        
        chunk_text_str = chunk.get("chunk_text", "")
        chunk_words = words(chunk_text_str)
        
        if query_words and chunk_words:
            overlap = len(query_words.intersection(chunk_words))
            keyword_boost = overlap / max(len(query_words), 1)
        else:
            keyword_boost = 0.0
        
        final_score = round(max(base_score, keyword_boost), 3)

        doc_title = chunk.get("metadata", {}).get("document_title", "Unknown")
        doc_category = chunk.get("metadata", {}).get("category", "")
        chunk_idx = chunk.get("chunk_index", 0)

        scored.append({
            "chunk_id": chunk["id"],
            "chunk_text": chunk_text_str,
            "chunk_index": chunk_idx,
            "document_id": chunk["document_id"],
            "document_title": doc_title,
            "category": doc_category,
            "similarity_score": final_score,
            "retrieval_mode": "semantic" if semantic else "degraded_keyword",
            "ref": f"{doc_title}: chunk {chunk_idx}",
        })

    if any(item["retrieval_mode"] == "degraded_keyword" for item in scored):
        logger.warning("retrieval_mode=degraded_keyword; untrusted legacy vectors excluded")
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    # P0-5: Filter out meaningless chunks below minimum relevance threshold
    relevant = [s for s in scored if s["similarity_score"] >= min_threshold]
    return relevant[:top_k]


async def get_all_documents(
    db: AsyncIOMotorDatabase,
    active_only: bool = True,
) -> list[SOPDocument]:
    """Get all SOP documents."""
    query = {"is_active": True} if active_only else {}
    docs = await db.sop_documents.find(query).sort("updated_at", -1).to_list(length=1000)
    return [SOPDocument(**doc) for doc in docs]


async def get_document_chunks(
    db: AsyncIOMotorDatabase,
    document_id: str,
) -> list[SOPChunk]:
    """Get all chunks for a specific document."""
    chunks = await db.sop_chunks.find({"document_id": document_id}).sort("chunk_index", 1).to_list(length=1000)
    return [SOPChunk(**chunk) for chunk in chunks]
