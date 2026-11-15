# 🎓 Agentic Multilingual Learning Tutor

<div align="center">

![Agentic Tutor Banner](https://img.shields.io/badge/Project-Agentic%20Multilingual%20Tutor-blueviolet?style=for-the-badge&logo=google)
![Gemini Live](https://img.shields.io/badge/Google-Gemini%20Live%203.8-4285F4?style=for-the-badge&logo=google)
![Gnani.ai](https://img.shields.io/badge/Gnani.ai-Timbre%20%7C%20Prisma%20v3-00C853?style=for-the-badge)
![SymPy CAS](https://img.shields.io/badge/CAS-SymPy%20Deterministic%20Verification-F57C00?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Complete%20%26%20Production%20Ready-success?style=for-the-badge)

<br/>

> **"Bridging India's STEM learning gap with voice-first Socratic AI, native Indic languages, real-time multimodal whiteboarding, and deterministic mathematical verification."**

</div>

---

## 🏆 Hackathon Submission & Judges Showcase

> [!IMPORTANT]
> **Quick Access Links for Hackathon Evaluators:**
> - 🎥 **Video Demo Walkthrough**: **[▶ Watch Video Submission (Google Drive)](https://drive.google.com/file/d/1C_P8EGqbkLXghm2vVgrkLuYWwY1W7SwU/view?usp=sharing)**
> - 📊 **Pitch Deck (Presentation Slides)**: **[📑 View Pitch Deck (Google Drive)](https://drive.google.com/file/d/1d4hk98USki2EsIRgpDy74Vs4_lNGWvMB/view?usp=sharing)**
> - 🚀 **Live Production Deployment**: **[https://gnani-ai-gnzb.vercel.app/](https://gnani-ai-gnzb.vercel.app/)**
> - 📑 **Full Submission Hub & Evaluation Rubrics**: **[Read SUBMISSION.md](SUBMISSION.md)**
> - 💻 **GitHub Repository**: **[https://github.com/vats1126/gnani-ai](https://github.com/vats1126/gnani-ai)**
> - 🌐 **Local Web Application**: `http://localhost:5173` | **FastAPI Backend**: `http://127.0.0.1:8000`

---

An interactive, voice-first, multimodal educational assistant designed for multilingual school students across India. Powered by **Google Gemini Live** (`gemini-3.8-live`), **Gnani Voice APIs** (Timbre TTS & Prisma STT), **SymPy mathematical CAS verification**, an interactive **digital whiteboard**, and a **PDF worksheet viewer**.

---

## 🚀 Key Features

1. **Multimodal Whiteboard & PDF Viewer**:
   - Draw equations, diagrams, and formulas with mouse, finger, or stylus using high-DPI normalized coordinate strokes.
   - Upload and inspect PDF worksheets (up to 15MB) with full page navigation, zoom controls, and instant visual snapshot export for AI vision.
   - Built-in `🎯 Demo Presets` menu for instant live pitch demonstration.

2. **Indic Voice Pipeline (Gnani.ai)**:
   - **Prisma STT v3.0**: Browser-side 16kHz mono PCM WAV encoding ensures universal speech-to-text compatibility across Chrome, Safari, and Android.
   - **Timbre TTS v3.0**: Natural speech synthesis in 10 Indic locales (`kn-IN`, `hi-IN`, `ta-IN`, `te-IN`, `en-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `bn-IN`, `gu-IN`) with automatic Unicode script detection.

3. **Deterministic Mathematical Verification (SymPy CAS)**:
   - Evaluates algebraic step equivalence without ever using Python `eval()`.
   - Diagnoses algebraic mistakes (e.g. dividing only one side, sign errors) and provides Socratic hints without giving away final answers.
   - Strict verdict rules: green `correct` badges are granted **only** when verified by CAS.

4. **Conversational Socratic AI (Google Gemini Live)**:
   - Real-time bidirectional WebSocket dialogue with visual whiteboard awareness.
   - Native tool calling with automatic session reconnection and history injection.

---

## 🛠️ Prerequisites

- **Node.js** v18+ and **npm** v9+
- **Python** 3.10+
- Valid API keys placed in `backend/.env`:
  - `GEMINI_API_KEY`: Google Gemini API Key
  - `GNANI_API_KEY`: Gnani.ai API Key (`X-API-Key-ID` for Vachana AI)

---

## ⚡ Quickstart Setup

### 1. Environment Configuration
Copy `.env.example` to `backend/.env`:
```bash
cp .env.example backend/.env
```
Edit `backend/.env` with your real keys:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_LIVE_MODEL=gemini-3.8-live
GNANI_API_KEY=your_actual_gnani_api_key_here
FRONTEND_ORIGIN=http://localhost:5173
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Health endpoint will be accessible at: `http://127.0.0.1:8000/api/health`

### 3. Frontend Setup
In a separate terminal:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```
Frontend will be accessible at: `http://localhost:5173`

---

## 📱 Remote Android Phone HTTPS Testing (Section 17)

Mobile browsers (Chrome on Android, Safari on iOS) require a secure origin (**HTTPS** or `localhost`) to grant microphone access (`navigator.mediaDevices.getUserMedia`). 

To test voice interactions on a physical smartphone:

### Option A: Cloudflare Tunnel (Free, No Account Required)
```bash
# In a new terminal window:
cloudflared tunnel --url http://localhost:5173
```
Copy the generated `https://<random-subdomain>.trycloudflare.com` URL into Chrome on your Android phone.

### Option B: ngrok
```bash
ngrok http 5173
```
Open the generated HTTPS forwarding URL on your mobile phone.

### Option C: Android Chrome Port Forwarding via USB
1. Connect Android phone via USB with USB Debugging enabled.
2. In desktop Chrome, open `chrome://inspect/#devices`.
3. Set Port Forwarding: Port `5173` -> `localhost:5173`.
4. On phone Chrome, navigate to `http://localhost:5173` (treated as secure origin).

---

## ⏱️ 3-Minute Live Hackathon Pitch Checklist (Section 15)

| Time | Script & Action | Expected Outcome |
| :--- | :--- | :--- |
| **0:00 - 0:45** | **Problem Intro**: State multilingual STEM learning challenges in tier-2/3 India. Select `Hindi` or `Kannada` in the top header. Click `🎯 Demo Presets` -> `Step 1: Problem (2x = 8)`. Click the mic button and ask in Indic voice how to start. | Tutor acknowledges handwritten problem on canvas and responds with a warm, encouraging Socratic guiding question. |
| **0:45 - 1:45** | **Error Detection**: Click `Step 2: Error Step (x = 8)` (simulating student dividing left by 2 but forgetting right). Click `🔍 Check work`. | SymPy CAS flags red `incorrect` badge: *"In '2x = 8', you adjusted the coefficient of x by a factor of 2, but did not apply the same operation to the other side. Divide both sides by 2."* |
| **1:45 - 2:30** | **Corrected Step**: Click `Step 3: Correct Step (x = 4)`. Click `🔍 Check work`. | SymPy CAS confirms green `correct` badge: *"Step is correct! The variable 'x' is isolated and solved: x = 4."* Tutor congratulates student via Indic voice. |
| **2:30 - 3:00** | **Worksheet / Science Expansion**: Click `📄 PDF Worksheet` -> `⚡ Load Sample Math Worksheet` to showcase textbook chapter ingestion. Switch Subject to `🔬 Science` for conceptual guidance. | Demonstrates end-to-end multimodal capability across math equations, PDF worksheets, and science concepts. |

---

## ☁️ Vercel Serverless Deployment (Milestone 7)

The repository is pre-configured for seamless unified deployment to **Vercel** as a full-stack application (Vite SPA + Python Serverless Functions):

### 1. Push to GitHub
Ensure all code is committed and pushed to your GitHub repository:
```bash
git push origin master
```

### 2. Deploy on Vercel
1. Log into [vercel.com](https://vercel.com) and click **"Add New..."** -> **"Project"**.
2. Import your GitHub repository.
3. In **Build and Output Settings**, Vercel will automatically read `vercel.json`:
   - **Framework Preset**: Vite
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Output Directory**: `frontend/dist`
4. In **Environment Variables**, add:
   | Variable | Value | Description |
   | :--- | :--- | :--- |
   | `GEMINI_API_KEY` | `your_actual_key` | Google AI Studio Gemini API Key |
   | `GEMINI_LIVE_MODEL` | `gemini-3.8-live` | Target Live model (auto-falls back if needed) |
   | `GNANI_API_KEY` | `your_actual_key` | Gnani.ai / Vachana API Key |
   | `GNANI_TTS_VOICE` | `default` | Optional voice name (defaults to account standard) |
5. Click **Deploy**. Vercel will install Python dependencies from root `requirements.txt`, bundle the React frontend, and serve `/api/*` via `api/index.py`.

---

## 🧪 Automated Test Verification

Run all test suites across the stack:
```bash
# Milestone 3: Live session manager, locking, turns
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone3.py

# Milestone 4: Gnani voice pipeline (Prisma STT + Timbre TTS)
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone4.py

# Milestone 5: SymPy CAS verifier & tool calling
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone5.py

# Milestone 6: PDF, Science & full demo verification
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone6.py

# Milestone 7: Production hardening, rate-limit shield, LRU caching & Vercel
PYTHONPATH=backend backend/.venv/bin/python backend/test_milestone7.py

# Frontend production bundle check
npm --prefix frontend run build
```

---

## 📚 Architectural Documentation
- See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for full architectural specs, contracts, and guidelines.
- See [DECISIONS.md](DECISIONS.md) for Architectural Decision Records (ADR 001 - 011).
- See [BUILD_LOG.md](BUILD_LOG.md) for milestone build and verification logs.
- See [HANDOFF_PROMPT.md](HANDOFF_PROMPT.md) for developer handoff instructions.
