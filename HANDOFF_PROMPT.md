# AI Handoff Prompt & Context Summary

> **Single Source of Truth**: This document provides an exhaustive, instant context summary for any incoming AI agent or senior engineer continuing work on the **Agentic Multilingual Learning Tutor MVP**.

---

## 1. Project Overview & Architecture

The **Agentic Multilingual Learning Tutor** is an interactive, voice-first, multimodal educational assistant designed for multilingual students across India. It integrates:
- **Visual Ingestion**: Real-time responsive HTML5 Whiteboard with normalized coordinate strokes (`[0, 1]`) and High-DPI canvas rendering, plus a native browser PDF Worksheet Viewer (`pdfjs-dist`).
- **Low-Latency Conversational AI**: Google Gemini Live (`gemini-3.8-live`) via the `google-genai` SDK over bidirectional WebSockets, equipped with tool calling and automatic reconnection recovery.
- **High-Fidelity Indic Speech**: Gnani Timbre TTS v3.0 (speech synthesis in 10 Indic locales with Unicode script auto-detection) and Gnani Prisma STT v3.0 (speech-to-text using client-side 16kHz mono PCM WAV encoding).
- **Deterministic Math Verification**: SymPy CAS engine (`verify_equation_step`) to strictly eliminate LLM math hallucinations. Green `correct` verdicts are issued **only** when verified equivalent by SymPy CAS.

### Technology Stack:
- **Frontend**: React 18 + Vite + plain JavaScript (`.jsx` / `.js`). Strictly **no TypeScript**.
- **Backend**: Python 3.10+ + FastAPI + Uvicorn + SymPy.
- **Audio**: Web Audio API (`AudioContext` / `OfflineAudioContext`) encoding directly to 16kHz 16-bit mono PCM `.wav` (`audio/wav`) in the browser.
- **PWA**: Standalone web app manifest (`manifest.webmanifest`) with touch-action protection for mobile phones and tablets.

---

## 2. Security & Secret Hygiene Rules

- **Zero Client-Side Secrets**: `GEMINI_API_KEY` and `GNANI_API_KEY` are stored strictly in `backend/.env` (git-ignored) and never exposed or logged.
- **Graceful Fallbacks**: When API keys are placeholders (`replace_me`), all endpoints return structured HTTP 503 (`GEMINI_NOT_CONFIGURED` / `GNANI_NOT_CONFIGURED`) with helpful UI notices. SymPy CAS verification and practice generation operate 100% locally and offline without external dependencies.
- **No Python `eval()`**: All math parsing passes through `sympy_parser.parse_expr` with disabled builtins, strict regex allowlists, and variable scope restrictions.

---

## 3. Repository Structure & Key Files

