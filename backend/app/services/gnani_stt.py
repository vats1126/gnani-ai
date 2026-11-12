import logging
import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

STT_ENDPOINT = "https://api.vachana.ai/stt/v3"
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB maximum audio payload (~30-60s clip)
SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "flac", "aac", "m4a"}

class GnaniNotConfiguredError(Exception):
    """Raised when GNANI_API_KEY is missing or placeholder."""
    pass

class GnaniSTTError(Exception):
    """Raised when Gnani STT transcription fails."""
    pass

def _detect_format(filename: str, content_type: str) -> str:
    """Infers the audio container format from file extension or content-type header."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext:
        return ext

    ct = content_type.lower()
    for fmt in SUPPORTED_FORMATS:
        if fmt in ct:
            return fmt
    if "webm" in ct:
        return "webm"
    return "wav"

async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "recording.wav",
    content_type: str = "audio/wav",
    language_code: str = "indic-auto"
) -> Dict[str, Any]:
    """
    Transcribes audio using Gnani Prisma v3.0 REST API.
    Enforces format validation, size constraints, and converts webm if ffmpeg is available.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        raise ValueError("Audio recording is too short or empty (minimum 0.5s required)")

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(f"Audio file exceeds maximum 10MB limit ({len(audio_bytes)} bytes)")

    fmt = _detect_format(filename, content_type)
    if fmt not in SUPPORTED_FORMATS and fmt != "webm":
        raise ValueError(
            f"Unsupported audio format '{fmt}'. Gnani STT supports: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    if not settings.is_gnani_configured:
        raise GnaniNotConfiguredError("GNANI_API_KEY is not configured in backend/.env")

    # Handle WebM fallback
    if fmt == "webm":
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise ValueError(
                "Audio format 'webm' is not accepted by Gnani REST STT. "
                "The browser must encode audio directly to 16-bit PCM WAV (audio/wav)."
            )
        # Attempt conversion if ffmpeg is found
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as in_f:
                in_f.write(audio_bytes)
                in_path = in_f.name
            out_path = in_path + ".wav"
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", out_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(out_path, "rb") as out_f:
                audio_bytes = out_f.read()
            filename = "converted.wav"
            content_type = "audio/wav"
            os.remove(in_path)
            os.remove(out_path)
        except Exception as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            raise ValueError(f"Failed to convert WebM audio: {e}")
    elif fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported audio format '{fmt}'. Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}")

    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY
    }

    files = {
        "audio_file": (filename, audio_bytes, content_type)
    }
    data = {
        "model": "prisma-v3.0",
        "language_code": language_code or "indic-auto"
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(STT_ENDPOINT, headers=headers, data=data, files=files)

            if resp.status_code in (200, 201):
                try:
                    res_json = resp.json()
                except Exception:
                    res_json = {"transcript": resp.text.strip()}

                transcript = ""
                detected_lang = language_code

                if isinstance(res_json, dict):
                    transcript = (
                        res_json.get("transcript") or
                        res_json.get("text") or
                        res_json.get("transcription") or
                        ""
                    )
                    if not transcript and "results" in res_json and isinstance(res_json["results"], list):
                        parts = [r.get("transcript", "") for r in res_json["results"] if isinstance(r, dict)]
                        transcript = " ".join(parts).strip()

                    detected_lang = (
                        res_json.get("detected_language_code") or
                        res_json.get("language_code") or
                        res_json.get("language_detected") or
                        language_code
                    )
                elif isinstance(res_json, str):
                    transcript = res_json

                # If indic-auto did not return an explicit locale, fallback safely
                if detected_lang == "indic-auto" or not detected_lang:
                    detected_lang = "en-IN"

                return {
                    "transcript": transcript.strip(),
                    "detected_language_code": detected_lang,
                    "provider": "gnani-prisma-v3.0"
                }
            else:
                logger.error(f"Gnani Prisma STT returned HTTP {resp.status_code}: {resp.text[:200]}")
                raise GnaniSTTError(f"Prisma STT failed with status {resp.status_code}")

    except httpx.RequestError as e:
        logger.error(f"Gnani Prisma network error: {e}")
        raise GnaniSTTError(f"Network error contacting Gnani STT API: {e}")
