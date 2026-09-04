import math
import shutil
import tempfile
from typing import List
import pytest

from app.core.exceptions import (
    EmptyDocumentError,
    EmptyQueryError,
    InvalidParameterError,
    VectorStoreError,
)
from app.db.vector_store import ChromaVectorStore, serialize_chunk_metadata
from app.schemas.material import DocumentChunk, ExtractedDocument, MaterialMetadata
from app.schemas.rag import GroundedContext, IngestionResult, RetrievedChunk
from app.services.rag_service import RAGService


import hashlib

def deterministic_mock_embedder(texts: List[str]) -> List[List[float]]:
    """Deterministic token-hash embedding function producing normalized 64-dim unit vectors."""
    dim = 64
    results = []
    for text in texts:
        vec = [0.0] * dim
        tokens = text.lower().replace(".", " ").replace(",", " ").split()
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim
            vec[h] += 1.0
        magnitude = math.sqrt(sum(x * x for x in vec))
        if magnitude > 0:
            vec = [x / magnitude for x in vec]
        else:
            vec[0] = 1.0
        results.append(vec)
    return results


import chromadb

@pytest.fixture
def temp_chroma_dir():
    """Create and tear down an isolated temporary directory for ChromaDB."""
    tmp = tempfile.mkdtemp(prefix="ai_brain_test_chroma_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def vector_store_instance():
    """Isolated in-memory ChromaVectorStore instance for fast test execution."""
    client = chromadb.EphemeralClient()
    store = ChromaVectorStore(collection_name="test_chunks", client=client)
    return store


@pytest.fixture
def rag_service_instance(vector_store_instance):
    """Isolated RAGService using deterministic mock embeddings."""
    return RAGService(store=vector_store_instance, embedder=deterministic_mock_embedder)


@pytest.fixture
def sample_document_chunks():
    """Create a diverse set of test document chunks with metadata."""
    return [
        DocumentChunk(
            chunk_id="chk_mat1_0_hash001",
            material_id="mat_photosynthesis",
            filename="biology_chapter1.pdf",
            file_type="pdf",
            chunk_index=0,
            text="Photosynthesis is the process by which green plants convert sunlight, water, and carbon dioxide into glucose and oxygen.",
            chapter="Chapter 1: Plant Physiology",
            section="Section 1.1: Light Reactions",
            page_number=1,
            source_metadata={"topic": "chloroplasts", "grade_level": 10},
        ),
        DocumentChunk(
            chunk_id="chk_mat1_1_hash002",
            material_id="mat_photosynthesis",
            filename="biology_chapter1.pdf",
            file_type="pdf",
            chunk_index=1,
            text="Chlorophyll inside the chloroplast thylakoid membranes absorbs red and blue light while reflecting green light wavelengths.",
            chapter="Chapter 1: Plant Physiology",
            section="Section 1.2: Chlorophyll Pigments",
            page_number=2,
            source_metadata={"pigment": "chlorophyll-a"},
        ),
        DocumentChunk(
            chunk_id="chk_mat2_0_hash003",
            material_id="mat_calculus",
            filename="calculus_derivatives.pptx",
            file_type="pptx",
            chunk_index=0,
            text="The derivative of a function represents the instantaneous rate of change of the function with respect to its variable.",
            chapter="Calculus Basics",
            section="Derivatives Overview",
            slide_number=3,
            source_metadata={"subject": "math"},
        ),
    ]


@pytest.fixture
def sample_extracted_document(sample_document_chunks):
    """Create a complete ExtractedDocument instance."""
    chunks = sample_document_chunks[:2]
    return ExtractedDocument(
        material_id="mat_photosynthesis",
        filename="biology_chapter1.pdf",
        file_type="pdf",
        metadata=MaterialMetadata(
            material_id="mat_photosynthesis",
            filename="biology_chapter1.pdf",
            file_type="pdf",
            total_pages=2,
            total_chunks=2,
        ),
        chunks=chunks,
        raw_text="Photosynthesis is the process by which green plants... Chlorophyll absorbs light...",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_vector_store_initialization(vector_store_instance):
    """1. ChromaDB initializes correctly and collection is created."""
    stats = vector_store_instance.get_stats()
    assert stats.status == "healthy"
    assert stats.collection_name == "test_chunks"
    assert stats.total_vectors == 0
    assert vector_store_instance.collection is not None


def test_persistent_chroma_storage(temp_chroma_dir):
    """Verify persistent local directory Chroma storage writes to disk."""
    store = ChromaVectorStore(persist_directory=temp_chroma_dir, collection_name="persist_chunks")
    stats = store.get_stats()
    assert stats.status == "healthy"
    assert stats.persist_directory == temp_chroma_dir


def test_metadata_serialization(sample_document_chunks):
    """Verify metadata sanitization eliminates None and preserves types."""
    meta = serialize_chunk_metadata(sample_document_chunks[0])
    assert meta["material_id"] == "mat_photosynthesis"
    assert meta["filename"] == "biology_chapter1.pdf"
    assert meta["file_type"] == "pdf"
    assert meta["chunk_index"] == 0
    assert meta["page_number"] == 1
    assert meta["chapter"] == "Chapter 1: Plant Physiology"
    assert meta["section"] == "Section 1.1: Light Reactions"
    assert meta["src_grade_level"] == 10
    # Verify no None values exist in Chroma metadata
    for k, v in meta.items():
        assert v is not None
        assert isinstance(v, (str, int, float, bool))


@pytest.mark.asyncio
async def test_ingest_document_and_vector_id(rag_service_instance, sample_extracted_document):
    """3, 4, 5, 6. Ingestion stores embeddings, uses chunk_id as vector ID, preserves metadata."""
    result = await rag_service_instance.ingest_document(sample_extracted_document)

    assert isinstance(result, IngestionResult)
    assert result.material_id == "mat_photosynthesis"
    assert result.chunks_ingested == 2
    assert result.chunks_skipped == 0
    assert result.total_chunks == 2

    # Check vector store contents
    stats = rag_service_instance.get_stats()
    assert stats.total_vectors == 2

    # Check that chunk_id is used as vector ID
    stored_chunk = rag_service_instance.store.get_chunk_by_id("chk_mat1_0_hash001")
    assert stored_chunk is not None
    assert stored_chunk["chunk_id"] == "chk_mat1_0_hash001"
    assert "Photosynthesis" in stored_chunk["text"]
    assert stored_chunk["metadata"]["page_number"] == 1
    assert stored_chunk["metadata"]["chapter"] == "Chapter 1: Plant Physiology"


@pytest.mark.asyncio
async def test_safe_upsert_idempotency(rag_service_instance, sample_extracted_document):
    """7. Same chunk can be safely upserted without duplication."""
    result1 = await rag_service_instance.ingest_document(sample_extracted_document)
    assert result1.chunks_ingested == 2

    # Ingesting the same document again
    result2 = await rag_service_instance.ingest_document(sample_extracted_document)
    assert result2.chunks_ingested == 2

    # Total vectors in Chroma collection should remain 2 (idempotent upsert)
    stats = rag_service_instance.get_stats()
    assert stats.total_vectors == 2


@pytest.mark.asyncio
async def test_material_deletion(rag_service_instance, sample_document_chunks):
    """8. Material deletion removes all chunks associated with material_id."""
    await rag_service_instance.ingest_chunks(sample_document_chunks)
    assert rag_service_instance.get_stats().total_vectors == 3

    # Delete photosynthesis material
    deleted_count = rag_service_instance.delete_material("mat_photosynthesis")
    assert deleted_count == 2

    # Only calculus material should remain
    assert rag_service_instance.get_stats().total_vectors == 1
    remaining_chunk = rag_service_instance.store.get_chunk_by_id("chk_mat2_0_hash003")
    assert remaining_chunk is not None
    assert remaining_chunk["metadata"]["material_id"] == "mat_calculus"


@pytest.mark.asyncio
async def test_semantic_retrieval(rag_service_instance, sample_document_chunks):
    """9 & 14. Semantic retrieval returns relevant chunks and preserves source metadata."""
    await rag_service_instance.ingest_chunks(sample_document_chunks)

    # Query for photosynthesis
    results = await rag_service_instance.search(query="How does sunlight convert into glucose in plants?", top_k=2)

    assert len(results) > 0
    top_result = results[0]
    assert isinstance(top_result, RetrievedChunk)
    assert top_result.material_id == "mat_photosynthesis"
    assert "Photosynthesis" in top_result.text or "Chlorophyll" in top_result.text
    assert top_result.filename == "biology_chapter1.pdf"
    assert top_result.page_number in [1, 2]
    assert top_result.similarity_score is not None
    assert 0.0 <= top_result.similarity_score <= 1.0


@pytest.mark.asyncio
async def test_top_k_parameter(rag_service_instance, sample_document_chunks):
    """10. top_k restricts the number of returned results."""
    await rag_service_instance.ingest_chunks(sample_document_chunks)

    res_1 = await rag_service_instance.search(query="science plants calculus", top_k=1)
    assert len(res_1) == 1

    res_2 = await rag_service_instance.search(query="science plants calculus", top_k=2)
    assert len(res_2) == 2

    res_all = await rag_service_instance.search(query="science plants calculus", top_k=10)
    assert len(res_all) == 3


@pytest.mark.asyncio
async def test_metadata_filtering(rag_service_instance, sample_document_chunks):
    """11. Metadata filtering restricts search to specific materials or file types."""
    await rag_service_instance.ingest_chunks(sample_document_chunks)

    # Search math only using material_id filter
    math_results = await rag_service_instance.search(
        query="rate of change and sunlight",
        material_id="mat_calculus",
    )
    assert len(math_results) == 1
    assert math_results[0].material_id == "mat_calculus"
    assert math_results[0].slide_number == 3

    # Search biology only using filter_metadata
    bio_results = await rag_service_instance.search(
        query="rate of change and sunlight",
        filter_metadata={"file_type": "pdf"},
    )
    assert all(r.file_type == "pdf" for r in bio_results)


@pytest.mark.asyncio
async def test_empty_query_rejected(rag_service_instance):
    """12. Empty queries are explicitly rejected."""
    with pytest.raises(EmptyQueryError):
        await rag_service_instance.search(query="")

    with pytest.raises(EmptyQueryError):
        await rag_service_instance.search(query="   \n\t  ")


@pytest.mark.asyncio
async def test_empty_chunks_and_documents_rejected(rag_service_instance):
    """13. Empty chunks and documents are explicitly rejected."""
    with pytest.raises(EmptyDocumentError):
        await rag_service_instance.ingest_chunks([])

    with pytest.raises(EmptyDocumentError):
        doc = ExtractedDocument(
            material_id="mat_empty",
            filename="empty.txt",
            file_type="txt",
            metadata=MaterialMetadata(
                material_id="mat_empty",
                filename="empty.txt",
                file_type="txt",
            ),
            chunks=[],
        )
        await rag_service_instance.ingest_document(doc)

    with pytest.raises(EmptyDocumentError):
        empty_chunk = DocumentChunk(
            chunk_id="chk_empty",
            material_id="mat_empty",
            filename="empty.txt",
            file_type="txt",
            chunk_index=0,
            text="   ",
        )
        await rag_service_instance.ingest_chunks([empty_chunk])


@pytest.mark.asyncio
async def test_invalid_top_k_rejected(rag_service_instance):
    """Verify invalid top_k values raise InvalidParameterError."""
    with pytest.raises(InvalidParameterError):
        await rag_service_instance.search(query="test", top_k=0)

    with pytest.raises(InvalidParameterError):
        await rag_service_instance.search(query="test", top_k=-5)


@pytest.mark.asyncio
async def test_build_grounded_context(rag_service_instance, sample_document_chunks):
    """Verify build_grounded_context formats chunks with explicit citations for LLM prompts."""
    await rag_service_instance.ingest_chunks(sample_document_chunks)
    retrieved = await rag_service_instance.search(query="photosynthesis chlorophyll light", top_k=2)

    context = rag_service_instance.build_grounded_context(
        query="Explain light absorption in photosynthesis",
        retrieved_chunks=retrieved,
    )

    assert isinstance(context, GroundedContext)
    assert context.total_chunks == len(retrieved)
    assert "biology_chapter1.pdf" in context.formatted_context
    assert "Page:" in context.formatted_context or "Chapter:" in context.formatted_context
    assert "Source Reference #" in context.formatted_context
