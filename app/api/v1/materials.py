import os
import shutil
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.exceptions import UnsupportedFileTypeError
from app.schemas.api import MaterialProcessingResponse
from app.services.material_processor import process_document
from app.services.rag_service import rag_service

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post(
    "/process",
    response_model=MaterialProcessingResponse,
    status_code=status.HTTP_200_OK,
    summary="Process learning document and optionally ingest into ChromaDB vector store",
)
async def process_material(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=1000),
    chunk_overlap: int = Form(default=200),
    auto_ingest: bool = Form(default=True),
) -> MaterialProcessingResponse:
    """Upload and process a document (PDF, DOCX, PPTX, TXT) and return extracted chunks with ingestion result."""
    filename = file.filename or "uploaded_document"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".pdf", ".docx", ".pptx", ".txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: PDF, DOCX, PPTX, TXT.",
        )

    # Save to a temporary file for extraction
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        extracted_doc = process_document(
            file_path=tmp_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        # Preserve original uploaded filename
        extracted_doc.filename = filename
        extracted_doc.metadata.filename = filename
        for chunk in extracted_doc.chunks:
            chunk.filename = filename

        ingestion_res = None
        if auto_ingest and extracted_doc.chunks:
            ingestion_res = await rag_service.ingest_document(extracted_doc)

        return MaterialProcessingResponse(
            extracted_document=extracted_doc,
            ingestion_result=ingestion_res,
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
