import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.schemas import (
    VerifyStepRequest,
    VerifyStepResponse,
    PracticeQuestionRequest,
    PracticeQuestionResponse,
    ErrorResponse,
    ErrorDetail
)
from app.tools.math_verifier import verify_equation_step
from app.tools.practice_generator import generate_practice_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])

@router.post(
    "/verify-step",
    response_model=VerifyStepResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def verify_step_endpoint(request: VerifyStepRequest):
    """
    Direct endpoint for verifying an algebraic equation step using SymPy CAS.
    """
    try:
        res = verify_equation_step(
            original_equation=request.original_equation,
            previous_step=request.previous_step,
            current_step=request.current_step,
            variable=request.variable
        )
        return VerifyStepResponse(
            status=res["status"],
            reason=res["reason"],
            expected_next_step=res.get("expected_next_step")
        )
    except Exception as e:
        logger.exception(f"Error in verify_step_endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VERIFICATION_FAILED",
                    message="An error occurred while verifying the mathematical step."
                )
            ).model_dump()
        )

@router.post(
    "/practice-question",
    response_model=PracticeQuestionResponse,
    responses={
        500: {"model": ErrorResponse}
    }
)
async def practice_question_endpoint(request: PracticeQuestionRequest):
    """
    Direct endpoint for generating a fresh practice question.
    """
    try:
        res = generate_practice_question(
            topic=request.topic,
            difficulty=request.difficulty,
            language=request.language
        )
        return PracticeQuestionResponse(
            topic=res["topic"],
            difficulty=res["difficulty"],
            question=res["question"],
            equation=res["equation"],
            variable=res["variable"],
            hint=res["hint"]
        )
    except Exception as e:
        logger.exception(f"Error in practice_question_endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GENERATION_FAILED",
                    message="An error occurred while generating a practice question."
                )
            ).model_dump()
        )

