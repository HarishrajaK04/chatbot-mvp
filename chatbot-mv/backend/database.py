"""
Lightweight SQLite storage for the chatbot MVP.

Design (per plan): one SQLite file, no server. History is keyed by an
anonymous session_id (a random UUID stored in a browser cookie) so each
visitor's conversation stays separate, with no login/auth required.
"""

import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).parent / "chatbot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)"
    )
    conn.commit()
    conn.close()


def create_session() -> str:
    """Create a brand new session (used on first visit and on 'New Chat')."""
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
        (session_id, time.time()),
    )
    conn.commit()
    conn.close()
    return session_id


def session_exists(session_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row is not None


def add_message(session_id: str, role: str, content: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str) -> List[Dict[str, str]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def trim_history(messages: List[Dict[str, str]], max_messages: int = 30) -> List[Dict[str, str]]:
    """
    Keep the conversation inside the model's context window.

    Simple, predictable strategy for an MVP: keep only the most recent
    `max_messages` turns. (A token-counting trim is a natural v2 upgrade —
    see README.)
    """
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]
