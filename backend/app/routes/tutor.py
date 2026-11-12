import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.schemas import (
    TutorTurnRequest,
    TutorTurnResponse,
    ResetSessionRequest,
    ResetSessionResponse,
    VerifyStepRequest,
    VerifyStepResponse,
    ErrorResponse,
    ErrorDetail,
)
from app.tools.math_verifier import verify_equation_step

from app.services.session_manager import session_manager
from app.services.gemini_live import (
    execute_tutor_turn,
    GeminiNotConfiguredError,
    GeminiProviderError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

@router.post(
    "/turn",
    response_model=TutorTurnResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def tutor_turn(request: TutorTurnRequest):
    record = await session_manager.get_or_create(
        session_id=request.session_id,
        subject=request.subject,
        language_code=request.language_code
    )

    # Hydrate stateless history if this container instance has no record
    if request.history:
        record.hydrate_history(request.history)

    # Use the session lock so concurrent turns for the same session never collide
    if record.lock.locked():
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="SESSION_BUSY",
                    message="A turn is currently in progress for this session. Please wait."
                )
            ).model_dump()
        )

    try:
        # Validate and decode image payload early if present
        if request.whiteboard_image_base64:
            request.get_decoded_image_bytes()

        async with record.lock:
            response = await execute_tutor_turn(request, record)
            return response

    except GeminiNotConfiguredError as e:
        logger.warning(f"Turn rejected: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GEMINI_NOT_CONFIGURED",
                    message="Gemini API is not configured. Please add your GEMINI_API_KEY in backend/.env."
                )
            ).model_dump()
        )

    except ValueError as e:
        logger.warning(f"Payload validation error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_PAYLOAD",
                    message=str(e)
                )
            ).model_dump()
        )

    except GeminiProviderError as e:
        logger.error(f"Gemini provider failure: {e}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="PROVIDER_ERROR",
                    message="Upstream Gemini Live service encountered an error. Please try again."
                )
            ).model_dump()
        )

    except Exception as e:
        logger.exception(f"Unexpected error in tutor_turn: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred while processing the tutor turn."
                )
            ).model_dump()
        )

@router.post("/reset", response_model=ResetSessionResponse)
async def reset_session(payload: ResetSessionRequest):
    await session_manager.close_session(payload.session_id)
    return ResetSessionResponse(
        ok=True,
        session_id=payload.session_id,
        message="Session and live connection reset successfully"
    )

@router.post("/verify-step", response_model=VerifyStepResponse)
async def verify_step_alias(request: VerifyStepRequest):
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

