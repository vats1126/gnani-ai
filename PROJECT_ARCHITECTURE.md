# Agentic Multilingual Learning Tutor — Project Architecture & Specification

## 1. Executive Summary & Product Vision
The **Agentic Multilingual Learning Tutor** is an interactive, voice-first, multimodal educational assistant designed for multilingual students across India. It bridges the conceptual learning gap in STEM and foundational subjects by coupling **real-time visual whiteboard interaction**, **low-latency conversational AI** (powered by Google Gemini Live), **high-fidelity Indic speech capabilities** (Gnani Timbre TTS & Prisma STT), and **deterministic mathematical verification** (SymPy).

Rather than delivering rote answers, the tutor guides learners socratic-style in their native tongue (e.g., Kannada, Hindi, Tamil, Telugu, English) while observing the student's handwritten work on an interactive canvas.

---

## 2. System Architecture & Topology

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT TIER                                       |
|  React 18 + Vite + Plain JavaScript (No TypeScript)                              |
|  - Canvas Whiteboard (Draw, Clear, Undo, Snapshot Capture)                        |
|  - Audio Capture / Streaming (Web Audio API / MediaRecorder)                      |
|  - Audio Playback (HTML5 Audio / Web Audio Buffer)                                |
|  - Session & State Management (Plain React Hooks: useState, useEffect, useRef)    |
|  - Vite Proxy (/api -> http://127.0.0.1:8000)                                     |
+------------------------------------------+----------------------------------------+
                                           | HTTP / SSE / WebSocket
                                           v
+-----------------------------------------------------------------------------------+
|                                BACKEND TIER                                       |
|  Python 3.10+ / FastAPI + Uvicorn (Async Core)                                   |
|                                                                                   |
|  [ Routes ]                                                                       |
|  - GET  /api/health            -> System & Provider Configuration Status          |
|  - POST /api/session/start     -> Initialize Tutor Session                        |
|  - POST /api/verify/math       -> Deterministic Math Verification (SymPy)         |
|  - POST /api/tts               -> Synthesize Speech via Gnani Timbre              |
|  - POST /api/stt               -> Transcribe Audio via Gnani Prisma               |
|  - WS   /api/live/stream       -> Gemini Live Multimodal Bi-directional Relay     |
|                                                                                   |
|  [ Services / Modules ]                                                           |
|  - app.config                  -> Safe Environment Config & Validation            |
|  - app.services.gemini_live    -> Google GenAI SDK (gemini-3.8-live) Client       |
|  - app.services.gnani_tts      -> Timbre v3.0 REST API Client                     |
|  - app.services.gnani_stt      -> Prisma v3.0 REST API Client                     |
|  - app.services.math_verifier  -> SymPy CAS Engine for Ground Truth Checks        |
+-------------------+---------------------+--------------------+--------------------+
                    |                     |                    |
                    v                     v                    v
         +--------------------+  +------------------+  +------------------+
         | Google Gemini Live |  | Gnani Timbre TTS |  | Gnani Prisma STT |
         |   Live API SDK     |  | vachana.ai API   |  | vachana.ai API   |
         | (gemini-3.8-live)  |  | (timbre-v3.0)    |  | (prisma-v3.0)    |
         +--------------------+  +------------------+  +------------------+
```

---

## 3. Strict Engineering Constraints & Rules
1. **Frontend Stack**: Strictly React + Vite + plain JavaScript (`.jsx` / `.js`). No TypeScript.
2. **Backend Stack**: Strictly Python + FastAPI + Uvicorn.
3. **No Heavy Framework Abstractions**: No Next.js, Docker, relational databases (PostgreSQL/MySQL), Redis, LangChain, or complex multi-agent frameworks.
4. **Secret Hygiene**: All API keys (`GEMINI_API_KEY`, `GNANI_API_KEY`) must remain strictly server-side in `backend/.env`. Never bundle keys into frontend builds, never expose keys in client responses, and never print raw keys in logs or CLI outputs.
5. **Incremental Milestone Execution**: Work on ONE milestone at a time. Do not jump ahead until the current milestone is verified and logged.

---

## 4. Multilingual & Indic Voice Capabilities
- **TTS Engine**: Gnani Timbre v3.0 (`https://api.vachana.ai/api/v1/tts/inference`)
  - Target Languages: `kn-IN` (Kannada), `hi-IN` (Hindi), `ta-IN` (Tamil), `te-IN` (Telugu), `en-IN` (Indian English).
  - Audio Config: 48,000 Hz, 1 channel (mono), 16-bit linear PCM WAV.
- **STT Engine**: Gnani Prisma v3.0 (`https://api.vachana.ai/stt/v3`)
  - Language Code: `indic-auto` or specific locale code.
  - Multi-part WAV audio upload for low-latency transcription.

---

## 5. Gemini Live Multimodal Engine
- **Model**: `gemini-3.8-live` via `google-genai` SDK (`client.aio.live.connect`).
- **Response Modalities**: Real-time text and speech feedback.
- **Visual Ingestion**: Periodic canvas snapshots (JPEG/PNG) transmitted over live WebSocket session so the tutor perceives what the student writes or sketches in real time.

---

## 6. Deterministic Mathematical Verification (SymPy)
- AI models can hallucinate math solutions. To maintain academic precision, step-by-step math evaluation passes through SymPy CAS (Computer Algebra System).
- When a student completes an equation on the whiteboard, the expression is parsed and verified for formal equivalence against ground truth before pedagogical feedback is generated.

---

## 7. Milestone Roadmap (6-Hour MVP)
- **Milestone 1 (0:00–0:30)**: Skeleton + Provider Connectivity Checks (Completed first).
- **Milestone 2 (0:30–1:30)**: Whiteboard UI & Canvas State Management (Completed).
- **Milestone 3 (1:30–2:30)**: Gemini Live Tutor Session, Session Manager & `/api/tutor/turn` (Completed).
- **Milestone 4 (2:30–3:45)**: Gnani Voice Pipeline (Prisma STT + Timbre TTS).
- **Milestone 5 (3:45–4:45)**: SymPy Deterministic Verification & Socratic Feedback Engine.
- **Milestone 6 (4:45–6:00)**: End-to-End Multilingual Integration, Demo Scenarios, Polish & Hardening.

---

## 7A. Section 7A: End-to-End Voice Flow
The complete voice interaction pipeline consists of 6 discrete stages:
1. **Audio Capture**: The student clicks the microphone button (or press-to-talk). Status pill displays `Listening`. Audio is recorded via `navigator.mediaDevices.getUserMedia`. A 25-second client-side hard cap is enforced (staying safely below Gnani's 30s limit).
2. **Client-Side WAV Encoding**: Upon stop, the Web Audio API (`AudioContext` / `OfflineAudioContext`) converts the recorded float buffer into standard 16kHz 16-bit mono PCM `.wav` (`audio/wav`), eliminating unsupported `audio/webm` browser formats.
3. **STT Transcription**: The WAV blob is uploaded to `POST /api/voice/transcribe`. Status pill displays `Transcribing`. Gnani Prisma v3.0 transcribes the speech and returns `{ "transcript": "...", "detected_language_code": "..." }`.
4. **Tutor Turn Execution**: The transcript populates the input field and immediately fires `POST /api/tutor/turn` with the text, the detected Indic language code (carried forward if `indic-auto` was active), and the current whiteboard snapshot.
5. **TTS Speech Synthesis**: As soon as `/api/tutor/turn` returns the tutor's answer, status pill displays `Speaking` and calls `POST /api/voice/speak` with the cleaned answer text and language code. Gnani Timbre v3.0 synthesizes speech in the matching Indic locale.
6. **Audio Playback**: The resulting WAV stream is played via an HTML5 `Audio` element using a transient Object URL (revoked on completion). Status pill returns to `Ready`. A manual replay button (`🔊 Replay`) is available on every tutor message.

---

## 10. Section 10: Gnani Voice Pipeline & Audio Specifications
- **STT Input Audio Formats**: Gnani Prisma v3.0 REST API natively supports `WAV`, `MP3`, `OGG`, `FLAC`, `AAC`, and `M4A`. Raw browser `audio/webm` is NOT accepted by Gnani REST STT. Browser-side conversion in `frontend/src/utils/audio.js` directly encodes into standard 16-bit mono PCM `.wav` at 16,000 Hz.
- **TTS Output Audio**: Gnani Timbre v3.0 generates 48,000 Hz 16-bit linear PCM WAV (`audio/wav`) audio.
- **Text Normalization**: Bulky Markdown formatting (`**`, `*`, `` ` ``, `#`, latex brackets) is stripped prior to TTS synthesis so equations and explanations are pronounced naturally.
- **Supported Gnani Locales**:
  * `hi-IN` (Hindi)
  * `en-IN` (Indian English)
  * `ta-IN` (Tamil)
  * `te-IN` (Telugu)
  * `kn-IN` (Kannada)
  * `ml-IN` (Malayalam)
  * `mr-IN` (Marathi)
  * `pa-IN` (Punjabi)
  * `bn-IN` (Bengali)
  * `gu-IN` (Gujarati)
- **Script-Based Auto-Detection**: When `indic-auto` or `auto` is passed to TTS, the backend inspects Unicode codepoint ranges in the text (Devanagari, Kannada, Tamil, Telugu, Malayalam, Bengali, Gujarati, Gurmukhi) to resolve the optimal matching Indic voice locale.

---

## 7D. Mathematical Verification & Verdict Rules
All pedagogical feedback emitted by the tutor must classify step soundness under one of five deterministic verdicts:
1. `correct`: The mathematical step is verified equivalent or valid by the SymPy CAS engine.
2. `incorrect`: The step contradicts algebraic rules as proven by SymPy.
3. `partial`: The intermediate reasoning is valid but incomplete.
4. `uncertain`: Assigned when a step check is requested but cannot be deterministically verified (e.g., in Milestone 3 prior to attaching the SymPy engine). Under no circumstances may an unverified step receive a false green `correct` verdict.
5. `not_applicable`: For conversational questions, hints, conceptual analogies, or non-step interactions.

---

## 8. Section 8: Gemini Live System Instruction & Pedagogical Persona

The system instruction passed to `google-genai` Live session initialization (`LiveConnectConfig.system_instruction`) is:

```text
You are an expert, encouraging, Socratic Multilingual Learning Tutor for school students in India.
Your mission is to guide learners to discover answers on their own, never giving away the final answer outright.

Pedagogical Guidelines:
1. Socratic Method: Ask guiding questions. Break complex problems into smaller, manageable steps. Give one small hint at a time.
2. Whiteboard Awareness: Pay close attention to what the student has drawn or written on the whiteboard image. Refer to their handwritten equations, numbers, and diagrams directly.
3. Multilingual Communication: Reply in the student's selected language (or match their spoken/typed language if Auto-detect is chosen). Keep mathematical equations, formulas, and variables in standard international notation (e.g. 2x + 5 = 15, x = 5) so they remain universally readable.
4. Simplicity & Analogies: When asked to explain simply, use intuitive everyday analogies (e.g., fruits, pocket money, balance scales).
5. Mathematical Rigor: Never confirm a student's step as definitively correct unless verified. When unverified, guide them to check their work or test with sample values.
6. Tone: Warm, patient, curious, and respectful. Celebrate effort and curiosity.
```

---

## 11. Section 11: API Error Contracts & Response Formats

All backend API endpoints must return structured JSON error payloads when non-200 responses occur:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description without leaking internal paths or API keys"
  }
}
```

Standard error codes:
- `GEMINI_NOT_CONFIGURED` (HTTP 503): When `GEMINI_API_KEY` is missing or placeholder `replace_me`.
- `IMAGE_TOO_LARGE` (HTTP 400): When base64 payload exceeds 4MB.
- `INVALID_PAYLOAD` (HTTP 400): When malformed JSON or corrupted base64 data is supplied.
- `SESSION_BUSY` (HTTP 429): When a concurrent turn request is sent for the same session before the previous turn completes.
- `PROVIDER_ERROR` (HTTP 502): When upstream Gemini Live raises an unrecoverable network failure.

---

## 7C. Section 7C: PDF Worksheet Ingestion & Document Processing

In addition to the interactive whiteboard canvas, the tutor supports digitizing and discussing printed school worksheets via PDF upload:
1. **File Constraint**: Accepts `.pdf` files up to a strict 15MB limit. Excessively large documents are rejected client-side with user-friendly error guidance before memory consumption occurs.
2. **Local Client-Side Rendering**: Uses `pdfjs-dist` configured with a local Vite worker bundle (`pdf.worker.min.mjs?url`), ensuring 100% offline-resilient rendering without external CDN dependencies or latency.
3. **Responsive Page Navigation**: Renders pages onto an HTML5 `<canvas>` element with high-DPI scaling (`window.devicePixelRatio`), maintaining crisp rendering across mobile and desktop displays. Includes page navigation (`Prev`, `Next`, `Page X of Y`) and zoom controls.
4. **Multimodal Snapshot Export**: When the student asks a question with the PDF mode active (`input_source: "pdf"`), the rendered page canvas is exported as a compressed JPEG data URL (`data:image/jpeg;base64,...`) with an explicit `#FFFFFF` white background and transmitted to `POST /api/tutor/turn`.

---

## 12. Section 12: Developer Handoff & Operation Protocol

The complete system requires minimal dependencies and runs without Docker, databases, or Redis:
1. **Backend**: Python 3.10+ virtual environment in `backend/.venv` running FastAPI + Uvicorn:
   ```bash
   cd backend && python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Frontend**: Vite + React 18 development server proxying `/api` requests to backend port 8000:
   ```bash
   cd frontend && npm install
   npm run dev -- --host 0.0.0.0 --port 5173
   ```
3. **Environment**: All secrets strictly reside in `backend/.env`. Placeholder values (`replace_me`) are handled gracefully with structured HTTP 503 error payloads (`GEMINI_NOT_CONFIGURED` and `GNANI_NOT_CONFIGURED`), allowing offline UI, Whiteboard, PDF, and SymPy CAS development without live cloud credentials.

---

## 14. Section 14: Mobile, Tablet & PWA Specifications

The application is engineered as a mobile-first, installable Progressive Web Application (PWA):
1. **Responsive Viewport**: Configured with `width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover` in `frontend/index.html` to eliminate double-tap zoom delay and support edge-to-edge mobile screens.
2. **Web App Manifest**: Declares `manifest.webmanifest` with `display: "standalone"`, SVG app icons (192x192 and 512x512), theme color `#4f46e5`, and educational categorization.
3. **Touch Action & Gesture Handling**: Whiteboard drawing canvas utilizes `touch-action: none` with normalized coordinate mapping (`[0, 1]`) and passive touch listeners to eliminate scroll interference and ensure fluid finger or stylus writing.
4. **Tap Target Accessibility**: All interactive buttons, toolbar controls, and mode selectors maintain a minimum 44px x 44px tap target area.

---

## 15. Section 15: Three-Minute Live Pitch Demo Walkthrough

The repository includes embedded demo presets in `frontend/src/utils/canvas.js` and `WhiteboardToolbar.jsx` to ensure foolproof live hackathon demonstrations:
1. **Step 1 — Problem Setup (`2x = 8`)**:
   - Presenter clicks `🎯 Demo Presets` -> `Step 1: Problem (2x = 8)`.
   - The whiteboard instantly renders a clean handwritten linear equation `2x = 8`.
   - Presenter clicks `Send` (or speaks: *"How do I solve this equation?"*). Tutor acknowledges the equation.
2. **Step 2 — Student Algebraic Misconception (`x = 8`)**:
   - Presenter clicks `Step 2: Error Step (x = 8)`.
   - The student has incorrectly removed the coefficient 2 from the left side without dividing the right side.
   - Presenter clicks `Check My Work`. SymPy CAS engine evaluates the step and flags it as `incorrect`.
   - Socratic feedback: *"In '2x = 8', you adjusted the coefficient of x by a factor of 2, but did not apply the same operation to the other side. Remember the golden rule of algebra: divide both sides by 2."*
   - Badge displays red `Incorrect Step` with explanatory diagnostic.
3. **Step 3 — Correct Ground Truth Verification (`x = 4`)**:
   - Presenter clicks `Step 3: Correct Step (x = 4)`.
   - Presenter clicks `Check My Work`. SymPy CAS engine verifies $x = 4$ ground truth equivalence.
   - Badge displays green `Step Verified Correct`.
   - Gnani Timbre TTS synthesizes encouraging spoken congratulations in the selected Indic language.
4. **Step 4 — PDF Worksheet or Science Versatility**:
   - Switch to `📄 PDF Worksheet` mode and navigate sample math worksheet, or load `Science: Gravity & Mass` demo preset to showcase multimodal STEM tutoring beyond algebra.

---

## 16. Section 16: Security Audit & Secret Hygiene Protocol

1. **Zero Client Secrets**: The `frontend/` directory and generated `frontend/dist/` production bundles contain zero API keys, secrets, or credential tokens.
2. **Safe CAS Evaluation**: Student equations are parsed strictly using SymPy's AST parser `sympy.parsing.sympy_parser.parse_expr` with disabled builtins (`{"__builtins__": None}`) and a strict character whitelist (`[a-zA-Z0-9+\-*/=^().\s]`). Python `eval` or `exec` is strictly forbidden.
3. **Secret Isolation in Version Control**: `.env` and `backend/.env` are strictly excluded in `.gitignore`. CI/CD and pre-commit checks run automated regex scans against key patterns.

---

## 17. Section 17: Remote Android HTTPS Mobile Testing (Tunnels)

To test the mobile experience and voice recording on physical Android or iOS devices, HTTPS is mandatory for browser `navigator.mediaDevices.getUserMedia` permissions:
1. **Option A: Cloudflare Quick Tunnel** (Free, no account needed):
   ```bash
   cloudflared tunnel --url http://localhost:5173
   ```
2. **Option B: ngrok**:
   ```bash
   ngrok http 5173
   ```
3. Scan the generated HTTPS URL on your phone to test the touch canvas, voice capture, and responsive UI in real-world mobile environments.

---

## 18. Section 18: Build Log Template & Change Tracking Protocol

All incremental milestones, architectural decisions, and verification results must be logged in `BUILD_LOG.md` following this exact template structure:

```markdown
# BUILD LOG — Agentic Multilingual Learning Tutor

## Milestone [N]: [Milestone Title]
- **Date / Timestamp**: YYYY-MM-DD HH:MM:SS (Timezone)
- **Status**: [IN_PROGRESS | VERIFIED | BLOCKED]
- **Goal / Scope**: Brief description of the milestone objectives.

### Files Created / Modified
- `path/to/file1` — Purpose
- `path/to/file2` — Purpose

### Verification & Testing
- **Commands Executed**:
  ```bash
  command 1
  command 2
  ```
- **Observed Outputs / Results**:
  - Description or code block of output

### Provider Status
- **Gemini Live (`gemini-3.8-live`)**: [Configured / Pending Key / Live Verified / Error]
- **Gnani Timbre TTS (`timbre-v3.0`)**: [Configured / Pending Key / Live Verified / Error]
- **Gnani Prisma STT (`prisma-v3.0`)**: [Configured / Pending Key / Live Verified / Error]

### Decisions & Blockers
- Architectural decisions or deviations taken during this step.
- Current blockers or items pending user action.

### Next Single Task
- Milestone [N+1]: [Next Title]
```

