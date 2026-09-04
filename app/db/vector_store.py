import os
from typing import Any, Dict, List, Optional, Union
import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.schemas.material import DocumentChunk
from app.schemas.rag import VectorStoreStats


DEFAULT_COLLECTION_NAME = "document_chunks"


def serialize_chunk_metadata(chunk: DocumentChunk) -> Dict[str, Union[str, int, float, bool]]:
    """Sanitize and flatten DocumentChunk metadata for ChromaDB storage.
    
    ChromaDB metadata values must be str, int, float, or bool (no None, no nested dicts/lists).
    """
    meta: Dict[str, Union[str, int, float, bool]] = {
        "material_id": str(chunk.material_id),
        "filename": str(chunk.filename),
        "file_type": str(chunk.file_type),
        "chunk_index": int(chunk.chunk_index),
    }

    if chunk.chapter is not None and chunk.chapter.strip():
        meta["chapter"] = str(chunk.chapter)
    if chunk.section is not None and chunk.section.strip():
        meta["section"] = str(chunk.section)
    if chunk.page_number is not None:
        meta["page_number"] = int(chunk.page_number)
    if chunk.slide_number is not None:
        meta["slide_number"] = int(chunk.slide_number)

    # Flatten primitive fields from source_metadata if present
    if chunk.source_metadata:
        for k, v in chunk.source_metadata.items():
            if isinstance(v, (str, int, float, bool)) and k not in meta:
                meta[f"src_{k}"] = v

    return meta


class ChromaVectorStore:
    """Manages persistent ChromaDB vector storage and querying for document chunks."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        client: Optional[ClientAPI] = None,
    ):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self.collection_name = collection_name
        self._client: Optional[ClientAPI] = client
        self._collection = None

    @property
    def client(self) -> ClientAPI:
        """Lazy-initialize or return the active ChromaDB client."""
        if self._client is None:
            try:
                os.makedirs(self.persist_directory, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            except Exception as e:
                raise VectorStoreError(f"Failed to initialize ChromaDB at '{self.persist_directory}': {str(e)}") from e
        return self._client

    @property
    def collection(self):
        """Get or create the dedicated document chunks collection."""
        if self._collection is None:
            try:
                self._collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                raise VectorStoreError(
                    f"Failed to obtain ChromaDB collection '{self.collection_name}': {str(e)}"
                ) from e
        return self._collection

    def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> int:
        """Upsert a batch of document chunks and their embeddings into ChromaDB.
        
        Uses deterministic chunk_id as ChromaDB document ID for idempotency.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                f"Mismatch between chunks count ({len(chunks)}) and embeddings count ({len(embeddings)})."
            )

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Union[str, int, float, bool]]] = []
        valid_embeddings: List[List[float]] = []

        for chunk, emb in zip(chunks, embeddings):
            if not chunk.text or not chunk.text.strip():
                continue
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            metadatas.append(serialize_chunk_metadata(chunk))
            valid_embeddings.append(emb)

        if not ids:
            return 0

        try:
            self.collection.upsert(
                ids=ids,
                embeddings=valid_embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            return len(ids)
        except Exception as e:
            raise VectorStoreError(f"Failed to upsert chunks into ChromaDB: {str(e)}") from e

    def query_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query nearest vector neighbors matching optional metadata filters."""
        if not query_embedding:
            raise VectorStoreError("Query embedding cannot be empty.")
        if top_k <= 0:
            raise VectorStoreError(f"top_k must be a positive integer, received {top_k}.")

        total_count = self.collection.count()
        if total_count == 0:
            return []

        n_results = min(top_k, total_count)

        try:
            kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            raw_results = self.collection.query(**kwargs)

            # Chroma returns lists of lists for each query embedding
            ids = raw_results.get("ids", [[]])[0]
            docs = raw_results.get("documents", [[]])[0]
            metas = raw_results.get("metadatas", [[]])[0]
            dists = raw_results.get("distances", [[]])[0]

            results = []
            for idx, chunk_id in enumerate(ids):
                results.append({
                    "chunk_id": chunk_id,
                    "text": docs[idx] if idx < len(docs) else "",
                    "metadata": metas[idx] if idx < len(metas) else {},
                    "distance": dists[idx] if idx < len(dists) else 0.0,
                })

            return results
        except Exception as e:
            raise VectorStoreError(f"ChromaDB similarity query failed: {str(e)}") from e

    def delete_material(self, material_id: str) -> int:
        """Delete all vectors and metadata associated with a material_id."""
        if not material_id or not material_id.strip():
            raise VectorStoreError("material_id cannot be empty.")

        try:
            # Query existing records to count deleted chunks
            existing = self.collection.get(
                where={"material_id": material_id},
                include=["metadatas"],
            )
            count = len(existing.get("ids", []))
            if count > 0:
                self.collection.delete(where={"material_id": material_id})
            return count
        except Exception as e:
            raise VectorStoreError(f"Failed to delete material '{material_id}' from ChromaDB: {str(e)}") from e

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific stored chunk by chunk_id."""
        try:
            res = self.collection.get(ids=[chunk_id], include=["documents", "metadatas"])
            ids = res.get("ids", [])
            if not ids:
                return None
            return {
                "chunk_id": ids[0],
                "text": res.get("documents", [""])[0],
                "metadata": res.get("metadatas", [{}])[0],
            }
        except Exception as e:
            raise VectorStoreError(f"Failed to retrieve chunk '{chunk_id}': {str(e)}") from e

    def get_stats(self) -> VectorStoreStats:
        """Return collection vector count and operational health."""
        try:
            count = self.collection.count()
            return VectorStoreStats(
                collection_name=self.collection_name,
                total_vectors=count,
                persist_directory=str(self.persist_directory),
                status="healthy",
            )
        except Exception as e:
            raise VectorStoreError(f"Failed to get vector store statistics: {str(e)}") from e

    def reset_collection(self) -> None:
        """Delete and recreate the collection."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = None


# Global singleton instance
vector_store = ChromaVectorStore()
