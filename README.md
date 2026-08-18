# Interview Coach

A live, AI-driven mock interview tool. You talk to an AI interviewer over video
(powered by [Tavus](https://www.tavus.io)'s Conversational Video Interface),
and the moment you hang up, you get a full coaching dashboard: sentiment and
emotion per answer, competency coverage, detected hard skills, and — if you
add an OpenAI key — AI-written feedback on every response plus an overall
evaluation.

<p>
  <img alt="status" src="https://img.shields.io/badge/status-working-34d399">
  <img alt="python" src="https://img.shields.io/badge/python-3.11-6d8cff">
</p>

## What it does

1. **Set up** — pick a role (ML Engineer, Software Engineer, Data Scientist,
   Product Manager, or write your own prompt), your name, and a duration.
2. **Talk it out** — a live AI interviewer asks questions over video in your
   browser, for as long as you configured.
3. **Get coached** — as soon as the call ends, the app automatically pulls
   the transcript, analyzes it, and shows you a dashboard: a sentiment
   timeline, an emotion breakdown, competency coverage, detected hard
   skills, and a per-question accordion with coaching notes. Export the
   transcript or the full report as Markdown.

Sentiment and emotion analysis run **entirely on your machine** (local
HuggingFace models) — no answer data leaves your computer unless you've
added an OpenAI key for the coaching-feedback layer, and even then only the
transcript text is sent, never audio/video.

## Quickstart

```bash
# 1. Activate the project's virtual environment (already set up with all
#    dependencies installed and tested)
source .venv/bin/activate

# 2. Add your API keys to .env (see "Getting API keys" below)
#    open .env in any editor and fill in TAVUS_API_KEY at minimum

# 3. Run it
python app.py
```

Then open **http://127.0.0.1:5000**. The first time you run it, the app
seeds two sample reports from real archived interviews into your history so
you can see the dashboard immediately — click **"View a Sample Report
Instead"** on the home page.

The very first analysis run will download two small local ML models
(~600MB total, one-time, cached under `~/.cache/huggingface`) — this can
take a minute or two depending on your connection.

## Getting API keys

### Tavus (required for live interviews)

1. Sign up at **https://platform.tavus.io** — there's a free tier, no card
   required to start testing.
2. Open the PAL Maker dashboard: **https://maker.tavus.io/dev** → click
   **"API Key"** in the sidebar → **"Create New Key"**. Copy it into
   `TAVUS_API_KEY` in `.env`.
3. You also need a **replica** (the AI interviewer's face + voice). Use a
   stock replica from your dashboard, or create your own at
   **https://platform.tavus.io/replicas**, then copy its ID into
   `TAVUS_REPLICA_ID`.
   - `.env` is pre-filled with `r9d30b0e55ac`, the replica this project used
     previously — check your Tavus dashboard to confirm it's still on your
     account before relying on it; replace it if not.
4. Optional: if you build a **Persona** in PAL Maker (custom LLM/voice
   config), set `TAVUS_PERSONA_ID` too.

Tavus pricing: free to start, paid plans from ~$20–39/month for ongoing use
(current pricing at https://www.tavus.io/pricing). Watch your usage on the
dashboard — creating a conversation has a cost on paid plans.

### OpenAI (optional — unlocks AI coaching feedback)

Without this, the app still gives you full sentiment/emotion analysis,
competency tagging, and hard-skill detection — the summary is just
rule-based text instead of an AI-written evaluation, and there's no
per-answer coaching note.

Get a key at **https://platform.openai.com/api-keys**, put it in
`OPENAI_API_KEY`. Default model is `gpt-4o-mini` (cheap, fast); change
`OPENAI_MODEL` if you want something else.

**Never commit `.env` or paste your key into code.** This project's `.gitignore`
already excludes it.

## Architecture

```
app.py                  Flask routes + background session worker
backend/
  config.py              .env loading & validation
  tavus_client.py         Tavus v2 API wrapper (create/end/get conversation)
  transcript.py            Parses Tavus's raw transcript into Q/A pairs
  analysis.py               Sentiment, emotion, competencies, AI coaching
  store.py                    JSON-file session persistence (no DB needed)
templates/               Jinja2 pages (setup, interview, report, history)
static/                 CSS + vanilla JS (Chart.js + marked.js via CDN)
scripts/seed_demo_data.py   Seeds sample reports from tests/fixtures/
tests/                  pytest suite (fixtures = 2 real archived interviews)
```

**Why no database?** This is a single-user local tool. Each interview gets
its own folder under `data/sessions/<id>/` (raw transcript + analysis
JSON), indexed by a flat `data/index.json`. Simple, inspectable, and easy
to back up by just copying the folder.

**Why Flask's dev server and not gunicorn/uwsgi?** This app is meant to run
on your own machine for your own practice sessions. If you ever want to
expose it beyond `127.0.0.1`, put a real WSGI server in front of it first.

## Running tests

```bash
source .venv/bin/activate
pytest -v
```

The test suite is fully offline and fast (~2s) — it mocks both the local ML
pipelines and the OpenAI client, and exercises real parsing logic against
the two archived interview transcripts in `tests/fixtures/`.

## Project history / what changed

This replaces an earlier version of the same idea (`main.py` +
`insights.py`/`insi2.py`/`separate_qa.py`) that worked but had a few real
problems, all fixed in this rewrite:

- A **live OpenAI API key was hardcoded in `insights.py` and in `.env`** —
  both have been scrubbed. **If you haven't already, rotate that key at
  platform.openai.com — treat it as compromised.**
- `insights.py` and `insi2.py` were two ~80%-duplicated, cross-mislabeled
  forks of the same analysis logic, both pointed at a hardcoded path that
  didn't exist in this project. Consolidated into `backend/analysis.py`,
  with every fallback path now actually reachable and unit-tested.
- Analysis output was three matplotlib windows that popped up and had to be
  closed manually. Replaced with a real in-browser dashboard.
- The three scripts (`main.py` → `separate_qa.py` → `insights.py`) had to be
  run by hand in sequence with manually-edited paths. Now it's one app: the
  analysis runs automatically the moment your interview ends.
- Tavus's API has shifted its canonical model to `pal_id`/`face_id` since
  this project was first built; this rewrite verified against current docs
  that the `replica_id`/`persona_id` fields it already used are still fully
  supported, so no migration is required on your end.
- `transformers` 5.x removed the `"sentiment-analysis"` pipeline alias this
  project originally used — updated to `"text-classification"` with the
  same model, verified working.

## Troubleshooting

- **Port 5000 already in use / can't reach the app** — on macOS, "AirPlay
  Receiver" listens on port 5000 by default and will silently grab it before
  your app can. Either turn it off (System Settings → General → AirDrop &
  Handoff → AirPlay Receiver), or set `PORT=5001` (or any free port) in
  `.env`.
- **"Tavus isn't configured yet" banner** — you're missing `TAVUS_API_KEY`
  or `TAVUS_REPLICA_ID`/`TAVUS_PERSONA_ID` in `.env`. Restart the app after
  editing `.env` (Flask only reads it at startup).
- **401 Unauthorized from Tavus** — the API key is wrong or was revoked;
  generate a new one from the PAL Maker dashboard.
- **Camera/mic don't work in the call** — your browser needs permission to
  use them for `127.0.0.1`; check your browser's site settings.
- **Analysis seems stuck on "Analyzing…"** — the first run downloads two ML
  models (~600MB); check your terminal for download progress. After that,
  it's fast every time.
- **No recording available** — video recording requires configuring cloud
  storage (S3/GCS) on your Tavus account; this app doesn't set that up for
  you since it's genuinely optional infrastructure. See
  https://docs.tavus.io/sections/conversational-video-interface/quickstart/conversation-recordings
  if you want it.
