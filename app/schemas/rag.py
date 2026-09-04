from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A retrieved text chunk enriched with source attribution and relevance scoring."""
    chunk_id: str = Field(description="Deterministic chunk identifier")
    material_id: str = Field(description="Parent material ID")
    text: str = Field(description="Text content of the retrieved chunk")
    filename: str = Field(description="Original document filename")
    file_type: str = Field(description="Document format type (pdf, docx, pptx, txt)")
    chunk_index: int = Field(description="0-based index of the chunk in document sequence")
    chapter: Optional[str] = Field(default=None, description="Enclosing chapter title if detected")
    section: Optional[str] = Field(default=None, description="Enclosing section/heading title if detected")
    page_number: Optional[int] = Field(default=None, description="1-based page number for PDF")
    slide_number: Optional[int] = Field(default=None, description="1-based slide number for PPTX")
    similarity_score: Optional[float] = Field(
        default=None,
        description="Normalized relevance/similarity score (0.0 to 1.0, higher is more relevant)"
    )
    distance: Optional[float] = Field(
        default=None,
        description="Raw vector distance metric (lower indicates closer vector proximity)"
    )
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved format-specific metadata"
    )


class GroundedContext(BaseModel):
    """Clean structured context container for downstream LLM prompting and source attribution."""
    query: str = Field(description="User query or retrieval concept")
    chunks: List[RetrievedChunk] = Field(default_factory=list, description="List of relevant retrieved chunks")
    total_chunks: int = Field(description="Number of chunks in this grounded context")
    formatted_context: str = Field(description="Formatted string ready to be injected into an LLM prompt")


class IngestionResult(BaseModel):
    """Summary of a document or chunk ingestion batch."""
    material_id: str = Field(description="Material identifier")
    chunks_ingested: int = Field(description="Number of newly embedded and stored chunks")
    chunks_skipped: int = Field(default=0, description="Number of duplicate chunks skipped")
    total_chunks: int = Field(description="Total chunks processed in this material")
    status: str = Field(default="success", description="Ingestion status summary")


class VectorStoreStats(BaseModel):
    """Health and volume telemetry of the vector store collection."""
    collection_name: str = Field(description="ChromaDB collection name")
    total_vectors: int = Field(description="Total number of stored chunk vectors")
    persist_directory: str = Field(description="Persistence storage path")
    status: str = Field(default="healthy", description="Operational status of the vector store")
