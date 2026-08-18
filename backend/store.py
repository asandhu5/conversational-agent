
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_LOCK = threading.Lock()


@dataclass
class SessionMeta:
    id: str
    role_title: str
    candidate_name: str
    duration_seconds: int
    created_at: str
    status: str = "live"  # live -> processing -> ready | error
    source: str = "live"  # live | demo
    conversation_url: str = ""
    error: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, sessions_dir: Path):
        self.dir = sessions_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir.parent / "index.json"

    # -- index -----------------------------------------------------------
    def _read_index(self) -> dict[str, dict]:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text())
        except json.JSONDecodeError:
            return {}

    def _write_index(self, index: dict[str, dict]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2))

    def list_sessions(self) -> list[dict]:
        index = self._read_index()
        return sorted(index.values(), key=lambda s: s.get("created_at", ""), reverse=True)

    # -- lifecycle ---------------------------------------------------------
    def create(self, meta: SessionMeta) -> None:
        with _LOCK:
            (self.dir / meta.id).mkdir(parents=True, exist_ok=True)
            index = self._read_index()
            index[meta.id] = asdict(meta)
            self._write_index(index)

    def update_status(self, session_id: str, status: str, error: Optional[str] = None) -> None:
        with _LOCK:
            index = self._read_index()
            if session_id in index:
                index[session_id]["status"] = status
                if error is not None:
                    index[session_id]["error"] = error
                self._write_index(index)

    def get_meta(self, session_id: str) -> Optional[dict]:
        return self._read_index().get(session_id)

    def save_raw(self, session_id: str, raw: dict) -> None:
        (self.dir / session_id / "raw.json").write_text(json.dumps(raw, indent=2))

    def save_analysis(self, session_id: str, analysis: dict) -> None:
        (self.dir / session_id / "analysis.json").write_text(json.dumps(analysis, indent=2))

    def load_raw(self, session_id: str) -> Optional[dict]:
        path = self.dir / session_id / "raw.json"
        return json.loads(path.read_text()) if path.exists() else None

    def load_analysis(self, session_id: str) -> Optional[dict]:
        path = self.dir / session_id / "analysis.json"
        return json.loads(path.read_text()) if path.exists() else None
