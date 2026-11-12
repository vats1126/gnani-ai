/**
 * API service for communication with the FastAPI backend.
 * Supports split-hosting via VITE_API_BASE_URL or unified Vercel proxy.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

/**
 * Fetch system and provider health status.
 */
export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

/**
 * Send a student turn (message + whiteboard snapshot + history) to the AI Tutor.
 * 
 * @param {Object} payload
 * @param {string} payload.session_id
 * @param {"maths"|"science"} [payload.subject="maths"]
 * @param {string} [payload.learner_level="school"]
 * @param {string} [payload.language_code="indic-auto"]
 * @param {string} [payload.message=""]
 * @param {"whiteboard"|"pdf"} [payload.input_source="whiteboard"]
 * @param {string|null} [payload.whiteboard_image_base64=null]
 * @param {"ask"|"check_work"|"hint"|"explain_simply"|"practice"} [payload.action="ask"]
 * @param {Array<Object>} [payload.history=null]
 */
export async function sendTutorTurn(payload) {
  try {
    const res = await fetch(`${API_BASE}/api/tutor/turn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      const errDetail = data?.error || {
        code: `HTTP_${res.status}`,
        message: data?.detail || res.statusText || 'Failed to complete tutor turn',
      };
      return { ok: false, error: errDetail };
    }

    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: err.message || 'Unable to connect to the backend server.',
      },
    };
  }
}

/**
 * Reset and close active session state on the backend.
 * 
 * @param {string} sessionId
 */
export async function resetTutorSession(sessionId) {
  try {
    const res = await fetch(`${API_BASE}/api/tutor/reset`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: sessionId }),
    });

    if (!res.ok) {
      return { ok: false };
    }
    return await res.json();
  } catch {
    return { ok: false };
  }
}

/**
 * Transcribe recorded audio using Gnani Prisma STT v3.0.
 * 
 * @param {Blob} wavBlob - 16kHz mono PCM WAV Blob
 * @param {string} [languageCode="indic-auto"]
 * @returns {Promise<{ ok: boolean, data?: { transcript: string, detected_language_code: string, provider: string }, error?: { code: string, message: string } }>}
 */
export async function transcribeAudio(wavBlob, languageCode = 'indic-auto') {
  try {
    const formData = new FormData();
    formData.append('audio_file', wavBlob, 'recording.wav');
    formData.append('language_code', languageCode);

    const res = await fetch(`${API_BASE}/api/voice/transcribe`, {
      method: 'POST',
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      const errDetail = data?.error || {
        code: `HTTP_${res.status}`,
        message: data?.detail || res.statusText || 'Audio transcription failed',
      };
      return { ok: false, error: errDetail };
    }

    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: err.message || 'Unable to connect to transcription service.',
      },
    };
  }
}

/**
 * Synthesize speech from text using Gnani Timbre TTS v3.0.
 * Returns a WAV audio Blob.
 * 
 * @param {string} text - Text to speak
 * @param {string} [languageCode="indic-auto"] - Indic language code
 * @returns {Promise<{ ok: boolean, blob?: Blob, error?: { code: string, message: string } }>}
 */
export async function speakText(text, languageCode = 'indic-auto') {
  try {
    const res = await fetch(`${API_BASE}/api/voice/speak`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        language_code: languageCode,
      }),
    });

    if (!res.ok) {
      let errDetail;
      try {
        const data = await res.json();
        errDetail = data?.error || {
          code: `HTTP_${res.status}`,
          message: data?.detail || res.statusText || 'Speech synthesis failed',
        };
      } catch {
        errDetail = {
          code: `HTTP_${res.status}`,
          message: res.statusText || 'Speech synthesis failed',
        };
      }
      return { ok: false, error: errDetail };
    }

    const blob = await res.blob();
    return { ok: true, blob };
  } catch (err) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: err.message || 'Unable to connect to speech synthesis service.',
      },
    };
  }
}

/**
 * Directly verify an algebraic equation step using SymPy CAS.
 * 
 * @param {string} originalEquation
 * @param {string} currentStep
 * @param {string} [previousStep=""]
 * @param {string} [variable="x"]
 */
export async function verifyMathStep(originalEquation, currentStep, previousStep = '', variable = 'x') {
  try {
    const res = await fetch(`${API_BASE}/api/tools/verify-step`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        original_equation: originalEquation,
        previous_step: previousStep,
        current_step: currentStep,
        variable,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data?.error || { message: 'Verification failed' } };
    }
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: err.message || 'Unable to connect to math verifier service.',
      },
    };
  }
}

/**
 * Generate a fresh practice question.
 * 
 * @param {string} [topic="linear_equations"]
 * @param {string} [difficulty="easy"]
 * @param {string} [language="en-IN"]
 */
export async function fetchPracticeQuestion(topic = 'linear_equations', difficulty = 'easy', language = 'en-IN') {
  try {
    const res = await fetch(`${API_BASE}/api/tools/practice-question`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        topic,
        difficulty,
        language,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data?.error || { message: 'Failed to generate practice question' } };
    }
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: err.message || 'Unable to connect to question generator service.',
      },
    };
  }
}
