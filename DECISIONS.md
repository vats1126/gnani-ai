# Architectural & Technical Decisions (DECISIONS.md)

## ADR 001: Pure React + Vite + Plain JavaScript (No TypeScript)
- **Context**: Rapid hackathon MVP delivery with minimal compilation overhead and clean developer ergonomics.
- **Decision**: Frontend is built using pure JavaScript (`.jsx` / `.js`) with Vite. TypeScript is strictly avoided to eliminate build-step type mismatches and reduce iteration friction.
- **Consequences**: Fast Hot Module Replacement (HMR), straightforward component composition, zero TS transpilation errors.

## ADR 002: Python + FastAPI Backend Core
- **Context**: Need high-performance async concurrency for Gemini Live SDK (`client.aio.live.connect`), streaming audio, and integration with the SymPy Computer Algebra System.
- **Decision**: Python 3.10+ with FastAPI and Uvicorn.
- **Consequences**: Native support for `google-genai` async client, direct in-process SymPy algebraic computation, and standardized OpenAPI schemas.

## ADR 003: Server-Side Secret Management via `backend/.env`
- **Context**: Security hygiene demands that `GEMINI_API_KEY` and `GNANI_API_KEY` never reach the browser bundle or client requests.
- **Decision**: Secrets are strictly housed in `backend/.env` (git-ignored) and accessed only within FastAPI server services.
- **Consequences**: Zero risk of API credential leakage to the frontend or git history. The health check endpoint exposes boolean flags (`gemini_configured`, `gnani_configured`) without revealing the secret strings or fragments.

## ADR 004: Vite Reverse Proxy for Development
- **Context**: Prevent CORS issues in local development when React runs on port 5173 and FastAPI runs on port 8000.
- **Decision**: Vite dev server proxies `/api` requests directly to `http://127.0.0.1:8000`.
- **Consequences**: The frontend code makes clean relative requests to `/api/*` without hardcoding hostnames, while CORS middleware in FastAPI provides defence-in-depth.

## ADR 005: Standalone Provider Verification Script
- **Context**: Need to verify live API access to Google Gemini Live and Gnani Voice APIs without requiring a full end-to-end UI loop.
- **Decision**: Implement `backend/check_providers.py` as an async CLI test tool that checks Gemini Live, Gnani Timbre TTS, and Gnani Prisma STT independently and reports exact statuses.

## ADR 006: Normalized Stroke Representation & High-DPI Canvas Rendering
- **Context**: Students write equations on phones, tablets, and laptops. Resizing windows or changing device orientation would normally wipe or distort raw canvas pixels.
- **Decision**: Whiteboard strokes store coordinates as normalized floats in `[0, 1]` relative to canvas width/height. A `ResizeObserver` re-renders strokes on the fly with High-DPI (`window.devicePixelRatio`) scaling. Snapshots for multimodal AI vision are rendered onto an offscreen canvas with solid white paper background to eliminate black-background JPEG compression artifacts.
- **Consequences**: Zero stroke loss during responsive resize; crisp rendering on Retina screens; clean OCR-ready JPEG payload for Gemini Live vision.

## ADR 007: Gemini Live Session State & Transparent WebSocket Reconnection
- **Context**: Gemini Live operates over persistent bidirectional WebSockets. WebSockets can disconnect due to network jitter or timeouts during multi-turn study sessions.
- **Decision**: An in-memory `SessionManager` tracks each student's `session_id`, manages an `asyncio.Lock` per session to prevent race conditions, and caps a rolling history of recent turns. If a Live WebSocket drops mid-turn, the backend transparently establishes a fresh Live session and injects the conversational history summary, ensuring continuous Socratic dialogue without user disruption.
- **Consequences**: Resilient conversational continuity, protection against race conditions, and automatic session cleanup without external database dependencies.

## ADR 008: Client-Side 16kHz PCM WAV Audio Encoding & Script-Based Voice Locale Resolution
- **Context**: Gnani Prisma v3.0 REST STT requires supported audio container formats (`WAV`, `MP3`, `OGG`, `FLAC`, etc.) and rejects raw browser `audio/webm`. Additionally, students asking questions in `indic-auto` or mixed Indic scripts need natural TTS vocal responses in the matching Indic locale without manual switching.
- **Decision**:
  1. The browser (`frontend/src/utils/audio.js`) records audio and resamples it via `OfflineAudioContext` directly into standard 16-bit mono PCM WAV (`audio/wav`) at 16,000 Hz, eliminating external server-side FFmpeg transcoding requirements and ensuring universal compatibility across Chrome, Safari, and Android.
  2. The backend (`backend/app/services/gnani_tts.py`) implements Unicode codepoint inspection (`detect_script_locale`) to identify Devanagari (`hi-IN`), Kannada (`kn-IN`), Tamil (`ta-IN`), Telugu (`te-IN`), Malayalam (`ml-IN`), Bengali (`bn-IN`), Gujarati (`gu-IN`), Gurmukhi (`pa-IN`), or Latin (`en-IN`), automatically mapping `indic-auto` into an explicit Gnani locale for Timbre TTS.
  3. Text normalization (`clean_text_for_speech`) strips Markdown asterisks, backticks, headings, and LaTeX delimiters so the speech engine reads natural words without spelling out formatting punctuation.
