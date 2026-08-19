
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Optional

from .transcript import Exchange, talk_time_words

logger = logging.getLogger(__name__)

COMPETENCY_KEYWORDS: dict[str, list[str]] = {
    "Technical Knowledge": ["model", "dataset", "algorithm", "architecture", "hyperparameter", "train", "pipeline", "framework"],
    "Problem Solving": ["challenge", "issue", "debug", "optimi", "improve", "solve", "trade-off", "tradeoff", "bottleneck"],
    "Communication": ["explain", "describe", "summar", "clarif", "present", "articulat"],
    "Leadership": ["lead", "own", "manage", "mentor", "coordinat", "decision", "initiative"],
    "Teamwork": ["team", "collaborat", "together", "cross-functional", "stakeholder", "pair"],
}

FALLBACK_HARD_SKILLS = [
    "Python", "SQL", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
    "AWS", "Docker", "Kubernetes", "React", "Node.js", "Git", "CI/CD", "API Design",
    "Data Engineering", "NLP", "Computer Vision", "Statistics", "A/B Testing", "Java", "C++",
]

_WORD_RE = re.compile(r"[a-zA-Z']+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "with", "as", "that", "this", "it", "i", "you", "your",
    "what", "how", "do", "did", "does", "can", "could", "would", "should", "tell", "me", "about",
    "so", "just", "like", "yeah", "um", "uh",
}

_POSITIVE_WORDS = {
    "good", "great", "strong", "successful", "improved", "effective", "confident", "excited",
    "achieved", "optimized", "proud", "love", "enjoy", "excellent", "solid", "smooth",
}
_NEGATIVE_WORDS = {
    "bad", "difficult", "fail", "failed", "struggle", "struggled", "confus", "weak",
    "problem", "issue", "stuck", "unsure", "worried", "hard", "annoying",
}

EMOTION_LABELS = {
    "joy": "Enthusiastic", "sadness": "Reflective", "anger": "Assertive",
    "disgust": "Analytical", "fear": "Cautious", "surprise": "Adaptive", "neutral": "Measured",
}


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def map_competencies(answer: str) -> list[str]:
    lower = answer.lower()
    tags = [name for name, kws in COMPETENCY_KEYWORDS.items() if any(k in lower for k in kws)]
    return tags or ["General"]


def completeness_note(question: str, answer: str) -> str:
    q_tokens = _tokenize(question) - _STOPWORDS
    a_tokens = _tokenize(answer)
    if not q_tokens:
        return ""
    overlap = q_tokens & a_tokens
    if len(overlap) / len(q_tokens) < 0.15 and len(answer.split()) < 15:
        return "This answer looks brief relative to the question asked — consider adding more detail."
    return ""


@dataclass
class ExchangeAnalysis:
    index: int
    question: str
    answer: str
    word_count: int
    sentiment_label: str
    sentiment_score: float
    positivity: float
    emotion_label: str
    emotion_score: float
    competencies: list[str]
    note: str
    ai_feedback: Optional[str] = None


@dataclass
class InterviewAnalysis:
    exchanges: list[ExchangeAnalysis]
    interviewer_words: int
    candidate_words: int
    competency_counts: dict[str, int]
    emotion_counts: dict[str, int]
    overall_positivity: float
    hard_skills: list[str]
    summary: str
    ai_powered: bool
    models_used: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)

@lru_cache(maxsize=1)
def _get_sentiment_pipeline():
    from transformers import pipeline
    logger.info("Loading local sentiment model (first run downloads ~260MB)...")

    return pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")


@lru_cache(maxsize=1)
def _get_emotion_pipeline():
    from transformers import pipeline
    logger.info("Loading local emotion model (first run downloads ~330MB)...")
    return pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        top_k=None,
    )


def _lexicon_sentiment(text: str) -> tuple[str, float]:
    tokens = _tokenize(text)
    pos = len(tokens & _POSITIVE_WORDS)
    neg = len(tokens & _NEGATIVE_WORDS)
    if pos == neg:
        return "NEUTRAL", 0.5
    if pos > neg:
        return "POSITIVE", min(0.6 + 0.05 * (pos - neg), 0.95)
    return "NEGATIVE", min(0.6 + 0.05 * (neg - pos), 0.95)


def _analyze_sentiment(text: str) -> tuple[str, float]:
    if not text.strip():
        return "NEUTRAL", 0.5
    try:
        result = _get_sentiment_pipeline()(text[:512])[0]
        return result["label"], float(result["score"])
    except Exception:
        logger.exception("Local sentiment model unavailable, using lexicon fallback")
        return _lexicon_sentiment(text)


def _analyze_emotion(text: str) -> tuple[str, float]:
    if not text.strip():
        return "Measured", 0.0
    try:
        scores = _get_emotion_pipeline()(text[:512])[0]
        best = max(scores, key=lambda s: s["score"])
        return EMOTION_LABELS.get(best["label"], best["label"].title()), float(best["score"])
    except Exception:
        logger.exception("Local emotion model unavailable, defaulting to 'Measured'")
        return "Measured", 0.0


def _positivity(sentiment_label: str, sentiment_score: float) -> float:
    """Fold label+confidence into a single 0..1 'positivity' axis for charting."""
    if sentiment_label.upper() == "POSITIVE":
        return sentiment_score
    if sentiment_label.upper() == "NEGATIVE":
        return 1 - sentiment_score
    return 0.5

