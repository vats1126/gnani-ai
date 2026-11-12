import asyncio
import time
from typing import Dict, Any, List, Optional

class SessionRecord:
    def __init__(self, session_id: str, subject: str = "maths", language_code: str = "indic-auto"):
        self.session_id: str = session_id
        self.lock: asyncio.Lock = asyncio.Lock()
        self.live_cm: Optional[Any] = None       # Async context manager from client.aio.live.connect
        self.live_session: Optional[Any] = None  # AsyncSession object
        self.history: List[Dict[str, str]] = []  # List of {"role": "student"|"tutor", "text": "..."}
        self.subject: str = subject
        self.last_language_code: str = language_code
        self.created_at: float = time.time()
        self.last_active_at: float = time.time()

    def touch(self):
        self.last_active_at = time.time()

    def append_turn(self, role: str, text: str):
        self.touch()
        self.history.append({"role": role, "text": text.strip()})
        # Keep capped at last 10 turns to avoid unbounded memory / token growth
        if len(self.history) > 10:
            self.history = self.history[-10:]

    def hydrate_history(self, history: Optional[List[Dict[str, str]]]):
        """Hydrates history from stateless request if current session has no history."""
        if not self.history and history:
            for item in history[-6:]:
                role = item.get("role", "student")
                text = item.get("text", "")
                if text:
                    self.history.append({"role": role, "text": str(text).strip()})

    def get_history_summary(self) -> str:
        """Constructs a compact conversational context string for transparent reconnection."""
        if not self.history:
            return ""
        lines = []
        for h in self.history[-6:]:
            speaker = "Student" if h["role"] == "student" else "Tutor"
            lines.append(f"{speaker}: {h['text']}")
        return "\n".join(lines)

    async def close_live(self):
        """Safely tears down the active Gemini Live connection."""
        if self.live_session:
            try:
                await self.live_session.close()
            except Exception:
                pass
            self.live_session = None

        if self.live_cm:
            try:
                await self.live_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self.live_cm = None

class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str, subject: str = "maths", language_code: str = "indic-auto") -> SessionRecord:
        async with self._lock:
            if session_id not in self._sessions:
                record = SessionRecord(session_id, subject=subject, language_code=language_code)
                self._sessions[session_id] = record
            else:
                record = self._sessions[session_id]
                record.touch()
                if subject:
                    record.subject = subject
                if language_code:
                    record.last_language_code = language_code
            return record

    async def get(self, session_id: str) -> Optional[SessionRecord]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> bool:
        """Closes and removes a student session."""
        async with self._lock:
            record = self._sessions.pop(session_id, None)

        if record:
            async with record.lock:
                await record.close_live()
            return True
        return False

    async def cleanup_stale_sessions(self, max_idle_seconds: int = 3600) -> int:
        """Removes sessions inactive for more than max_idle_seconds."""
        now = time.time()
        stale_ids = []
        async with self._lock:
            for sid, rec in self._sessions.items():
                if now - rec.last_active_at > max_idle_seconds:
                    stale_ids.append(sid)

        for sid in stale_ids:
            await self.close_session(sid)
        return len(stale_ids)

session_manager = SessionManager()

