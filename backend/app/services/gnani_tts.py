import base64
from collections import OrderedDict
import io
import logging
import re
from typing import Optional
import wave
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


class GeminiTTSError(Exception):
    """Raised when Gemini Native Audio TTS fails."""
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


# ---------------------------------------------------------------------
# Math & Speech Normalization
# ---------------------------------------------------------------------
def verbalize_math_for_speech(text: str, lang: str = "en-IN") -> str:
    """
    Converts mathematical expressions into natural spoken words localized by language
    (en-IN, hi-IN, kn-IN, ta-IN, te-IN), strips bullet points, markdown symbols, and
    LaTeX brackets, and formats spoken responses into 1-4 conversational sentences.
    """
    if not text:
        return ""
    lang_prefix = (lang or "en-IN").split("-")[0].lower()

    # 1. Strip markdown code blocks & inline code
    t = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    t = re.sub(r"`(.*?)`", r"\1", t)

    # 2. Strip bullet points & numbered lists at start of lines
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*\d+[\.\)]\s+", "", t, flags=re.MULTILINE)

    # 3. Strip markdown headers (#, ##), bold (**), italic (*), strikethrough (~~), blockquotes (>)
    t = re.sub(r"#+\s*", "", t)
    t = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", t)
    t = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", t)
    t = re.sub(r"~~(.*?)~~", r"\1", t)
    t = re.sub(r"^\s*>\s*", "", t, flags=re.MULTILINE)

    # 4. Strip LaTeX math delimiters
    t = re.sub(r"\\\[(.*?)\\\]", r"\1", t)
    t = re.sub(r"\\\((.*?)\\\)", r"\1", t)
    t = re.sub(r"\$\$(.*?)\$\$", r"\1", t)
    t = re.sub(r"\$(.*?)\$", r"\1", t)
    t = re.sub(r"\\text\{(.*?)\}", r"\1", t)

    # 5. Localized vocabulary dictionary
    words = {
        "en": {
            "plus": " plus ",
            "minus": " minus ",
            "times": " multiplied by ",
            "div": " divided by ",
            "equals": " equals ",
            "neq": " does not equal ",
            "leq": " is less than or equal to ",
            "geq": " is greater than or equal to ",
            "lt": " is less than ",
            "gt": " is greater than ",
            "pm": " plus or minus ",
            "squared": " squared ",
            "cubed": " cubed ",
            "power": " to the power of ",
            "sqrt": " square root of ",
            "over": " divided by ",
            "approx": " is approximately ",
            "arrow": " gives ",
        },
        "hi": {
            "plus": " प्लस ",
            "minus": " माइनस ",
            "times": " गुणा ",
            "div": " भाग ",
            "equals": " बराबर ",
            "neq": " बराबर नहीं है ",
            "leq": " से छोटा या बराबर ",
            "geq": " से बड़ा या बराबर ",
            "lt": " से छोटा ",
            "gt": " से बड़ा ",
            "pm": " प्लस या माइनस ",
            "squared": " का वर्ग ",
            "cubed": " का घन ",
            "power": " की घात ",
            "sqrt": " वर्गमूल ",
            "over": " बटे ",
            "approx": " लगभग बराबर ",
            "arrow": " तो ",
        },
        "kn": {
            "plus": " ಪ್ಲಸ್ ",
            "minus": " ಮೈನಸ್ ",
            "times": " ಗುಣಿಸು ",
            "div": " ಭಾಗಿಸು ",
            "equals": " ಸಮ ",
            "neq": " ಸಮವಾಗಿಲ್ಲ ",
            "leq": " ಗಿಂತ ಕಡಿಮೆ ಅಥವಾ ಸಮ ",
            "geq": " ಗಿಂತ ಹೆಚ್ಚು ಅಥವಾ ಸಮ ",
            "lt": " ಗಿಂತ ಕಡಿಮೆ ",
            "gt": " ಗಿಂತ ಹೆಚ್ಚು ",
            "pm": " ಪ್ಲಸ್ ಅಥವಾ ಮೈನಸ್ ",
            "squared": " ರ ವರ್ಗ ",
            "cubed": " ರ ಘನ ",
            "power": " ರ ಘಾತ ",
            "sqrt": " ವರ್ಗಮೂಲ ",
            "over": " ಭಾಗಿಸು ",
            "approx": " ಸರಿಸುಮಾರು ಸಮ ",
            "arrow": " ನಂತರ ",
        },
        "ta": {
            "plus": " பிளஸ் ",
            "minus": " மைனஸ் ",
            "times": " பெருக்கல் ",
            "div": " வகுத்தல் ",
            "equals": " சமம் ",
            "neq": " சமமில்லை ",
            "leq": " குறைவு அல்லது சமம் ",
            "geq": " அதிகம் அல்லது சமம் ",
            "lt": " விடக் குறைவு ",
            "gt": " விட அதிகம் ",
            "pm": " பிளஸ் அல்லது மைனஸ் ",
            "squared": " இன் வர்க்கம் ",
            "cubed": " இன் கனம் ",
            "power": " இன் அடுக்கு ",
            "sqrt": " வர்க்கமூலம் ",
            "over": " வகுத்தல் ",
            "approx": " தோராயமாக சமம் ",
            "arrow": " எனவே ",
        },
        "te": {
            "plus": " ప్లస్ ",
            "minus": " మైనస్ ",
            "times": " గుణకారం ",
            "div": " భాగహారం ",
            "equals": " సమానం ",
            "neq": " సమానం కాదు ",
            "leq": " కంటే తక్కువ లేదా సమానం ",
            "geq": " కంటే ఎక్కువ లేదా సమానం ",
            "lt": " కంటే తక్కువ ",
            "gt": " కంటే ఎక్కువ ",
            "pm": " ప్లస్ లేదా మైనస్ ",
            "squared": " యొక్క వర్గం ",
            "cubed": " యొక్క ఘనం ",
            "power": " ఘాతం ",
            "sqrt": " వర్గమూలం ",
            "over": " భాగహారం ",
            "approx": " దాదాపు సమానం ",
            "arrow": " అంటే ",
        }
    }
    w = words.get(lang_prefix, words["en"])

    # Arrows
    t = re.sub(r"\s*(?:->|-->|=>|==>)\s*", w["arrow"], t)

    # Fractions: \frac{a}{b}
    t = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", rf"\1 {w['over']} \2", t)

    # Square roots: \sqrt{x} or √x
    t = re.sub(r"\\sqrt\{([^}]+)\}", rf"{w['sqrt']} \1", t)
    t = re.sub(r"[√]\s*([a-zA-Z0-9]+)", rf"{w['sqrt']} \1", t)

    # Powers: ^2, ², ^3, ³, ^n
    t = re.sub(r"(\w+)\^2|\b(\w+)²", rf"\1{w['squared']}", t)
    t = re.sub(r"(\w+)\^3|\b(\w+)³", rf"\1{w['cubed']}", t)
    t = re.sub(r"(\w+)\^[\{\(]?([0-9a-zA-Z\+\-\*\/]+)[\}\)]?", rf"\1{w['power']}\2", t)

    # Spacing between coefficient and variable (2x -> 2 x)
    t = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", t)

    # Relational & arithmetic symbols
    t = re.sub(r"\s*(?:!=|≠|\\neq)\s*", w["neq"], t)
    t = re.sub(r"\s*(?:<=|≤|\\leq|\\le)\s*", w["leq"], t)
    t = re.sub(r"\s*(?:>=|≥|\\geq|\\ge)\s*", w["geq"], t)
    t = re.sub(r"\s*(?:\\approx|≈)\s*", w["approx"], t)
    t = re.sub(r"\s*(?:\+-|±|\\pm)\s*", w["pm"], t)
    t = re.sub(r"\s*=\s*", w["equals"], t)
    t = re.sub(r"\s*\+\s*", w["plus"], t)

    # Negative sign before number/variable
    t = re.sub(r"(^|[\s=+\(])-([a-zA-Z0-9])", rf"\1{w['minus']}\2", t)
    # Math minus between tokens (avoiding word hyphens like step-by-step)
    t = re.sub(r"(?<=\w)\s+-\s+(?=\w)|(?<=\d)\s*-\s*(?=\w)|(?<=\w)\s*-\s*(?=\d)", w["minus"], t)

    # Multiplication & Division
    t = re.sub(r"\s*(?:\*|×|\\times)\s*", w["times"], t)
    t = re.sub(r"\s*(?:÷|\\div)\s*", w["div"], t)
    t = re.sub(r"(?<=\d|[a-zA-Z\)\}\]])\s*/\s*(?=\d|[a-zA-Z\(\{\[])", w["div"], t)

    # Stripping brackets & formatting pauses
    t = re.sub(r"[\(\)\[\]\{\}]", " ", t)
    t = re.sub(r":\s*", ", ", t)
    t = re.sub(r"[ \t]+", " ", t).strip()

    # Split into sentences and limit to 1-4 conversational sentences
    raw_sentences = [s.strip(" ,.") for s in re.split(r"[\n\r]+|\.(?!\d)\s*|[!?।]\s*", t) if s.strip(" ,.")]
    chosen = raw_sentences[:4]
    if not chosen:
        return ""

    res = ". ".join(chosen)
    if not res.endswith("."):
        res += "."
    return res


