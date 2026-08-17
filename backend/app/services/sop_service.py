"""
SOP Forge — SOP service.
Handles SOP document ingestion, text chunking, embedding generation, 
and vector similarity search for RAG retrieval.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.sop import SOPChunk, SOPDocument

logger = logging.getLogger(__name__)
settings = get_settings()


def chunk_text(content: str, chunk_size: int = 800, overlap: int = 0) -> list[str]:
    """
    Split SOP text into section-aware chunks for embedding.
    
    Strategy:
    1. Split on markdown section headers (## / ###) first
    2. Each section = header + all paragraphs until next header
    3. If a section exceeds chunk_size, split paragraphs within it
       but always prepend the section title so every chunk has context
    4. Never break a paragraph mid-sentence
    """
    import re

    # Split into sections by markdown headers (## or ###)
    # Keep the header with its content
    section_pattern = re.compile(r'^(#{2,3}\s+.+)$', re.MULTILINE)
    
    sections = []
    current_title = ""
    current_body = []
    
    for line in content.split('\n'):
        if section_pattern.match(line.strip()):
            # Save previous section
            if current_body or current_title:
                body_text = '\n'.join(current_body).strip()
                if body_text or current_title:
                    sections.append((current_title, body_text))
            current_title = line.strip()
            current_body = []
        else:
            current_body.append(line)
    
    # Don't forget last section
    if current_body or current_title:
        body_text = '\n'.join(current_body).strip()
        if body_text or current_title:
            sections.append((current_title, body_text))
    
    # If no sections found (no ## headers), treat as flat paragraphs
    if not sections or (len(sections) == 1 and not sections[0][0]):
        return _chunk_flat_paragraphs(content, chunk_size)
    
    # Build chunks from sections
    chunks: list[str] = []
    
    for title, body in sections:
        if not body and not title:
            continue
            
        # Combine title + body
        full_section = f"{title}\n\n{body}" if title and body else (title or body)
        
        if len(full_section) <= chunk_size:
            # Section fits in one chunk
            chunks.append(full_section.strip())
        else:
            # Section too large — split by paragraphs but keep title in each chunk
            paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
            current_chunk = title if title else ""
            
            for para in paragraphs:
                test = f"{current_chunk}\n\n{para}" if current_chunk else para
                
                if len(test) > chunk_size and current_chunk and current_chunk != title:
                    # Finalize current chunk
                    chunks.append(current_chunk.strip())
                    # Start new chunk with section title for context
                    current_chunk = f"{title}\n\n{para}" if title else para
                else:
                    current_chunk = test
            
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
    
    # Filter out empty/tiny chunks
    chunks = [c for c in chunks if len(c.strip()) > 20]
    
    return chunks


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
    """
    Generate embeddings for a list of text chunks.
    
    Uses DeepSeek/OpenAI-compatible embedding API if configured,
    otherwise falls back to deterministic hash-based mock embeddings.
    """
    if settings.is_llm_configured:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.deepseek_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.embedding_model,
                        "input": texts,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.warning(f"Embedding API failed, falling back to mock: {e}")

    # Mock embeddings: deterministic hash-based vectors for development
    embeddings = []
    for text_item in texts:
        hash_bytes = hashlib.sha256(text_item.encode()).digest()
        # Create a deterministic 1536-dim vector from the hash
        embedding = []
        for i in range(settings.embedding_dimensions):
            byte_idx = i % len(hash_bytes)
            embedding.append((hash_bytes[byte_idx] - 128) / 128.0)
        embeddings.append(embedding)

    return embeddings


async def ingest_sop_document(
    db: AsyncSession,
    *,
    title: str,
    category: str,
    content_text: str,
    created_by: uuid.UUID | None = None,
) -> SOPDocument:
    """
    Ingest a new SOP document: store text, chunk it, generate embeddings.
    """
    # Create the document
    doc = SOPDocument(
        id=uuid.uuid4(),
        title=title,
        category=category,
        content_text=content_text,
        version=1,
        is_active=True,
        created_by=created_by,
    )
    db.add(doc)
    await db.flush()

    # Chunk the text
    chunks = chunk_text(content_text)
    logger.info(f"SOP '{title}' split into {len(chunks)} chunks")

    # Generate embeddings
    embeddings = await generate_embeddings(chunks)

    # Store chunks with embeddings
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        sop_chunk = SOPChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_text=chunk,
            chunk_index=idx,
            embedding=embedding,
            extra_metadata={
                "document_title": title,
                "category": category,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            },
        )
        db.add(sop_chunk)

    await db.flush()
    logger.info(f"SOP '{title}' ingested with {len(chunks)} embedded chunks")
    return doc


async def update_sop_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    *,
    title: str | None = None,
    category: str | None = None,
    content_text: str | None = None,
) -> SOPDocument:
    """
    Update an SOP document. If content_text changes, re-chunk and re-embed.
    Per PRD: re-embed on every update.
    """
    result = await db.execute(
        select(SOPDocument).where(SOPDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"SOP document {document_id} not found")

    if title:
        doc.title = title
    if category:
        doc.category = category

    if content_text and content_text != doc.content_text:
        doc.content_text = content_text
        doc.version += 1

        # Delete old chunks
        await db.execute(
            delete(SOPChunk).where(SOPChunk.document_id == document_id)
        )

        # Re-chunk and re-embed
        chunks = chunk_text(content_text)
        embeddings = await generate_embeddings(chunks)

        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            sop_chunk = SOPChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding=embedding,
                extra_metadata={
                    "document_title": doc.title,
                    "category": doc.category or category,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "version": doc.version,
                },
            )
            db.add(sop_chunk)

        logger.info(f"SOP '{doc.title}' re-embedded with {len(chunks)} chunks (v{doc.version})")

    doc.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return doc


def compute_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


async def search_policy(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    category: str | None = None,
) -> list[dict]:
    """
    Search SOP policy chunks via cosine similarity using pgvector or Python fallback.
    Returns ranked policy chunks with document references.
    """
    # Generate query embedding
    query_embeddings = await generate_embeddings([query])
    query_embedding = query_embeddings[0]

    # Try pgvector native cosine similarity query
    try:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        sql = text("""
            SELECT 
                sc.id,
                sc.chunk_text,
                sc.chunk_index,
                sc.metadata,
                sd.id as document_id,
                sd.title as document_title,
                sd.category,
                sc.embedding <=> :query_embedding::vector AS distance
            FROM sop_chunks sc
            JOIN sop_documents sd ON sc.document_id = sd.id
            WHERE sd.is_active = true
        """ + (" AND sd.category = :category" if category else "") + """
            ORDER BY sc.embedding <=> :query_embedding::vector
            LIMIT :top_k
        """)

        params = {"query_embedding": embedding_str, "top_k": top_k}
        if category:
            params["category"] = category

        result = await db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row.id),
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "document_id": str(row.document_id),
                "document_title": row.document_title,
                "category": row.category,
                "similarity_score": 1 - row.distance,
                "ref": f"{row.document_title}: chunk {row.chunk_index}",
            }
            for row in rows
        ]
    except Exception:
        # Fallback to Python-side vector comparison (for SQLite or non-pgvector DBs)
        stmt = (
            select(SOPChunk, SOPDocument)
            .join(SOPDocument, SOPChunk.document_id == SOPDocument.id)
            .where(SOPDocument.is_active == True)
        )
        if category:
            stmt = stmt.where(SOPDocument.category == category)

        result = await db.execute(stmt)
        rows = result.all()

        scored = []
        query_words = set(query.lower().split())
        for chunk, doc in rows:
            emb = chunk.embedding
            base_score = compute_cosine_similarity(query_embedding, emb) if isinstance(emb, list) else 0.5
            
            # Hybrid scoring: boost score if chunk text shares key terms with query
            chunk_words = set(chunk.chunk_text.lower().split())
            if query_words and chunk_words:
                overlap = len(query_words.intersection(chunk_words))
                keyword_boost = (overlap / max(len(query_words), 1)) * 0.5
            else:
                keyword_boost = 0.0
            
            final_score = round(min(base_score + keyword_boost, 1.0), 3)

            scored.append({
                "chunk_id": str(chunk.id),
                "chunk_text": chunk.chunk_text,
                "chunk_index": chunk.chunk_index,
                "document_id": str(doc.id),
                "document_title": doc.title,
                "category": doc.category,
                "similarity_score": final_score,
                "ref": f"{doc.title}: chunk {chunk.chunk_index}",
            })

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_k]


async def get_all_documents(
    db: AsyncSession,
    active_only: bool = True,
) -> list[SOPDocument]:
    """Get all SOP documents, optionally filtered by active status."""
    stmt = select(SOPDocument).order_by(SOPDocument.updated_at.desc())
    if active_only:
        stmt = stmt.where(SOPDocument.is_active == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_document_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> list[SOPChunk]:
    """Get all chunks for a specific document."""
    result = await db.execute(
        select(SOPChunk)
        .where(SOPChunk.document_id == document_id)
        .order_by(SOPChunk.chunk_index)
    )
    return list(result.scalars().all())
