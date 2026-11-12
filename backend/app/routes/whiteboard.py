import base64
import time
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/whiteboard", tags=["whiteboard"])

# In-memory storage for the latest whiteboard snapshot
latest_snapshot: Dict[str, Any] = {
    "image_data": None,
    "timestamp": None,
    "size_bytes": 0,
    "format": None,
    "meta": {}
}

class SnapshotRequest(BaseModel):
    image_data: str = Field(..., description="Base64 data URL (e.g. data:image/png;base64,...)")
    timestamp: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class SnapshotResponse(BaseModel):
    ok: bool
    size_bytes: int
    format: str
    timestamp: float
    message: str

@router.post("/snapshot", response_model=SnapshotResponse)
async def upload_snapshot(payload: SnapshotRequest):
    data_url = payload.image_data.strip()
    if not data_url:
        raise HTTPException(status_code=400, detail="image_data cannot be empty")

    # Parse data URL scheme
    fmt = "png"
    raw_base64 = data_url
    if data_url.startswith("data:image/"):
        header, sep, raw_base64 = data_url.partition(";base64,")
        if not sep:
            raise HTTPException(status_code=400, detail="Invalid data URL format")
        fmt = header.split("/")[1]

    try:
        decoded_bytes = base64.b64decode(raw_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode base64: {e}")

    now = time.time()
    size = len(decoded_bytes)

    # Store latest snapshot in memory for live tutor ingestion
    latest_snapshot["image_data"] = data_url
    latest_snapshot["raw_bytes"] = decoded_bytes
    latest_snapshot["timestamp"] = payload.timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    latest_snapshot["size_bytes"] = size
    latest_snapshot["format"] = fmt
    latest_snapshot["meta"] = payload.meta or {}

    return SnapshotResponse(
        ok=True,
        size_bytes=size,
        format=fmt,
        timestamp=now,
        message="Whiteboard snapshot stored successfully"
    )

@router.get("/snapshot/latest")
async def get_latest_snapshot():
    if not latest_snapshot["image_data"]:
        return {
            "has_snapshot": False,
            "message": "No snapshot has been submitted yet"
        }
    return {
        "has_snapshot": True,
        "timestamp": latest_snapshot["timestamp"],
        "size_bytes": latest_snapshot["size_bytes"],
        "format": latest_snapshot["format"],
        "meta": latest_snapshot["meta"],
        "preview": latest_snapshot["image_data"][:100] + "..."
    }

