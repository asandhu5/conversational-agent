from backend.transcript import parse_transcript, talk_time_words


def test_parses_real_transcript_into_exchanges(raw_conversation_1):
    exchanges = parse_transcript(raw_conversation_1)
    assert len(exchanges) > 0
    for e in exchanges:
        assert e.question.strip()
        assert e.answer.strip()
        assert e.answer_word_count == len(e.answer.split())


def test_exchanges_are_indexed_sequentially(raw_conversation_2):
    exchanges = parse_transcript(raw_conversation_2)
    assert [e.index for e in exchanges] == list(range(len(exchanges)))


def test_talk_time_words_counts_both_sides(raw_conversation_1):
    exchanges = parse_transcript(raw_conversation_1)
    interviewer_words, candidate_words = talk_time_words(exchanges)
    assert interviewer_words > 0
    assert candidate_words > 0


def test_empty_payload_yields_no_exchanges():
    assert parse_transcript({}) == []
    assert parse_transcript({"events": []}) == []


def test_ignores_system_turn_and_pairs_assistant_with_next_user():
    raw = {
        "events": [
            {
                "event_type": "application.transcription_ready",
                "properties": {
                    "transcript": [
                        {"role": "system", "content": "hidden instructions"},
                        {"role": "assistant", "content": "What's your background?"},
                        {"role": "user", "content": "I studied mechatronics."},
                        {"role": "assistant", "content": "Tell me about a project."},
                        {"role": "user", "content": "I built a segmentation model."},
                    ]
                },
            }
        ]
    }
    exchanges = parse_transcript(raw)
    assert len(exchanges) == 2
    assert exchanges[0].question == "What's your background?"
    assert exchanges[0].answer == "I studied mechatronics."
    assert exchanges[1].answer == "I built a segmentation model."


def test_unanswered_question_is_dropped():
    raw = {
        "events": [
            {
                "event_type": "application.transcription_ready",
                "properties": {
                    "transcript": [
                        {"role": "assistant", "content": "Q1"},
                        {"role": "user", "content": "A1"},
                        {"role": "assistant", "content": "Q2 with no answer"},
                    ]
                },
            }
        ]
    }
    exchanges = parse_transcript(raw)
    assert len(exchanges) == 1
    assert exchanges[0].question == "Q1"
