"""
Chatbot MVP backend.

FastAPI + SQLite + Gemini (Google), streaming responses over SSE.
Single public URL, no login: an anonymous session_id cookie keys each
visitor's history in SQLite.
"""

import json
import os
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 1024
SESSION_COOKIE = "chat_session_id"

SYSTEM_PROMPT = (
    "You are a helpful, friendly assistant in a simple chat app. "
    "Keep answers clear and conversational. Use Markdown (including code "
    "blocks with language tags) when it helps readability."
)

# Gemini client — reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment.
# Set it before running: export GEMINI_API_KEY=your-key-from-aistudio.google.com
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "missing-key"
)

app = FastAPI(title="Chatbot MVP")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    db.init_db()


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_or_create_session(request: Request) -> tuple[str, bool]:
    """Return (session_id, is_new). Reuses the cookie if it's a valid, known session."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id and db.session_exists(session_id):
        return session_id, False
    return db.create_session(), True


def to_gemini_contents(history: list[dict]) -> list[genai_types.Content]:
    """Gemini uses role 'model' for the assistant, not 'assistant'."""
    role_map = {"user": "user", "assistant": "model"}
    return [
        genai_types.Content(
            role=role_map[msg["role"]],
            parts=[genai_types.Part(text=msg["content"])],
        )
        for msg in history
    ]


# ---------------------------------------------------------------------------
# Routes: frontend
# ---------------------------------------------------------------------------

@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ---------------------------------------------------------------------------
# Routes: API
# ---------------------------------------------------------------------------

@app.get("/api/history")
def api_history(request: Request):
    """Return existing history for the current session (used on page load)."""
    session_id, is_new = get_or_create_session(request)
    history = [] if is_new else db.get_history(session_id)
    response = JSONResponse({"history": history})
    if is_new:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")
    return response


@app.post("/api/new-chat")
def api_new_chat():
    """Start a fresh conversation — new session_id, old history stays in the DB untouched."""
    session_id = db.create_session()
    response = JSONResponse({"ok": True})
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")
    return response


@app.post("/api/chat")
def api_chat(chat_request: ChatRequest, request: Request):
    """Send a message, stream Gemini's reply back as Server-Sent Events."""
    user_message = chat_request.message.strip()

    if not user_message:
        return JSONResponse({"error": "Message cannot be empty."}, status_code=400)

    session_id, is_new = get_or_create_session(request)

    db.add_message(session_id, "user", user_message)
    history = db.get_history(session_id)
    history = db.trim_history(history)

    def event_stream():
        full_reply = ""
        try:
            contents = to_gemini_contents(history)
            stream = client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
            for chunk in stream:
                if chunk.text:
                    full_reply += chunk.text
                    yield f"data: {json.dumps({'delta': chunk.text})}\n\n"

            if not full_reply:
                # Model returned an empty response (e.g. blocked by safety filters)
                yield f"data: {json.dumps({'error': 'The model returned an empty response. Try rephrasing your message.'})}\n\n"
                return

            db.add_message(session_id, "assistant", full_reply)
            yield f"data: {json.dumps({'done': True})}\n\n"

        except genai_errors.APIError as e:
            # Covers rate limits (429), auth errors (401/403), server errors (5xx), etc.
            yield f"data: {json.dumps({'error': f'The AI service returned an error ({e.code}). Please try again.'})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'error': 'Something went wrong generating a response. Please try again.'})}\n\n"

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    if is_new:
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax")
    return response
