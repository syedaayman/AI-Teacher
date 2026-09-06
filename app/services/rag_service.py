import math
from typing import Any, Callable, Dict, List, Optional
from app.core.exceptions import (
    EmptyDocumentError,
    EmptyQueryError,
    InvalidParameterError,
    RAGError,
)
from app.core.gemini import gemini_client, GeminiClient
from app.db.vector_store import vector_store, ChromaVectorStore
from app.schemas.material import DocumentChunk, ExtractedDocument
from app.schemas.rag import GroundedContext, IngestionResult, RetrievedChunk, VectorStoreStats


class RAGService:
    """Service orchestrating document embedding, vector storage, and semantic knowledge retrieval."""

    def __init__(
        self,
        store: Optional[ChromaVectorStore] = None,
        client: Optional[GeminiClient] = None,
        embedder: Optional[Callable[[List[str]], Any]] = None,
    ):
        self.store = store or vector_store
        self.client = client or gemini_client
        self._embedder = embedder

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using custom embedder or Gemini client."""
        if not texts:
            return []
        if self._embedder is not None:
            res = self._embedder(texts)
            if hasattr(res, "__await__"):
                return await res
            return res
        return await self.client.embed_batch(texts)

    async def _generate_single_embedding(self, text: str) -> List[float]:
        """Generate a single embedding vector."""
        if self._embedder is not None:
            results = await self._generate_embeddings([text])
            if not results:
                raise RAGError("Embedder returned no embedding.")
            return results[0]
        return await self.client.embed_text(text)

    async def ingest_document(
        self,
        document: ExtractedDocument,
        batch_size: int = 64,
    ) -> IngestionResult:
        """Ingest all chunks of an ExtractedDocument into the vector store with embeddings."""
        if not document or not document.chunks:
            raise EmptyDocumentError(
                f"Cannot ingest document '{getattr(document, 'filename', 'unknown')}': No chunks found."
            )

        return await self.ingest_chunks(
            chunks=document.chunks,
            material_id=document.material_id,
            batch_size=batch_size,
        )

    async def ingest_chunks(
        self,
        chunks: List[DocumentChunk],
        material_id: Optional[str] = None,
        batch_size: int = 64,
    ) -> IngestionResult:
        """Ingest a list of DocumentChunks into ChromaDB."""
        if not chunks:
            raise EmptyDocumentError("Cannot ingest an empty list of document chunks.")

        valid_chunks = [c for c in chunks if c.text and c.text.strip()]
        if not valid_chunks:
            raise EmptyDocumentError("All document chunks contain empty text.")

        target_material_id = material_id or valid_chunks[0].material_id
        total_ingested = 0

        # Process in batches
        for i in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            embeddings = await self._generate_embeddings(texts)

            if len(embeddings) != len(batch):
                raise RAGError(
                    f"Embedding generation mismatch: expected {len(batch)} vectors, got {len(embeddings)}."
                )

            upserted_count = self.store.upsert_chunks(batch, embeddings)
            total_ingested += upserted_count

        return IngestionResult(
            material_id=target_material_id,
            chunks_ingested=total_ingested,
            chunks_skipped=len(chunks) - total_ingested,
            total_chunks=len(chunks),
            status="success",
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        material_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """Semantically retrieve relevant document chunks matching a query."""
        if not query or not query.strip():
            raise EmptyQueryError("Search query cannot be empty or whitespace only.")
        if top_k <= 0:
            raise InvalidParameterError(f"top_k must be greater than 0, received {top_k}.")

        # Formulate Chroma where filter
        where: Optional[Dict[str, Any]] = None
        filters: Dict[str, Any] = {}
        if filter_metadata:
            filters.update(filter_metadata)
        if material_id:
            filters["material_id"] = material_id

        if len(filters) == 1:
            where = filters
        elif len(filters) > 1:
            where = {"$and": [{k: v} for k, v in filters.items()]}

        query_embedding = await self._generate_single_embedding(query.strip())
        raw_results = self.store.query_similar(query_embedding=query_embedding, top_k=top_k, where=where)

        retrieved_chunks: List[RetrievedChunk] = []
        for r in raw_results:
            meta = r.get("metadata", {})
            distance = float(r.get("distance", 0.0))

            # Normalize distance into a 0.0 - 1.0 similarity score (cosine distance is in [0, 2])
            similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))

            # Reconstruct source metadata dict from flattened prefix src_
            source_meta = {
                k[4:]: v for k, v in meta.items() if k.startswith("src_")
            }

            retrieved_chunks.append(
                RetrievedChunk(
                    chunk_id=r.get("chunk_id", ""),
                    material_id=str(meta.get("material_id", "")),
                    text=r.get("text", ""),
                    filename=str(meta.get("filename", "")),
                    file_type=str(meta.get("file_type", "")),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    chapter=str(meta["chapter"]) if "chapter" in meta else None,
                    section=str(meta["section"]) if "section" in meta else None,
                    page_number=int(meta["page_number"]) if "page_number" in meta else None,
                    slide_number=int(meta["slide_number"]) if "slide_number" in meta else None,
                    similarity_score=round(similarity, 4),
                    distance=round(distance, 4),
                    source_metadata=source_meta,
                )
            )

        return retrieved_chunks

    async def query_knowledge(
        self,
        query: str,
        material_id: Optional[str] = None,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Query knowledge base for relevant chunks (alias for search with material_id first)."""
        return await self.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata,
            material_id=material_id,
        )

    def build_grounded_context(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk],
    ) -> GroundedContext:
        """Format retrieved chunks into a structured grounded context object for downstream LLM prompts."""
        if not retrieved_chunks:
            return GroundedContext(
                query=query,
                chunks=[],
                total_chunks=0,
                formatted_context="No relevant source material found.",
            )

        context_blocks: List[str] = []
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            source_info_parts = [f"File: {chunk.filename}"]
            if chunk.chapter:
                source_info_parts.append(f"Chapter: {chunk.chapter}")
            if chunk.section:
                source_info_parts.append(f"Section: {chunk.section}")
            if chunk.page_number is not None:
                source_info_parts.append(f"Page: {chunk.page_number}")
            if chunk.slide_number is not None:
                source_info_parts.append(f"Slide: {chunk.slide_number}")
            if chunk.similarity_score is not None:
                source_info_parts.append(f"Relevance: {chunk.similarity_score:.2f}")

            source_header = f"--- [Source Reference #{idx} | {', '.join(source_info_parts)}] ---"
            context_blocks.append(f"{source_header}\n{chunk.text.strip()}")

        formatted_context = "\n\n".join(context_blocks)

        return GroundedContext(
            query=query,
            chunks=retrieved_chunks,
            total_chunks=len(retrieved_chunks),
            formatted_context=formatted_context,
        )

    def delete_material(self, material_id: str) -> int:
        """Remove material vectors from storage."""
        return self.store.delete_material(material_id)

    def get_stats(self) -> VectorStoreStats:
        """Get vector store operational telemetry."""
        return self.store.get_stats()


# Global singleton instance
rag_service = RAGService()