def _get_openai_client(api_key: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")


def _fallback_hard_skills(exchanges: list[Exchange]) -> list[str]:
    text = " ".join(e.answer.lower() for e in exchanges)
    found = [s for s in FALLBACK_HARD_SKILLS if s.lower() in text]
    return found[:10] or ["Problem Solving", "Communication"]


def _extract_hard_skills_ai(client, model: str, exchanges: list[Exchange]) -> list[str]:
    combined = " ".join(e.answer for e in exchanges)[:6000]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract concrete hard skills (languages, tools, frameworks, "
                        "methodologies) mentioned in an interview transcript. Reply with a "
                        "comma-separated list only, 5-15 items, no commentary."
                    ),
                },
                {"role": "user", "content": combined or "(no answers given)"},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content or ""
        skills = [s.strip() for s in text.split(",") if s.strip()]
        return skills[:15] if skills else _fallback_hard_skills(exchanges)
    except Exception:
        logger.exception("OpenAI hard-skill extraction failed, using keyword fallback")
        return _fallback_hard_skills(exchanges)


def _coach_feedback_ai(client, model: str, question: str, answer: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, encouraging interview coach. In 1-2 sentences "
                        "(max 40 words), give specific, actionable feedback on this single answer."
                    ),
                },
                {"role": "user", "content": f"Question: {question}\nAnswer: {answer}"},
            ],
            temperature=0.4,
            max_tokens=100,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("OpenAI per-answer feedback failed")
        return ""


def _fallback_summary(exchanges: list[Exchange], hard_skills: list[str]) -> str:
    total = len(exchanges)
    avg_words = (sum(e.answer_word_count for e in exchanges) / total) if total else 0
    return (
        f"**Overall Impression**\n\nYou answered {total} question(s) with an average of "
        f"{avg_words:.0f} words per answer.\n\n"
        f"**Strengths**\n\n- Engaged with every question asked\n"
        f"- Touched on: {', '.join(hard_skills[:5]) or 'the topics discussed'}\n\n"
        "**Areas to Improve**\n\n- Add a coaching key to `.env` to unlock AI-generated, "
        "answer-specific coaching feedback and a real evaluation here — this is a built-in "
        "placeholder.\n\n"
        "**Suggested Next Steps**\n\n"
        "- Structure answers with the STAR method (Situation, Task, Action, Result) for more concrete impact."
    )


def _summary_ai(client, model: str, exchanges: list[Exchange], hard_skills: list[str]) -> str:
    transcript_text = "\n\n".join(f"Q: {e.question}\nA: {e.answer}" for e in exchanges)[:8000]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior technical interview coach. Review this full mock-interview "
                        "transcript and write a structured evaluation in Markdown with these exact "
                        "section headers: **Overall Impression**, **Strengths**, **Areas to Improve**, "
                        "**Suggested Next Steps**. Be specific, reference the candidate's actual "
                        "answers, and keep the whole thing under 300 words."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Transcript:\n{transcript_text}\n\nHard skills detected: {', '.join(hard_skills)}",
                },
            ],
            temperature=0.4,
            max_tokens=700,
        )
        return (resp.choices[0].message.content or "").strip() or _fallback_summary(exchanges, hard_skills)
    except Exception:
        logger.exception("OpenAI summary generation failed, using rule-based fallback")
        return _fallback_summary(exchanges, hard_skills)


def analyze_interview(
    exchanges: list[Exchange],
    *,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
) -> InterviewAnalysis:
    interviewer_words, candidate_words = talk_time_words(exchanges)

    client = None
    ai_powered = False
    if openai_api_key:
        try:
            client = _get_openai_client(openai_api_key)
            ai_powered = True
        except Exception:
            logger.exception("Could not initialize OpenAI client; continuing without AI augmentation")

    hard_skills = _extract_hard_skills_ai(client, openai_model, exchanges) if client else _fallback_hard_skills(exchanges)

    exchange_results: list[ExchangeAnalysis] = []
    competency_counts: dict[str, int] = {}
    emotion_counts: dict[str, int] = {}

    for e in exchanges:
        sent_label, sent_score = _analyze_sentiment(e.answer)
        emo_label, emo_score = _analyze_emotion(e.answer)
        comps = map_competencies(e.answer)
        for c in comps:
            competency_counts[c] = competency_counts.get(c, 0) + 1
        emotion_counts[emo_label] = emotion_counts.get(emo_label, 0) + 1

        feedback = _coach_feedback_ai(client, openai_model, e.question, e.answer) if client else ""

        exchange_results.append(
            ExchangeAnalysis(
                index=e.index,
                question=e.question,
                answer=e.answer,
                word_count=e.answer_word_count,
                sentiment_label=sent_label,
                sentiment_score=round(sent_score, 3),
                positivity=round(_positivity(sent_label, sent_score), 3),
                emotion_label=emo_label,
                emotion_score=round(emo_score, 3),
                competencies=comps,
                note=completeness_note(e.question, e.answer),
                ai_feedback=feedback or None,
            )
        )

    overall_positivity = (
        sum(r.positivity for r in exchange_results) / len(exchange_results) if exchange_results else 0.5
    )
    summary = _summary_ai(client, openai_model, exchanges, hard_skills) if client else _fallback_summary(exchanges, hard_skills)

    return InterviewAnalysis(
        exchanges=exchange_results,
        interviewer_words=interviewer_words,
        candidate_words=candidate_words,
        competency_counts=competency_counts,
        emotion_counts=emotion_counts,
        overall_positivity=round(overall_positivity, 3),
        hard_skills=hard_skills,
        summary=summary,
        ai_powered=ai_powered,
        models_used={
            "sentiment": "distilbert-base-uncased-finetuned-sst-2-english (local)",
            "emotion": "j-hartmann/emotion-english-distilroberta-base (local)",
            "coaching": openai_model if ai_powered else "heuristic (no OpenAI key configured)",
        },
    )
