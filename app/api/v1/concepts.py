from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.api import ConceptExtractionRequest, ConceptGraphRequest, ConceptGraphResponse
from app.schemas.lesson import Concept
from app.services.concept_service import concept_service

router = APIRouter(prefix="/concepts", tags=["Concepts"])


@router.post(
    "/extract",
    response_model=List[Concept],
    status_code=status.HTTP_200_OK,
    summary="Extract concepts from topic or document material",
)
async def extract_concepts(req: ConceptExtractionRequest) -> List[Concept]:
    """Extract pedagogical concepts from either grounded document chunks or topic string."""
    if req.document and req.document.chunks:
        return await concept_service.extract_concepts_from_material(
            document_chunks=req.document.chunks,
            material_id=req.document.material_id,
        )
    elif req.topic and req.topic.strip():
        return await concept_service.extract_concepts_from_topic(
            topic=req.topic.strip(),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'topic' or 'document' must be provided for concept extraction.",
        )


@router.post(
    "/graph",
    response_model=ConceptGraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Construct validated ConceptGraph and deterministic topological ordering",
)
def build_graph(req: ConceptGraphRequest) -> ConceptGraphResponse:
    """Build cycle-validated ConceptGraph and compute topological sequence."""
    graph = concept_service.build_concept_graph(req.concepts)
    topological_order = concept_service.topological_sort(req.concepts)
    return ConceptGraphResponse(graph=graph, topological_order=topological_order)
