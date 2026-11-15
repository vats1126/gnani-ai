import base64
from collections import OrderedDict
import logging
import re
from typing import Optional
import httpx
from app.config import settings
from app.schemas import clean_text_for_speech

logger = logging.getLogger(__name__)

TTS_ENDPOINT = "https://api.vachana.ai/api/v1/tts/inference"

SUPPORTED_LOCALES = {
    "hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN",
    "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN"
}

# In-memory LRU Cache for synthesized WAV bytes (up to 64 items)
_TTS_CACHE: OrderedDict[tuple[str, str, str], bytes] = OrderedDict()
_MAX_CACHE_SIZE = 64


def clear_tts_cache():
    """Clears the in-memory TTS cache (useful for tests)."""
    _TTS_CACHE.clear()


def get_cached_tts(key: tuple[str, str, str]) -> Optional[bytes]:
    if key in _TTS_CACHE:
        _TTS_CACHE.move_to_end(key)
        return _TTS_CACHE[key]
    return None


def set_cached_tts(key: tuple[str, str, str], data: bytes):
    if key in _TTS_CACHE:
        _TTS_CACHE.move_to_end(key)
    else:
        if len(_TTS_CACHE) >= _MAX_CACHE_SIZE:
            _TTS_CACHE.popitem(last=False)
    _TTS_CACHE[key] = data


class GnaniNotConfiguredError(Exception):
    """Raised when GNANI_API_KEY is missing or placeholder."""
    pass


class GnaniTTSError(Exception):
    """Raised when Gnani TTS synthesis fails."""
    pass


def detect_script_locale(text: str) -> str:
    """Detects Indic script based on Unicode codepoint ranges."""
    for char in text:
        cp = ord(char)
        if 0x0900 <= cp <= 0x097F:
            return "hi-IN"  # Devanagari (Hindi / Marathi)
        elif 0x0C80 <= cp <= 0x0CFF:
            return "kn-IN"  # Kannada
        elif 0x0B80 <= cp <= 0x0BFF:
            return "ta-IN"  # Tamil
        elif 0x0C00 <= cp <= 0x0C7F:
            return "te-IN"  # Telugu
        elif 0x0D00 <= cp <= 0x0D7F:
            return "ml-IN"  # Malayalam
        elif 0x0980 <= cp <= 0x09FF:
            return "bn-IN"  # Bengali
        elif 0x0A80 <= cp <= 0x0AFF:
            return "gu-IN"  # Gujarati
        elif 0x0A00 <= cp <= 0x0A7F:
            return "pa-IN"  # Gurmukhi / Punjabi
    return "en-IN"


def resolve_tts_locale(language_code: Optional[str], text: str = "") -> str:
    """
    Normalizes language code.
    If 'indic-auto' or 'auto', inspects text Unicode script ranges.
    Always returns a valid explicit locale from the 10 supported Gnani locales.
    """
    if not language_code or language_code in ("indic-auto", "auto"):
        return detect_script_locale(text)

    clean_code = language_code.strip()
    if clean_code in SUPPORTED_LOCALES:
        return clean_code

    # Match by prefix (e.g. 'kn' -> 'kn-IN')
    prefix = clean_code.split("-")[0].lower()
    for loc in SUPPORTED_LOCALES:
        if loc.startswith(prefix):
            return loc

    return detect_script_locale(text)


async def synthesize_speech(text: str, language_code: str = "en-IN") -> bytes:
    """
    Synthesizes speech using Gnani Timbre v3.0 REST API with LRU caching.
    Returns raw WAV bytes (starting with 'RIFF').
    """
    cleaned_text = clean_text_for_speech(text)
    if not cleaned_text:
        raise ValueError("Text cannot be empty for speech synthesis")

    target_lang = resolve_tts_locale(language_code, cleaned_text)
    active_voice = settings.GNANI_TTS_VOICE
    if not active_voice or active_voice.lower() == "default":
        active_voice = "Shivani"
    cache_key = (cleaned_text, target_lang, active_voice)

    # 1. Check LRU Cache
    cached_bytes = get_cached_tts(cache_key)
    if cached_bytes is not None:
        logger.info(f"Gnani TTS: Cache HIT for '{cleaned_text[:30]}...' ({target_lang})")
        return cached_bytes

    # 2. Check Provider Key
    if not settings.is_gnani_configured:
        raise GnaniNotConfiguredError("GNANI_API_KEY is not configured in backend/.env")

    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY,
        "Content-Type": "application/json"
    }

    # Audio config matching Section 10 specification
    payload = {
        "text": cleaned_text,
        "model": "timbre-v3.0",
        "voice": active_voice,
        "language": target_lang,
        "audio_config": {
            "sample_rate": 48000,
            "sample_rate_hertz": 48000,
            "num_channels": 1,
            "channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "audio_encoding": "linear_pcm",
            "container": "wav",
            "format": "wav"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TTS_ENDPOINT, headers=headers, json=payload)

            # Fallback for voice validation error: retry once with default voice
            if resp.status_code in (400, 422) and payload.get("voice") != "default":
                logger.warning(
                    f"Gnani TTS returned {resp.status_code} with voice '{active_voice}'. Retrying with 'default' voice..."
                )
                payload["voice"] = "default"
                resp = await client.post(TTS_ENDPOINT, headers=headers, json=payload)

            if resp.status_code == 200:
                raw_bytes = resp.content
                wav_result = raw_bytes
                if not raw_bytes.startswith(b"RIFF"):
                    # JSON response containing base64 audio
                    try:
                        data = resp.json()
                        audio_b64 = data.get("audioContent") or data.get("audio") or data.get("data")
                        if audio_b64:
                            wav_result = base64.b64decode(audio_b64)
                    except Exception:
                        pass

                # Store in LRU Cache
                set_cached_tts(cache_key, wav_result)
                return wav_result
            else:
                logger.error(f"Gnani Timbre TTS returned HTTP {resp.status_code}: {resp.text[:200]}")
                raise GnaniTTSError(f"Timbre TTS synthesis failed with status {resp.status_code}")

    except httpx.RequestError as e:
        logger.error(f"Gnani Timbre network error: {e}")
        raise GnaniTTSError(f"Network error contacting Gnani TTS API: {e}")
