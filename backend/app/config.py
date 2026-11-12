from pathlib import Path
import os
from typing import Optional, Dict
from dotenv import dotenv_values, load_dotenv

# Resolve paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
BACKEND_ENV_PATH = BACKEND_DIR / ".env"
ROOT_ENV_PATH = ROOT_DIR / ".env"

# Capture genuine OS environment variables present at process startup before any dotenv loading
_STARTUP_OS_ENV = {
    k: os.environ[k].strip()
    for k in ("GEMINI_API_KEY", "GNANI_API_KEY", "GEMINI_LIVE_MODEL", "GNANI_TTS_VOICE", "FRONTEND_ORIGIN")
    if k in os.environ and os.environ[k].strip() and os.environ[k].strip() != "replace_me"
}


def _is_real_key(val: Optional[str]) -> bool:
    return bool(val and val.strip() and val.strip() != "replace_me")


class Settings:
    def __init__(self):
        self._backend_mtime: float = 0
        self._root_mtime: float = 0
        self._backend_values: Dict[str, str] = {}
        self._root_values: Dict[str, str] = {}
        self.reload_settings()

    def reload_settings(self):
        """
        Reloads environment settings seamlessly from:
        1. Vercel / OS environment variables (os.environ)
        2. backend/.env (if present)
        3. root .env (if present)
        Does not crash if no .env file exists on disk.
        """
        self._backend_values = {}
        if BACKEND_ENV_PATH.exists() and BACKEND_ENV_PATH.is_file():
            try:
                self._backend_mtime = BACKEND_ENV_PATH.stat().st_mtime
                self._backend_values = {
                    k: v.strip()
                    for k, v in dotenv_values(BACKEND_ENV_PATH).items()
                    if v is not None and v.strip()
                }
            except Exception:
                self._backend_values = {}
        else:
            self._backend_mtime = 0

        self._root_values = {}
        if ROOT_ENV_PATH.exists() and ROOT_ENV_PATH.is_file():
            try:
                self._root_mtime = ROOT_ENV_PATH.stat().st_mtime
                self._root_values = {
                    k: v.strip()
                    for k, v in dotenv_values(ROOT_ENV_PATH).items()
                    if v is not None and v.strip()
                }
            except Exception:
                self._root_values = {}
        else:
            self._root_mtime = 0

        # Also load into os.environ for third-party libraries (e.g., google-genai)
        if BACKEND_ENV_PATH.exists():
            load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)
        if ROOT_ENV_PATH.exists():
            load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)

    def _check_and_reload_if_modified(self):
        b_mtime = BACKEND_ENV_PATH.stat().st_mtime if BACKEND_ENV_PATH.exists() else 0
        r_mtime = ROOT_ENV_PATH.stat().st_mtime if ROOT_ENV_PATH.exists() else 0
        if b_mtime != self._backend_mtime or r_mtime != self._root_mtime:
            self.reload_settings()

    def _resolve_key(self, key: str, default: str = "") -> tuple[str, str]:
        """
        Resolves the key value and its source.
        Returns: (value, source) where source is 'os_environ', 'backend_env', 'root_env', or 'default'.
        """
        self._check_and_reload_if_modified()

        # 1. Check if set in startup OS env (e.g. Vercel dashboard)
        if key in _STARTUP_OS_ENV and _is_real_key(_STARTUP_OS_ENV[key]):
            return _STARTUP_OS_ENV[key], "os_environ"

        # 2. Check if set dynamically in os.environ and differs from disk .env
        cur_env = os.environ.get(key, "").strip()
        b_val = self._backend_values.get(key, "").strip()
        r_val = self._root_values.get(key, "").strip()
        if _is_real_key(cur_env) and cur_env != b_val and cur_env != r_val:
            return cur_env, "os_environ"

        # 3. Check backend/.env
        b_val = self._backend_values.get(key, "").strip()
        if _is_real_key(b_val):
            return b_val, "backend_env"

        # 4. Check root .env
        r_val = self._root_values.get(key, "").strip()
        if _is_real_key(r_val):
            return r_val, "root_env"

        # 5. If os.environ has any value (even placeholder), or .env had placeholder
        if cur_env and cur_env != "replace_me":
            return cur_env, "os_environ"
        if b_val:
            return b_val, "backend_env"
        if r_val:
            return r_val, "root_env"

        return default, "default"

    @property
    def GEMINI_API_KEY(self) -> str:
        val, _ = self._resolve_key("GEMINI_API_KEY", "replace_me")
        return val

    @property
    def GEMINI_LIVE_MODEL(self) -> str:
        val, _ = self._resolve_key("GEMINI_LIVE_MODEL", "gemini-3.8-live")
        return val

    @property
    def GNANI_API_KEY(self) -> str:
        val, _ = self._resolve_key("GNANI_API_KEY", "replace_me")
        return val

    @property
    def GNANI_TTS_VOICE(self) -> str:
        val, _ = self._resolve_key("GNANI_TTS_VOICE", "default")
        return val

    @property
    def FRONTEND_ORIGIN(self) -> str:
        val, _ = self._resolve_key("FRONTEND_ORIGIN", "http://localhost:5173")
        return val

    @property
    def is_gemini_configured(self) -> bool:
        return _is_real_key(self.GEMINI_API_KEY)

    @property
    def is_gnani_configured(self) -> bool:
        return _is_real_key(self.GNANI_API_KEY)

    @property
    def env_source(self) -> str:
        if not self.is_gemini_configured and not self.is_gnani_configured:
            return "unconfigured"

        # Check source of GEMINI_API_KEY or GNANI_API_KEY
        if self.is_gemini_configured:
            _, src = self._resolve_key("GEMINI_API_KEY")
            if src in ("os_environ", "backend_env", "root_env"):
                return src

        if self.is_gnani_configured:
            _, src = self._resolve_key("GNANI_API_KEY")
            if src in ("os_environ", "backend_env", "root_env"):
                return src

        return "unconfigured"


settings = Settings()
