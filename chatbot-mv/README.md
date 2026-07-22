# Chatbot MVP

A ChatGPT-style chatbot: clean interface, streaming responses, conversational
memory, and a single shareable URL — no login required. Built with FastAPI,
SQLite, and Gemini (Google) — using Google AI Studio's free tier, no credit
card required.

This implements the Day 1–7 plan: LLM chat, session memory, error handling,
a responsive UI, and history that survives across visits via an anonymous
session cookie.

## 1. Setup

```bash
cd backend
pip install -r requirements.txt
```

Get a **free** API key at https://aistudio.google.com/apikey (no credit card
required), then set it as an environment variable:

```bash
export GEMINI_API_KEY=your-gemini-key-here
```

Or copy `.env.example` to `.env` and load it with your process manager of choice
(e.g. `python-dotenv`, or your deploy platform's env var settings).

## 2. Run locally

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — that's it. The frontend is served by the same
FastAPI app, so there's nothing else to start.

## 3. How it works

- **Frontend** (`frontend/`): plain HTML/CSS/JS. Renders Markdown (via
  `marked`), streams the assistant's reply token-by-token, shows a typing
  indicator, and has a "New Chat" button.
- **Backend** (`backend/main.py`): FastAPI app with three endpoints:
  - `GET /api/history` — returns the current session's messages (sets a new
    session cookie on first visit)
  - `POST /api/chat` — takes `{"message": "..."}`, streams Gemini's reply back
    over Server-Sent Events, saves both sides of the exchange to SQLite
  - `POST /api/new-chat` — issues a fresh session_id (old history stays in
    the DB, just no longer attached to the active cookie)
- **Storage** (`backend/database.py`): one SQLite file (`chatbot.db`, created
  automatically). Each visitor gets a random `session_id` in an HTTP-only
  cookie — no accounts, no passwords, but each browser's history stays
  separate from everyone else's.
- **System prompt**: set in `main.py` as `SYSTEM_PROMPT` — edit it to change
  the assistant's personality.
- **Context limit**: `database.trim_history()` keeps only the most recent 30
  messages sent to the model, so long conversations don't blow the context
  window. (A token-counting trim, rather than a fixed message count, is a
  reasonable v2 upgrade if conversations get very long or verbose.)

## 4. What's already handled (the plan's "must-haves")

- ✅ Chat with the LLM, with conversation memory
- ✅ System prompt / personality
- ✅ Clean, responsive chat interface
- ✅ Loading (typing) indicator
- ✅ Error handling: empty input, API failures/timeouts, connection errors —
  all surface a clear message in the chat instead of crashing
- ✅ Streaming responses with Markdown + code block formatting
- ✅ Shareable via one URL, no login

## 5. A note on the free tier

Google's free Gemini API tier has rate limits (a cap on requests per minute
and per day) that can change without much notice. That's fine for a personal
MVP and demos — if you ever hit a "resource exhausted" style error, it just
means you've hit the free quota for the moment; wait a bit or check
https://aistudio.google.com for your current limits.

## 6. Deploying

Any host that runs a Python ASGI app works (Railway, Render, Fly.io, a plain
VPS, etc.). The essentials:

1. Set the `GEMINI_API_KEY` environment variable on the host.
2. Run `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Make sure the SQLite file's directory is writable and — if your host uses
   ephemeral filesystems (like most serverless platforms) — mount a
   persistent volume for `chatbot.db`, or history won't survive a restart.
4. Share the URL. Test it end-to-end once it's live (send a message, refresh
   the page to confirm history persists, try "New Chat").

## 7. Testing checklist (from the plan)

Manually verify before calling it done:

- [ ] Empty input submitted (blocked client-side; also rejected server-side)
- [ ] Very long conversation (confirm older messages get trimmed, not just
      truncated mid-response)
- [ ] Kill your network mid-request (confirms the connection-error message)
- [ ] Slow connection (throttle in devtools — confirm the typing indicator
      shows before tokens start arriving)
- [ ] Refresh the page mid-conversation (history should reload correctly)
- [ ] Click "New Chat" and confirm the old conversation is gone from view
      but still in `chatbot.db`

## 8. Optional features (v2, per the plan)

Not built here, intentionally — save for later if the MVP gets traction:
dark mode, PDF upload / RAG, voice input/output, exporting chats, switching
between multiple models, user accounts, or moving off SQLite to Postgres.
