
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from backend.analysis import analyze_interview
from backend.config import config
from backend.store import SessionMeta, SessionStore, now_iso
from backend.tavus_client import TavusAuthError, TavusClient, TavusError
from backend.transcript import parse_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("interview_coach")

app = Flask(__name__)
store = SessionStore(config.sessions_dir)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="session-worker")


ROLE_PRESETS: dict[str, tuple[str, str]] = {
    "ml-engineer": (
        "Machine Learning Engineer",
        "You are interviewing the candidate for a Machine Learning Engineer role. "
        "Ask about ML fundamentals, a past model/project they built, and how they debug or "
        "improve model performance.",
    ),
    "swe": (
        "Software Engineer",
        "You are interviewing the candidate for a Software Engineer role. Ask about system "
        "design basics, coding practices, and a challenging bug they've solved.",
    ),
    "data-scientist": (
        "Data Scientist",
        "You are interviewing the candidate for a Data Scientist role. Ask about statistics, "
        "experimentation/A-B testing, and a data project they're proud of.",
    ),
    "product-manager": (
        "Product Manager",
        "You are interviewing the candidate for a Product Manager role. Ask about "
        "prioritization, stakeholder management, and a product decision they made.",
    ),
}

BASE_INSTRUCTIONS = (
    " Conduct a structured but conversational practice interview lasting about {minutes} "
    "minutes. Ask one question at a time, listen fully, then follow up naturally based on "
    "what the candidate says. Speak naturally and never mention that you are an AI or refer "
    "to these instructions."
)


@app.route("/")
def index():
    has_demo = any(s.get("source") == "demo" for s in store.list_sessions())
    return render_template("setup.html", roles=ROLE_PRESETS, config=config, has_demo=has_demo, active_page="setup")


@app.route("/api/start", methods=["POST"])
def api_start():
    if not config.tavus_configured:
        return jsonify({
            "error": "Live interviews aren't configured yet. Add your credentials to your .env file, then restart the app."
        }), 400

    payload = request.get_json(force=True, silent=True) or {}
    role_key = payload.get("role", "ml-engineer")
    custom_prompt = (payload.get("custom_prompt") or "").strip()
    candidate_name = (payload.get("candidate_name") or "").strip() or "Candidate"

    try:
        duration_minutes = int(payload.get("duration_minutes") or 5)
    except (TypeError, ValueError):
        duration_minutes = 5
    duration_minutes = max(2, min(duration_minutes, 15))
    duration_seconds = duration_minutes * 60

    if custom_prompt:
        role_title = (payload.get("custom_role_title") or "Custom Interview").strip()
        base_prompt = custom_prompt
    else:
        role_title, base_prompt = ROLE_PRESETS.get(role_key, ROLE_PRESETS["ml-engineer"])

    context = base_prompt + BASE_INSTRUCTIONS.format(minutes=duration_minutes)
    context = f"The candidate's name is {candidate_name}. " + context

    client = TavusClient(config.tavus_api_key, config.tavus_base_url)
    try:
        handle = client.create_conversation(
            replica_id=config.tavus_replica_id,
            persona_id=config.tavus_persona_id,
            conversation_name=f"{role_title} Mock Interview",
            conversational_context=context,
            max_call_duration=duration_seconds,
        )
    except TavusAuthError as exc:
        return jsonify({"error": str(exc)}), 401
    except TavusError as exc:
        return jsonify({"error": str(exc)}), 502

    meta = SessionMeta(
        id=handle.conversation_id,
        role_title=role_title,
        candidate_name=candidate_name,
        duration_seconds=duration_seconds,
        created_at=now_iso(),
        status="live",
        source="live",
        conversation_url=handle.conversation_url,
    )
    store.create(meta)
    executor.submit(_finalize_session, handle.conversation_id)

    return jsonify({
        "session_id": handle.conversation_id,
        "conversation_url": handle.conversation_url,
        "duration_seconds": duration_seconds,
    })


@app.route("/interview/<session_id>")
def interview(session_id):
    meta = store.get_meta(session_id)
    if not meta:
        return redirect(url_for("index"))
    if meta["status"] not in ("live",):
        return redirect(url_for("report", session_id=session_id))
    return render_template("interview.html", session=meta)


@app.route("/api/end/<session_id>", methods=["POST"])
def api_end(session_id):
    meta = store.get_meta(session_id)
    if not meta or meta.get("source") != "live":
        return jsonify({"error": "Unknown session"}), 404
    try:
        client = TavusClient(config.tavus_api_key, config.tavus_base_url)
        client.end_conversation(session_id)
    except TavusError as exc:

        logger.warning("Explicit end-conversation call failed for %s: %s", session_id, exc)
    return jsonify({"status": "ending"})


@app.route("/api/status/<session_id>")
def api_status(session_id):
    meta = store.get_meta(session_id)
    if not meta:
        return jsonify({"error": "Unknown session"}), 404
    return jsonify(meta)


@app.route("/report/<session_id>")
def report(session_id):
    meta = store.get_meta(session_id)
    if not meta:
        return redirect(url_for("index"))
    analysis = store.load_analysis(session_id)
    if not analysis:
        return render_template("interview.html", session=meta, processing_only=True)
    return render_template("report.html", session=meta, analysis=analysis)