# ---------------------------------------------------------------------
# PCM to RIFF WAV Converter
# ---------------------------------------------------------------------
def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, num_channels: int = 1, sampwidth: int = 2) -> bytes:
    """Wraps raw 16-bit linear PCM audio bytes into a valid RIFF WAV container using wave standard library."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------
# Primary: Gnani Timbre TTS
# ---------------------------------------------------------------------
async def synthesize_gnani_timbre(cleaned_text: str, target_lang: str) -> bytes:
    if not settings.is_gnani_configured:
        raise GnaniNotConfiguredError("GNANI_API_KEY is not configured in backend/.env")

    active_voice = settings.GNANI_TTS_VOICE
    if not active_voice or active_voice.lower() == "default":
        active_voice = "Shivani"

    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY,
        "Content-Type": "application/json"
    }

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

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(TTS_ENDPOINT, headers=headers, json=payload)
        if resp.status_code in (400, 422) and payload.get("voice") != "default":
            logger.warning(
                f"Gnani TTS returned {resp.status_code} with voice '{active_voice}'. Retrying with 'default' voice..."
            )
            payload["voice"] = "default"
            resp = await client.post(TTS_ENDPOINT, headers=headers, json=payload)

        if resp.status_code == 200:
            raw_bytes = resp.content
            if not raw_bytes.startswith(b"RIFF"):
                try:
                    data = resp.json()
                    b64 = data.get("audioContent") or data.get("audio") or data.get("data")
                    if b64:
                        raw_bytes = base64.b64decode(b64)
                except Exception:
                    pass
            return raw_bytes
        else:
            raise GnaniTTSError(f"Gnani Timbre returned status {resp.status_code}: {resp.text[:200]}")


# ---------------------------------------------------------------------
# Secondary Fallback: Gemini Native Audio TTS
# ---------------------------------------------------------------------
async def synthesize_gemini_audio(cleaned_text: str, target_lang: str = "en-IN") -> bytes:
    """Synthesizes speech using Gemini Native Audio modality and wraps in RIFF WAV."""
    if not settings.is_gemini_configured:
        raise GeminiTTSError("GEMINI_API_KEY is not configured for Gemini Audio TTS")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options={"api_version": "v1alpha"})

    models_to_try = [settings.GEMINI_LIVE_MODEL, "gemini-2.0-flash-live-001", "gemini-2.5-flash-preview-tts"]
    last_err = None

    for model_name in models_to_try:
        try:
            config = types.LiveConnectConfig(
                response_modalities=[types.Modality.AUDIO],
                system_instruction=types.Content(
                    parts=[types.Part.from_text(text=(
                        f"You are a warm, clear, encouraging multilingual tutor speech synthesizer. "
                        f"Read the following text aloud verbatim in {target_lang} with natural pacing. "
                        f"Do NOT add any greetings, commentary, or conversational additions."
                    ))]
                )
            )

            pcm_chunks = []
            async with client.aio.live.connect(model=model_name, config=config) as session:
                prompt_input = f"Read aloud verbatim:\n{cleaned_text}"
                await session.send(input=prompt_input, end_of_turn=True)
                async for resp in session.receive():
                    sc = resp.server_content
                    if sc and sc.model_turn:
                        for p in sc.model_turn.parts:
                            if p.inline_data and p.inline_data.data:
                                pcm_chunks.append(p.inline_data.data)
                    if sc and sc.turn_complete:
                        break

            if pcm_chunks:
                raw_pcm = b"".join(pcm_chunks)
                wav_bytes = pcm_to_wav(raw_pcm, sample_rate=24000, num_channels=1, sampwidth=2)
                return wav_bytes

        except Exception as e:
            last_err = e
            logger.warning(f"Gemini Audio TTS attempt with '{model_name}' failed: {e}")
            continue

    raise GeminiTTSError(f"Gemini Native Audio TTS failed across all models: {last_err}")


# ---------------------------------------------------------------------
# Dual Cloud Neural TTS Pipeline Entrypoint
# ---------------------------------------------------------------------
async def synthesize_speech(text: str, language_code: str = "en-IN", bypass_gnani: bool = False) -> bytes:
    """
    Dual Cloud Neural TTS Pipeline:
      1. Speech Normalization via verbalize_math_for_speech.
      2. Primary: Gnani Timbre v3.0 (48kHz mono WAV).
      3. Secondary Fallback: Gemini Native Audio TTS (24kHz PCM -> RIFF WAV).
      4. In-memory LRU Caching across calls.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty for speech synthesis")

    target_lang = resolve_tts_locale(language_code, text)
    verbalized = verbalize_math_for_speech(text, target_lang)
    if not verbalized:
        verbalized = clean_text_for_speech(text)

    cache_key = (verbalized, target_lang, f"bypass={bypass_gnani}")
    cached = get_cached_tts(cache_key)
    if cached is not None:
        logger.info(f"TTS LRU Cache HIT for '{verbalized[:30]}...' ({target_lang})")
        return cached

    # Primary: Gnani Timbre
    if not bypass_gnani:
        try:
            wav_bytes = await synthesize_gnani_timbre(verbalized, target_lang)
            set_cached_tts(cache_key, wav_bytes)
            return wav_bytes
        except Exception as gnani_err:
            logger.warning(f"Primary Gnani TTS failed ({gnani_err}). Cascading to Gemini Native Audio TTS...")

    # Secondary: Gemini Native Audio TTS
    try:
        wav_bytes = await synthesize_gemini_audio(verbalized, target_lang)
        set_cached_tts(cache_key, wav_bytes)
        return wav_bytes
    except Exception as gemini_err:
        logger.error(f"Secondary Gemini TTS failed: {gemini_err}")
        raise GnaniTTSError(f"All TTS cloud providers failed (Gnani: bypass={bypass_gnani}, Gemini: {gemini_err})")
