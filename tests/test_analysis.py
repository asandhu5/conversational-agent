from backend.analysis import (
    analyze_interview,
    completeness_note,
    map_competencies,
)
from backend.transcript import parse_transcript


def test_map_competencies_matches_keywords():
    assert "Technical Knowledge" in map_competencies("I trained a model on a large dataset.")
    assert "Leadership" in map_competencies("I mentored two junior engineers on the team.")
    assert map_competencies("The weather was nice today.") == ["General"]


def test_completeness_note_flags_short_off_topic_answers():
    note = completeness_note("What machine learning frameworks have you used?", "Not sure.")
    assert note


def test_completeness_note_empty_for_relevant_answer():
    note = completeness_note(
        "What machine learning frameworks have you used?",
        "I've used PyTorch and TensorFlow extensively for training deep learning models.",
    )
    assert note == ""


def test_analyze_interview_without_openai_key_uses_fallbacks(raw_conversation_1, fake_ml_pipelines):
    exchanges = parse_transcript(raw_conversation_1)
    result = analyze_interview(exchanges, openai_api_key="", openai_model="gpt-4o-mini")

    assert result.ai_powered is False
    assert len(result.exchanges) == len(exchanges)
    assert all(ex.ai_feedback is None for ex in result.exchanges)
    assert "OPENAI_API_KEY" in result.summary  # honest fallback text, not fabricated AI content
    assert result.hard_skills  # keyword fallback still finds something or a sane default
    assert 0.0 <= result.overall_positivity <= 1.0
    assert result.interviewer_words > 0 and result.candidate_words > 0


def test_analyze_interview_with_openai_key_uses_ai_paths(raw_conversation_1, fake_ml_pipelines, fake_openai_client):
    exchanges = parse_transcript(raw_conversation_1)
    result = analyze_interview(exchanges, openai_api_key="sk-fake", openai_model="gpt-4o-mini")

    assert result.ai_powered is True
    assert result.hard_skills == ["Python", "Machine Learning", "Computer Vision"]
    assert all(ex.ai_feedback for ex in result.exchanges)
    assert "Overall Impression" in result.summary
    assert fake_openai_client.chat.completions.create.called


def test_analyze_interview_handles_zero_exchanges(fake_ml_pipelines):
    result = analyze_interview([], openai_api_key="", openai_model="gpt-4o-mini")
    assert result.exchanges == []
    assert result.overall_positivity == 0.5
    assert result.interviewer_words == 0
    assert result.candidate_words == 0


def test_to_dict_is_json_serializable(raw_conversation_1, fake_ml_pipelines):
    import json

    exchanges = parse_transcript(raw_conversation_1)
    result = analyze_interview(exchanges, openai_api_key="", openai_model="gpt-4o-mini")
    json.dumps(result.to_dict())  # raises if anything isn't serializable