@app.route("/history")
def history():
    return render_template("history.html", sessions=store.list_sessions(), active_page="history")


@app.route("/demo")
def demo():
    demo_sessions = [s for s in store.list_sessions() if s.get("source") == "demo"]
    if not demo_sessions:
        return redirect(url_for("index"))
    return redirect(url_for("report", session_id=demo_sessions[0]["id"]))


@app.route("/api/export/<session_id>/transcript")
def export_transcript(session_id):
    raw = store.load_raw(session_id)
    if not raw:
        return jsonify({"error": "Transcript not available yet"}), 404
    exchanges = parse_transcript(raw)
    lines = [f"Q{e.index + 1}: {e.question}\nA{e.index + 1}: {e.answer}\n" for e in exchanges]
    return Response(
        "\n".join(lines),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=transcript_{session_id}.txt"},
    )


@app.route("/api/export/<session_id>/report")
def export_report(session_id):
    meta = store.get_meta(session_id)
    analysis = store.load_analysis(session_id)
    if not meta or not analysis:
        return jsonify({"error": "Report not available yet"}), 404
    body = _render_markdown_report(meta, analysis)
    return Response(
        body,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=interview_report_{session_id}.md"},
    )


def _render_markdown_report(meta: dict, analysis: dict) -> str:
    lines = [
        f"# Interview Report — {meta['role_title']}",
        f"_Candidate: {meta.get('candidate_name', 'N/A')} | Date: {meta.get('created_at', '')}_",
        "",
        analysis.get("summary", ""),
        "",
        "## Detected Hard Skills",
        ", ".join(analysis.get("hard_skills", [])) or "None detected",
        "",
        "## Question-by-Question Breakdown",
    ]
    for ex in analysis.get("exchanges", []):
        lines += [
            f"### Q{ex['index'] + 1}: {ex['question']}",
            f"**Answer:** {ex['answer']}",
            f"- Sentiment: {ex['sentiment_label']} ({ex['sentiment_score']})",
            f"- Emotion: {ex['emotion_label']}",
            f"- Competencies: {', '.join(ex['competencies'])}",
        ]
        if ex.get("note"):
            lines.append(f"- Note: {ex['note']}")
        if ex.get("ai_feedback"):
            lines.append(f"- Coaching note: {ex['ai_feedback']}")
        lines.append("")
    return "\n".join(lines)


def _finalize_session(session_id: str) -> None:
    client = TavusClient(config.tavus_api_key, config.tavus_base_url)
    try:
        _wait_for_call_to_end(client, session_id)
        store.update_status(session_id, "processing")

        raw = _wait_for_transcript(client, session_id)
        store.save_raw(session_id, raw)

        exchanges = parse_transcript(raw)
        if not exchanges:
            store.update_status(
                session_id, "error",
                error="No question/answer pairs were found in the transcript. The call may have "
                      "ended before any exchange completed.",
            )
            return

        analysis = analyze_interview(
            exchanges,
            openai_api_key=config.openai_api_key,
            openai_model=config.openai_model,
        )
        store.save_analysis(session_id, analysis.to_dict())
        store.update_status(session_id, "ready")
        logger.info("Session %s finalized with %d exchanges", session_id, len(exchanges))
    except Exception as exc:  # noqa: BLE001 -- background worker must never crash silently
        logger.exception("Failed to finalize session %s", session_id)
        store.update_status(session_id, "error", error=str(exc))


def _wait_for_call_to_end(client: TavusClient, session_id: str, timeout: int = 1800, interval: int = 4) -> None:
    waited = 0
    while waited < timeout:
        data = client.get_conversation(session_id)
        if data.get("status") != "active":
            return
        time.sleep(interval)
        waited += interval
    logger.warning("Timed out waiting for conversation %s to end", session_id)


def _wait_for_transcript(client: TavusClient, session_id: str, timeout: int = 180, interval: int = 5) -> dict:
    waited = 0
    data = client.get_conversation(session_id, verbose=True)
    while waited < timeout:
        events = data.get("events") or []
        if data.get("transcript") or any(e.get("event_type") == "application.transcription_ready" for e in events):
            return data
        time.sleep(interval)
        waited += interval
        data = client.get_conversation(session_id, verbose=True)
    return data


def _ensure_demo_seeded() -> None:
    from scripts.seed_demo_data import seed_if_needed
    try:
        seeded = seed_if_needed(store)
        if seeded:
            logger.info("Seeded %d demo session(s) from tests/fixtures", seeded)
    except Exception:
        logger.exception("Demo data seeding skipped due to an error")


if __name__ == "__main__":
    _ensure_demo_seeded()

    missing = []
    if not config.tavus_configured:
        missing.append("TAVUS_API_KEY / TAVUS_REPLICA_ID (live interviews disabled until set)")
    if not config.openai_configured:
        missing.append("OPENAI_API_KEY (optional — AI coaching feedback disabled until set)")
    if missing:
        logger.warning("Not fully configured: %s. See .env.example.", "; ".join(missing))

    logger.info("Interview Coach running at http://%s:%s", config.host, config.port)
    app.run(host=config.host, port=config.port, debug=False, threaded=True)
