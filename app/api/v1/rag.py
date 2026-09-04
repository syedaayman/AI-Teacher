from fastapi import APIRouter, status

from app.schemas.api import RAGContextRequest, RAGSearchRequest, RAGSearchResponse
from app.schemas.rag import GroundedContext, VectorStoreStats
from app.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/search",
    response_model=RAGSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic retrieval of relevant document chunks",
)
async def search_chunks(req: RAGSearchRequest) -> RAGSearchResponse:
    """Perform cosine distance similarity search across indexed document chunks."""
    results = await rag_service.search(
        query=req.query,
        top_k=req.top_k,
        material_id=req.material_id,
    )
    return RAGSearchResponse(query=req.query, results=results)


@router.post(
    "/context",
    response_model=GroundedContext,
    status_code=status.HTTP_200_OK,
    summary="Construct grounded context for prompt injection",
)
async def build_context(req: RAGContextRequest) -> GroundedContext:
    """Retrieve top chunks and construct grounded context string with citations."""
    results = await rag_service.search(
        query=req.query,
        top_k=req.top_k,
        material_id=req.material_id,
    )
    return rag_service.build_grounded_context(
        query=req.query,
        retrieved_chunks=results,
    )


@router.get(
    "/stats",
    response_model=VectorStoreStats,
    status_code=status.HTTP_200_OK,
    summary="Get vector store index statistics",
)
def get_stats() -> VectorStoreStats:
    """Return total vector count and active collection name."""
    return rag_service.get_stats()