- **Consequences**: Fast, robust speech synthesis and recognition across all devices; seamless multilingual conversation without requiring students to constantly toggle language settings.

## ADR 009: Deterministic SymPy CAS Verification & Socratic Step Evaluation
- **Context**: LLMs, including multimodal models, can hallucinate algebraic solutions or mistakenly validate student steps that contradict algebraic equivalence. Academic precision requires a formal Computer Algebra System (CAS) to ground step-by-step verification. At the same time, executing arbitrary user math strings poses code-injection risks.
- **Decision**:
  1. Input strings are sanitized against a strict regex allowlist (`^[0-9a-zA-Z_+\-*/^=().,\s]+$`), normalized for unicode math characters, and checked for forbidden keywords (`__`, `import`, `eval`, `system`, etc.).
  2. Expressions are parsed safely using `sympy.parsing.sympy_parser.parse_expr` with disabled builtins and explicit symbol scope. Python's `eval()` is strictly prohibited.
  3. Linear equations are solved via `sympy.solveset` and compared for solution set equality. Trivial tautologies (e.g. `0 = 0`, `x = x`) are rejected as `uncertain`.
  4. Step evaluation distinguishes intermediate steps (generating Socratic hints like "divide both sides by 2" without giving away the final value) from solved steps, and diagnoses common errors (dividing only one side, sign errors across `=`).
  5. The verifier is exposed to Gemini Live as a registered function declaration (`verify_equation_step`), allowing Gemini to request formal verification and synthesize culturally warm Socratic explanations. Direct HTTP routes (`/api/tools/verify-step`) allow independent testing and client fallback.
- **Consequences**: Provably sound mathematical feedback; zero false-positive green badges; complete safety against code injection; highly pedagogical Socratic hints.

## ADR 010: PDF.js Client-Side Worksheet Ingestion, Mobile PWA Shell & Pitch Demo Presets
- **Context**:
  1. Students frequently learn from printed school worksheets and textbook pages (PDF format) in addition to freehand whiteboard drawing.
  2. Mobile testing on physical Android and iOS devices requires PWA responsiveness, fluid touch drawing gestures, and HTTPS tunnels for browser microphone permissions.
  3. Live hackathon pitch demonstrations require deterministic, jitter-free problem loading under tight 3-minute time constraints.
- **Decision**:
  1. Integrated `pdfjs-dist` with Vite local worker asset bundling (`pdf.worker.min.mjs?url`) to achieve 100% offline-capable, CDN-free PDF rendering. Pages are rendered onto high-DPI HTML5 canvas with pagination and zoom controls, and exported as compressed JPEG snapshots with solid `#FFFFFF` backgrounds for Gemini Live visual ingestion (`input_source: "pdf"`). A 15MB file size cap is enforced client-side.
  2. Added Web App Manifest (`manifest.webmanifest`), SVG icons (192x192, 512x512), mobile viewport optimization (`viewport-fit=cover`, `maximum-scale=1.0`), and 44px+ tap targets for full mobile and tablet ergonomics.
  3. Added `DEMO_PRESETS` in `frontend/src/utils/canvas.js` (`step1_problem`: 2x=8, `step2_error`: x=8, `step3_correct`: x=4, `science_gravity`: mass & gravity diagram) accessible via a toolbar dropdown, ensuring flawless, fast live pitch demonstrations.
- **Consequences**:
  1. Dual-mode visual workspace supporting both freehand drawing and scanned worksheet PDFs.
  2. Installable PWA experience with responsive layout for phones, tablets, and desktops.
  3. Completely reliable, rapid live demo flow for judges and evaluators without trackpad drawing errors.

## ADR 011: Multi-Tier Resilient Gemini Cascade, Gnani LRU Caching & Vercel Serverless Architecture
- **Context**:
  1. Hackathon Google AI Studio API keys frequently face quota limits (`429 Resource Exhausted`), WebSocket disconnects, or model availability differences between Live and standard APIs.
  2. Repeated TTS calls during demo rehearsals burn cloud audio credits unnecessarily.
  3. Vercel deployment requires serverless function compatibility (`api/index.py`), cold-start stateless session hydration, and flexible API base URL support (`VITE_API_BASE_URL`).
