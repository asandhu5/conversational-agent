
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    tavus_api_key: str
    tavus_replica_id: str
    tavus_persona_id: str
    openai_api_key: str
    openai_model: str
    tavus_base_url: str
    default_interview_seconds: int
    host: str
    port: int
    data_dir: Path
    sessions_dir: Path

    @property
    def tavus_configured(self) -> bool:
        return bool(self.tavus_api_key and (self.tavus_replica_id or self.tavus_persona_id))

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)


def _load() -> Config:
    data_dir = BASE_DIR / "data"
    return Config(
        tavus_api_key=os.getenv("TAVUS_API_KEY", "").strip(),
        tavus_replica_id=os.getenv("TAVUS_REPLICA_ID", "").strip(),
        tavus_persona_id=os.getenv("TAVUS_PERSONA_ID", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        tavus_base_url=os.getenv("TAVUS_BASE_URL", "https://tavusapi.com/v2").strip(),
        default_interview_seconds=_int_env("DEFAULT_INTERVIEW_SECONDS", 300),
        host=os.getenv("HOST", "127.0.0.1").strip(),
        port=_int_env("PORT", 5000),
        data_dir=data_dir,
        sessions_dir=data_dir / "sessions",
    )


config = _load()
config.sessions_dir.mkdir(parents=True, exist_ok=True)
