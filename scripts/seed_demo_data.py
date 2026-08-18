
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.analysis import analyze_interview  # noqa: E402
from backend.config import config  # noqa: E402
from backend.store import SessionMeta, SessionStore, now_iso  # noqa: E402
from backend.transcript import parse_transcript  # noqa: E402

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

DEMO_FILES = {
    "conversation_c7fda5809e314440_verbose.json": "Machine Learning Engineer",
    "conversation_cbd40a2fa07eb4a5_verbose.json": "Machine Learning Engineer",
}


def seed_if_needed(store: SessionStore, fixtures_dir: Path = FIXTURES_DIR) -> int:
    if any(s.get("source") == "demo" for s in store.list_sessions()):
        return 0

    seeded = 0
    for filename, role_title in DEMO_FILES.items():
        path = fixtures_dir / filename
        if not path.exists():
            continue

        raw = json.loads(path.read_text())
        exchanges = parse_transcript(raw)
        if not exchanges:
            continue

        analysis = analyze_interview(
            exchanges,
            openai_api_key=config.openai_api_key,
            openai_model=config.openai_model,
        )

        session_id = raw.get("conversation_id") or path.stem
        meta = SessionMeta(
            id=session_id,
            role_title=role_title,
            candidate_name="Sample Candidate",
            duration_seconds=300,
            created_at=raw.get("created_at") or now_iso(),
            status="ready",
            source="demo",
        )
        store.create(meta)
        store.save_raw(session_id, raw)
        store.save_analysis(session_id, analysis.to_dict())
        seeded += 1
        logger.info("Seeded demo session %s (%s)", session_id, role_title)

    return seeded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _store = SessionStore(config.sessions_dir)
    count = seed_if_needed(_store)
    print(f"Seeded {count} demo session(s) into {_store.dir}")
