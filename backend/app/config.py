"""Application settings, read from environment variables (optionally from backend/.env).

Secrets are never hard-coded. If no LLM key is configured the app runs in deterministic mock mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (KEY=VALUE lines). Existing environment variables win."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: os.getenv("INSURE_DB_PATH", str(BACKEND_DIR / "data" / "insurendclaim.db")))
    upload_dir: str = field(default_factory=lambda: os.getenv("INSURE_UPLOAD_DIR", str(BACKEND_DIR / "data" / "uploads")))
    max_upload_mb: float = field(default_factory=lambda: float(os.getenv("INSURE_MAX_UPLOAD_MB", "10")))
    max_files_per_request: int = field(default_factory=lambda: int(os.getenv("INSURE_MAX_FILES", "10")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("INSURE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    )
    # LLM provider: "mock" | "anthropic" | "openai" (any OpenAI-compatible chat completions endpoint)
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock").lower())
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("LLM_API_KEY") or None)
    llm_model: str | None = field(default_factory=lambda: os.getenv("LLM_MODEL") or None)
    llm_base_url: str | None = field(default_factory=lambda: os.getenv("LLM_BASE_URL") or None)
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "25")))

    @property
    def effective_provider(self) -> str:
        """Fall back to mock when a real provider is requested but no key is set."""
        if self.llm_provider in ("anthropic", "openai") and self.llm_api_key:
            return self.llm_provider
        return "mock"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


def get_settings() -> Settings:
    return Settings()
