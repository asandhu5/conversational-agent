
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Exchange:
    index: int
    question: str
    answer: str
    question_at: Optional[float] = None
    answer_at: Optional[float] = None

    @property
    def answer_word_count(self) -> int:
        return len(self.answer.split())


def _find_transcript_turns(raw: dict) -> list[dict]:
    """Locate the transcript array inside a verbose Tavus conversation payload."""
    for event in raw.get("events", []) or []:
        if event.get("event_type") == "application.transcription_ready":
            return event.get("properties", {}).get("transcript", []) or []
    # A small number of accounts surface the transcript directly on the
    # conversation object instead of inside the events array.
    return raw.get("transcript", []) or []


def parse_transcript(raw: dict) -> list[Exchange]:
    """Turn a verbose Tavus conversation payload into ordered Q/A exchanges.

    Tavus transcripts interleave three roles: `system` (the hidden
    instructions turn, ignored here), `assistant` (the interviewer), and
    `user` (the candidate). Each assistant turn is paired with the very
    next user turn that follows it.
    """
    turns = [t for t in _find_transcript_turns(raw) if t.get("role") in ("assistant", "user")]

    exchanges: list[Exchange] = []
    idx = 0
    i = 0
    while i < len(turns):
        turn = turns[i]
        if turn.get("role") == "assistant":
            question = (turn.get("content") or "").strip()
            answer = ""
            answer_at = None
            if i + 1 < len(turns) and turns[i + 1].get("role") == "user":
                answer = (turns[i + 1].get("content") or "").strip()
                answer_at = turns[i + 1].get("timestamp") or turns[i + 1].get("seconds_from_start")
                i += 1
            if question and answer:
                exchanges.append(
                    Exchange(
                        index=idx,
                        question=question,
                        answer=answer,
                        question_at=turn.get("timestamp") or turn.get("seconds_from_start"),
                        answer_at=answer_at,
                    )
                )
                idx += 1
        i += 1
    return exchanges


def talk_time_words(exchanges: list[Exchange]) -> tuple[int, int]:
    """Return (interviewer_words, candidate_words)."""
    interviewer = sum(len(e.question.split()) for e in exchanges)
    candidate = sum(len(e.answer.split()) for e in exchanges)
    return interviewer, candidate
