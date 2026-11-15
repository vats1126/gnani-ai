import logging
from fastapi import APIRouter, UploadFile, File, Form, Response, status
from fastapi.responses import JSONResponse
from app.schemas import (
    TranscribeResponse,
    SpeakRequest,
    ErrorResponse,
    ErrorDetail
)
from app.services.gnani_stt import (
    transcribe_audio,
    GnaniNotConfiguredError as STTNotConfiguredError,
    GnaniSTTError
)
from app.services.gnani_tts import (
    synthesize_speech,
    GnaniNotConfiguredError as TTSNotConfiguredError,
    GnaniTTSError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def transcribe_endpoint(
    audio_file: UploadFile = File(..., description="Recorded audio file (WAV preferred)"),
    language_code: str = Form("indic-auto", description="Indic language code or indic-auto")
):
    try:
        audio_bytes = await audio_file.read()
        res = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio_file.filename or "recording.wav",
            content_type=audio_file.content_type or "audio/wav",
            language_code=language_code
        )
        return TranscribeResponse(
            transcript=res["transcript"],
            detected_language_code=res["detected_language_code"],
            provider="gnani-prisma-v3.0"
        )

    except STTNotConfiguredError as e:
        logger.warning(f"Transcribe rejected: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GNANI_NOT_CONFIGURED",
                    message="Gnani Voice API is not configured. Please add GNANI_API_KEY in backend/.env."
                )
            ).model_dump()
        )

    except ValueError as e:
        logger.warning(f"Audio validation error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_AUDIO",
                    message=str(e)
                )
            ).model_dump()
        )

    except GnaniSTTError as e:
        logger.error(f"Prisma STT error: {e}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GNANI_STT_FAILED",
                    message="Speech-to-text service encountered an error. Please try again."
                )
            ).model_dump()
        )

    except Exception as e:
        logger.exception(f"Unexpected error in transcribe_endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred during audio transcription."
                )
            ).model_dump()
        )

@router.post(
    "/speak",
    responses={
        200: {"content": {"audio/wav": {}}},
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def speak_endpoint(payload: SpeakRequest):
    try:
        wav_bytes = await synthesize_speech(
            text=payload.text,
            language_code=payload.language_code
        )
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav"
            }
        )

    except TTSNotConfiguredError as e:
        logger.warning(f"Speak rejected: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GNANI_NOT_CONFIGURED",
                    message="Gnani Voice API is not configured. Please add GNANI_API_KEY in backend/.env."
                )
            ).model_dump()
        )

    except ValueError as e:
        logger.warning(f"Speak validation error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_PAYLOAD",
                    message=str(e)
                )
            ).model_dump()
        )

    except GnaniTTSError as e:
        logger.error(f"Timbre TTS error: {e}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="GNANI_TTS_FAILED",
                    message="Text-to-speech service encountered an error. Please try again."
                )
            ).model_dump()
        )

    except Exception as e:
        logger.exception(f"Unexpected error in speak_endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred during speech synthesis."
                )
            ).model_dump()
        )

