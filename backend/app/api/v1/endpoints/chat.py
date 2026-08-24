"""
Chat endpoint — RAG question answering.

POST /api/v1/chat

Phase 1: Returns a stub response to validate the API contract.
Phase 4: Will wire in the full RAG pipeline (retrieval → prompt → LLM).
"""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import APIResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=APIResponse[ChatResponse],
    summary="Ask a question against indexed documents",
    description=(
        "Submits a question to the RAG pipeline. The pipeline retrieves relevant "
        "document chunks from Azure AI Search and generates a grounded answer using "
        "Azure OpenAI. Citations are returned alongside the answer."
    ),
    status_code=status.HTTP_200_OK,
)
async def chat(
    body: ChatRequest,
    request: Request,
) -> APIResponse[ChatResponse]:
    """
    RAG chat endpoint.

    Phase 1 stub — returns a placeholder response.
    The real implementation will inject a ChatService via Depends() in Phase 4.
    """
    logger.info(
        "chat_request",
        question_length=len(body.question),
        history_turns=len(body.conversation_history),
        top_k=body.top_k,
    )

    # Stub response
    stub_response = ChatResponse(
        answer=("This is a Phase 1 stub response."),
        citations=[],
        model="stub",
        retrieval_count=0,
    )

    return APIResponse(data=stub_response, request_id=request.state.request_id)
