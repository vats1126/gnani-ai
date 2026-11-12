import sys
from pathlib import Path

# Resolve backend directory and ensure it is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Expose the FastAPI application for Vercel Serverless Functions
from app.main import app  # noqa: E402
