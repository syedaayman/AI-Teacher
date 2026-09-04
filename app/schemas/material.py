from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MaterialMetadata(BaseModel):
    """Metadata describing a processed document material."""
    material_id: str = Field(description="Unique deterministic or assigned identifier for the material")
    filename: str = Field(description="Original filename of the document")
    file_type: str = Field(description="File format extension or MIME type (e.g., pdf, docx, pptx, txt)")
    file_size_bytes: Optional[int] = Field(default=None, description="Size of the raw document file in bytes")
    total_pages: Optional[int] = Field(default=None, description="Total pages if applicable (e.g. PDF)")
    total_slides: Optional[int] = Field(default=None, description="Total slides if applicable (e.g. PPTX)")
    total_sections: Optional[int] = Field(default=None, description="Total detected sections or headings")
    total_chunks: Optional[int] = Field(default=None, description="Total number of chunks produced")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of extraction"
    )
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional format-specific metadata"
    )


class DocumentChunk(BaseModel):
    """A single deterministic text chunk with preserved structural and positional metadata."""
    chunk_id: str = Field(description="Deterministic hash-based unique chunk identifier")
    material_id: str = Field(description="ID of the parent material")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="Document format type")
    chunk_index: int = Field(description="0-based sequential ordering index within the material")
    text: str = Field(description="Cleaned text content of the chunk")
    chapter: Optional[str] = Field(default=None, description="Enclosing chapter title if detected")
    section: Optional[str] = Field(default=None, description="Enclosing section/heading title if detected")
    page_number: Optional[int] = Field(default=None, description="1-based page number for PDF")
    slide_number: Optional[int] = Field(default=None, description="1-based slide number for PPTX")
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Format-specific source metadata (e.g., heading level, bounding info)"
    )


class ExtractedDocument(BaseModel):
    """Top-level structured representation of an extracted and chunked document."""
    material_id: str = Field(description="Unique identifier for the material")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="Document type")
    metadata: MaterialMetadata = Field(description="Summary metadata for the material")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="Ordered list of text chunks")
    raw_text: Optional[str] = Field(default=None, description="Full cleaned document text")