```
├── PROJECT_ARCHITECTURE.md     # Single source of truth for specs, contracts & demo scripts
├── BUILD_LOG.md                # Chronological milestone log (M1 through M6 verified)
├── DECISIONS.md                # Architectural Decision Records (ADR 001 - 010)
├── HANDOFF_PROMPT.md           # This handoff file
├── README.md                   # Setup guide, HTTPS mobile tunnel guide & demo checklist
├── .env.example                # Sample environment variables template
│
├── backend/
│   ├── .env                    # Real server-side keys (never commit)
│   ├── check_providers.py      # Standalone provider CLI check script
│   ├── requirements.txt        # FastAPI, google-genai, sympy, httpx, uvicorn
│   ├── test_milestone3.py      # Automated tests for Live session manager & turns
│   ├── test_milestone4.py      # Automated tests for Gnani voice pipeline
│   ├── test_milestone5.py      # Automated tests for SymPy math verifier & tool calling
│   ├── test_milestone6.py      # Automated tests for PDF, Science & full demo flow
│   └── app/
│       ├── config.py           # Pydantic settings loading from backend/.env
│       ├── main.py             # FastAPI app mounting routers & CORS
│       ├── schemas.py          # Pydantic validation schemas & error models
│       ├── routes/
│       │   ├── health.py       # GET /api/health
│       │   ├── whiteboard.py   # POST /api/whiteboard/snapshot
│       │   ├── tutor.py        # POST /api/tutor/turn, POST /api/tutor/reset
│       │   ├── voice.py        # POST /api/voice/transcribe, POST /api/voice/speak
│       │   └── tools.py        # POST /api/tools/verify-step, POST /api/tools/practice-question
│       ├── services/
│       │   ├── session_manager.py # In-memory session tracking & asyncio locks
│       │   ├── gemini_live.py     # Gemini Live multimodal relay & tool loop
│       │   ├── gnani_stt.py       # Prisma STT v3.0 REST client
│       │   └── gnani_tts.py       # Timbre TTS v3.0 REST client & script detector
│       └── tools/
│           ├── math_verifier.py   # Safe SymPy CAS verifier (verify_equation_step)
│           └── practice_generator.py # Practice problem generator
│
└── frontend/
    ├── package.json
    ├── vite.config.js          # Proxies /api -> http://127.0.0.1:8000
    ├── index.html              # PWA meta tags & manifest link
    ├── public/
    │   ├── manifest.webmanifest# PWA manifest
    │   ├── favicon.svg         # App favicon
    │   ├── icon-192.svg        # 192px app icon
    │   └── icon-512.svg        # 512px app icon
    └── src/
        ├── App.jsx             # Master workspace, voice loop & turn coordinator
        ├── index.css           # Responsive paper whiteboard & accessible typography
        ├── components/
        │   ├── Header.jsx           # Subject & workspace mode toggle, status pill, new session
        │   ├── Whiteboard.jsx       # HTML5 canvas, pointer capture, snapshot export
        │   ├── WhiteboardToolbar.jsx# Pen, eraser, palette, stroke width, Demo Presets menu
        │   ├── PdfViewer.jsx        # PDF.js worksheet viewer, 15MB limit, page controls
        │   ├── TutorPanel.jsx       # Chat history, quick chips, feedback badge, voice controls
        │   ├── FeedbackBadge.jsx    # Green correct / Red incorrect / Amber uncertain badges
        │   ├── LanguageSelector.jsx # 10 Indic locales + indic-auto dropdown
        │   └── VoiceButton.jsx      # 48px mic button with 25s limit & live timer
        ├── services/
        │   └── api.js          # Client API calls (turns, voice, tools, health)
        └── utils/
            ├── audio.js        # AudioRecorder, 16kHz PCM WAV encoder, player
            ├── canvas.js       # Normalized stroke math, redrawCanvas, DEMO_PRESETS
            └── samplePdf.js    # Embedded sample math worksheet for instant testing
```

---

## 4. How to Run Locally

### Start Backend (Port 8000)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start Frontend (Port 5173)
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Run All Automated Verification Test Suites
```bash
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone3.py
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone4.py
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone5.py
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone6.py
npm --prefix frontend run build
```

---

## 5. Live Pitch Demo Walkthrough (Section 15)

1. Open `http://localhost:5173`.
2. Select language (e.g. `Hindi`, `Kannada`, `English`).
3. Click `🎯 Demo Presets` in the whiteboard toolbar:
   - **Step 1**: Click `Step 1: Problem (2x = 8)` -> Board renders `2x = 8`. Click **Ask Tutor** or press the mic button. Tutor provides Socratic guiding question.
   - **Step 2 (Error Detection)**: Click `Step 2: Error Step (x = 8)` -> Board renders line 2 `x = 8`. Click **Check Work**. SymPy CAS flags red `incorrect` badge: *"In '2x = 8', you adjusted the coefficient of x by a factor of 2, but did not apply the same operation to the other side. Divide both sides by 2."*
   - **Step 3 (Corrected Work)**: Click `Step 3: Correct Step (x = 4)` -> Board renders line 2 `x = 4`. Click **Check Work**. SymPy CAS confirms green `correct` badge: *"Step is correct! The variable 'x' is isolated and solved: x = 4."*
4. Click `📄 PDF Worksheet` (in header or bottom bar) -> Click `⚡ Load Sample Math Worksheet` -> PDF page renders with zoom and page controls.

