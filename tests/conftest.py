import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def raw_conversation_1() -> dict:
    return json.loads((FIXTURES_DIR / "conversation_c7fda5809e314440_verbose.json").read_text())


@pytest.fixture
def raw_conversation_2() -> dict:
    return json.loads((FIXTURES_DIR / "conversation_cbd40a2fa07eb4a5_verbose.json").read_text())


@pytest.fixture
def fake_ml_pipelines(monkeypatch):
    """Replace the local HF sentiment/emotion pipelines with instant fakes.

    Unit tests should never need to download hundreds of MB of model
    weights or depend on network access to pass.
    """
    from backend import analysis

    def fake_sentiment_pipeline():
        def _call(text_batch):
            text = text_batch if isinstance(text_batch, str) else text_batch[0]
            label = "NEGATIVE" if any(w in text.lower() for w in ("bad", "fail", "struggle")) else "POSITIVE"
            return [{"label": label, "score": 0.87}]
        return _call

    def fake_emotion_pipeline():
        def _call(text_batch):
            return [[
                {"label": "joy", "score": 0.6},
                {"label": "neutral", "score": 0.3},
                {"label": "fear", "score": 0.1},
            ]]
        return _call

    monkeypatch.setattr(analysis, "_get_sentiment_pipeline", fake_sentiment_pipeline)
    monkeypatch.setattr(analysis, "_get_emotion_pipeline", fake_emotion_pipeline)
    return analysis


@pytest.fixture
def fake_openai_client(monkeypatch):
    """Replace backend.analysis._get_openai_client with a scripted mock client.

    Dispatches on the *system prompt* rather than call order/count, since
    analyze_interview() makes one skills call, N per-answer feedback calls
    (N = number of exchanges, unknown to the test in advance), then one
    summary call -- a fixed-length side_effect list would silently
    misalign as soon as N changed.
    """
    from backend import analysis

    def make_response(text):
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content=text))]
        return resp

    def fake_create(model, messages, **kwargs):
        system_prompt = messages[0]["content"]
        if "hard skills" in system_prompt.lower():
            return make_response("Python, Machine Learning, Computer Vision")
        if "senior technical interview coach" in system_prompt.lower():
            return make_response(
                "**Overall Impression**\n\nStrong technical depth.\n\n"
                "**Strengths**\n\n- Clear examples\n\n"
                "**Areas to Improve**\n\n- More metrics\n\n"
                "**Suggested Next Steps**\n\n- Practice STAR format"
            )
        return make_response("Solid, specific answer — nice use of a concrete example.")

    client = MagicMock()
    client.chat.completions.create.side_effect = fake_create

    monkeypatch.setattr(analysis, "_get_openai_client", lambda api_key: client)
    return client
