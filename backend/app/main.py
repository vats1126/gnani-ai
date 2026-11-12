from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes.health import router as health_router
from app.routes.whiteboard import router as whiteboard_router
from app.routes.tutor import router as tutor_router
from app.routes.voice import router as voice_router
from app.routes.tools import router as tools_router

app = FastAPI(
    title="Agentic Multilingual Learning Tutor Backend",
    version="1.0.0",
    description="Backend API providing Gemini Live relay, Gnani voice integration, and SymPy verification."
)

# Allowed CORS origins
allowed_origins = {
    settings.FRONTEND_ORIGIN,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(health_router)
app.include_router(whiteboard_router)
app.include_router(tutor_router)
app.include_router(voice_router)
app.include_router(tools_router)