- **Decision**:
  1. **3-Tier Gemini Execution Cascade**:
     - *Tier 1*: Live WebSocket session (`gemini-3.8-live` with fallback to `gemini-2.0-flash-live-001`).
     - *Tier 2*: Multimodal `generate_content` fallback (`gemini-2.5-flash` $\rightarrow$ `gemini-2.0-flash`) with full tool execution.
     - *Tier 3*: Emergency Local Rescue: Offline SymPy CAS verification and localized Socratic response synthesis in Indic locales (`hi-IN`, `kn-IN`, `ta-IN`, `te-IN`, `en-IN`), returning HTTP 200 with `fallback_mode=True` without crashing.
  2. **Gnani TTS In-Memory LRU Cache & Browser Fallback**:
     - Backend LRU cache (up to 64 items) stores synthesized WAV bytes, returning repeated phrases in 0ms without hitting the network.
     - Frontend caches audio blobs and falls back to native `window.speechSynthesis` if cloud voice rate limits occur.
  3. **Vercel Serverless Deployment**:
     - Created `api/index.py` mounting FastAPI `app` with sys.path isolation.
     - Added `vercel.json` routing `/api/(.*)` to `api/index.py` and SPA fallback to `index.html`.
     - Added stateless `history` parameter to `TutorTurnRequest` for hydrating cold serverless function instances.
- **Consequences**:
  1. Zero demo crashes under live rate-limits or network drops.
  2. Quota-efficient audio synthesis with instant local replays.
  3. Single-command or git-push deployment to Vercel with zero architectural friction.

## ADR 012: Unified Two-Layer Whiteboard with PDF Underlay, Dual-Engine Multilingual TTS Cascade, and Mathematical Speech Normalization
- **Context**:
  1. Previously, digital whiteboard drawing and PDF worksheet viewing were isolated into separate components, preventing students from annotating, highlighting, or working out math problems directly on top of school worksheets.
  2. Erasing previously painted over the canvas with solid beige, corrupting underlying worksheet diagrams or coordinate grids.
  3. Mathematical equations (e.g. `2x + 5 = 15`, `\frac{1}{2}`, `x^2`, `\sqrt{16}`) were read aloud raw or garbled by speech engines, without localized Indic words for operators.
  4. Relying solely on Gnani Timbre for cloud TTS created a single point of failure with no secondary neural cloud fallback.
- **Decision**:
  1. **Two-Layer Stacked Canvas Architecture**:
     - *Layer 0 (`bgCanvasRef`)*: High-DPI underlay rendering selectable paper backgrounds (24px Math Grid, Ruled Notebook, Plain Paper) or PDF pages via `pdfjs-dist`.
     - *Layer 1 (`inkCanvasRef`)*: Transparent overlay capturing pointer events for fluid drawing, highlighters (`globalAlpha = 0.35`), and inline text/equation annotations (`T`).
     - *Layer-Safe Eraser*: Uses `ctx.globalCompositeOperation = 'destination-out'` to punch transparent holes on Layer 1 without touching Layer 0.
     - *Spline Smoothing*: Midpoint quadratic Bezier curve interpolation with velocity-aware stroke dynamics.
     - *Per-Page Annotation Memory*: Maintains isolated strokes, text annotations, and undo/redo stacks keyed by page number (`page_1`, `page_2`, ...) or `'board'`.
     - *Composite Snapshot Export*: Renders solid white `#FFFFFF` base, Layer 0, and Layer 1 onto an offscreen canvas (max 1400px, JPEG quality 0.85).
  2. **Mathematical Speech Normalization (`verbalize_math_for_speech`)**:
     - Localizes algebraic operators (`+`, `-`, `*`, `/`, `=`, `^2`, `\sqrt{}`, `\frac{}{}`) across `en-IN`, `hi-IN`, `kn-IN`, `ta-IN`, and `te-IN`.
     - Disambiguates negative numbers and minus signs from natural hyphenated words (e.g., preserving `step-by-step`).
     - Strips markdown, headings, bullets, and LaTeX delimiters, formatting speech into 1–4 conversational sentences.
  3. **Dual Cloud Neural TTS Pipeline & Standard PCM-to-WAV Wrapping**:
     - *Primary*: Gnani Timbre v3.0 (48kHz mono WAV).
     - *Secondary Fallback*: Gemini Native Audio TTS via `google-genai` Live audio modality, wrapped in standard 44-byte RIFF WAV using Python's standard `wave` module.
     - *Tertiary Fallback*: Browser Web Speech API filtering for Natural/Google/Neural voices with rate 0.96 and pitch 1.0.
- **Consequences**:
  - Seamless unified canvas experience where students annotate directly over worksheets or coordinate grids.
  - Zero background erasure discoloration.
  - Clear, natural, culturally authentic mathematical speech in Indian English, Hindi, Kannada, Tamil, and Telugu with complete multi-tier cloud and offline fallback resilience.





