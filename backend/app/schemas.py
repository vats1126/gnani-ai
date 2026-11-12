import base64
import re
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

MAX_IMAGE_BASE64_BYTES = 4 * 1024 * 1024  # 4 MB maximum image payload
MAX_AUDIO_BASE64_BYTES = 10 * 1024 * 1024  # 10 MB maximum audio recording payload

ActionType = Literal["ask", "check_work", "hint", "explain_simply", "practice"]
VerdictType = Literal["correct", "incorrect", "partial", "uncertain", "not_applicable"]
SubjectType = Literal["maths", "science"]
InputSourceType = Literal["whiteboard", "pdf"]

def clean_text_for_speech(raw_text: str) -> str:
    """Strips bulky markdown symbols (bold, italic, code blocks, latex delimiters) for TTS synthesis."""
    if not raw_text:
        return ""
    # Strip markdown bold/italic
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', raw_text)
    # Strip code spans / backticks
    text = re.sub(r'`+(.*?)`+', r'\1', text)
    # Strip markdown headings and bullet characters
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Strip LaTeX delimiters e.g. \(...\) or \[...\] or $$...$$
    text = re.sub(r'\\\[(.*?)\\\]', r'\1', text)
    text = re.sub(r'\\\((.*?)\\\)', r'\1', text)
    text = re.sub(r'\$\$(.*?)\$\$', r'\1', text)
    text = re.sub(r'\$(.*?)\$', r'\1', text)
    # Strip multiple consecutive whitespaces/newlines
    text = re.sub(r'\s+', ' ', text).strip()
    return text

class TutorTurnRequest(BaseModel):
    session_id: str = Field(..., description="Unique persistent client session ID")
    subject: SubjectType = Field(default="maths", description="Academic subject area")
    learner_level: str = Field(default="school", description="Target grade/learner level")
    language_code: str = Field(default="indic-auto", description="Preferred Indic locale or indic-auto")
    message: str = Field(default="", description="Student typed or transcribed question")
    input_source: InputSourceType = Field(default="whiteboard", description="Origin of visual content")
    whiteboard_image_base64: Optional[str] = Field(default=None, description="Base64 data URL or raw base64 JPEG/PNG")
    audio_base64: Optional[str] = Field(default=None, description="Base64 data URL or raw audio bytes (WAV/WEBM)")
    action: ActionType = Field(default="ask", description="Pedagogical intent for this turn")
    history: Optional[List[dict]] = Field(default=None, description="Stateless recent conversation history turns")

    @field_validator("whiteboard_image_base64")
    @classmethod
    def validate_image_payload(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if len(v) > MAX_IMAGE_BASE64_BYTES:
            raise ValueError(f"Whiteboard image payload exceeds maximum allowed size ({MAX_IMAGE_BASE64_BYTES} bytes)")
        return v

    @field_validator("audio_base64")
    @classmethod
    def validate_audio_payload(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if len(v) > MAX_AUDIO_BASE64_BYTES:
            raise ValueError(f"Audio payload exceeds maximum allowed size ({MAX_AUDIO_BASE64_BYTES} bytes)")
        return v

    def get_decoded_image_bytes(self) -> Optional[bytes]:
        """Strip data URL prefix if present and return raw image bytes."""
        if not self.whiteboard_image_base64:
            return None
        raw = self.whiteboard_image_base64
        if "base64," in raw:
            raw = raw.split("base64,", 1)[1]
        try:
            return base64.b64decode(raw, validate=True)
        except Exception as e:
            raise ValueError(f"Corrupted or invalid base64 image data: {e}")

    def get_decoded_audio_bytes(self) -> Optional[bytes]:
        """Strip data URL prefix if present and return raw audio bytes."""
        if not self.audio_base64:
            return None
        raw = self.audio_base64
        if "base64," in raw:
            raw = raw.split("base64,", 1)[1]
        try:
            return base64.b64decode(raw, validate=True)
        except Exception as e:
            raise ValueError(f"Corrupted or invalid base64 audio data: {e}")

class TutorTurnResponse(BaseModel):
    session_id: str
    answer: str
    language_code: str
    verdict: VerdictType = "not_applicable"
    transcript: str = ""
    steps: List[str] = Field(default_factory=list)
    next_suggestion: Optional[str] = None
    audio_data: Optional[str] = Field(default=None, description="Base64 data URL for synthesized voice feedback")
    fallback_mode: bool = Field(default=False, description="True if response was generated via local fallback rescue")

class ResetSessionRequest(BaseModel):
    session_id: str

class ResetSessionResponse(BaseModel):
    ok: bool
    session_id: str
    message: str

class TranscribeResponse(BaseModel):
    transcript: str
    detected_language_code: str
    provider: str = "gnani-prisma-v3.0"

class SpeakRequest(BaseModel):
    text: str = Field(..., max_length=1500, description="Text string to synthesize (max 1500 chars)")
    language_code: str = Field(default="en-IN", description="Target Indic locale")
    bypass_gnani: bool = Field(default=False, description="Bypasses Gnani Timbre to test or use Gemini Native Audio TTS")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        cleaned = clean_text_for_speech(v)
        if not cleaned:
            raise ValueError("Text cannot be empty after stripping markdown")
        if len(cleaned) > 1500:
            raise ValueError(f"Text length exceeds 1500 characters limit ({len(cleaned)} chars)")
        return cleaned

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text string to synthesize")
    language_code: str = Field(default="en-IN", description="Target Indic locale")

class TTSResponse(BaseModel):
    ok: bool
    audio_data: str
    format: str = "wav"
    language_code: str

class STTRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 audio payload")
    language_code: str = Field(default="indic-auto", description="Indic language code or indic-auto")

class STTResponse(BaseModel):
    ok: bool
    transcript: str
    language_code: str

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    error: ErrorDetail

class VerifyStepRequest(BaseModel):
    original_equation: str = Field(..., max_length=120, description="The starting equation (e.g. '2x = 8')")
    previous_step: str = Field(default="", max_length=120, description="Preceding step if part of sequence")
    current_step: str = Field(..., max_length=120, description="The step written by student to verify (e.g. 'x = 8')")
    variable: str = Field(default="x", max_length=10, description="Target variable")

class VerifyStepResponse(BaseModel):
    status: Literal["correct", "incorrect", "uncertain"]
    reason: str
    expected_next_step: Optional[str] = None

class PracticeQuestionRequest(BaseModel):
    topic: str = Field(default="linear_equations", description="Topic to generate")
    difficulty: str = Field(default="easy", description="Difficulty level")
    language: str = Field(default="en-IN", description="Language code")

class PracticeQuestionResponse(BaseModel):
    topic: str
    difficulty: str
    question: str
    equation: str
    variable: str
    hint: str

