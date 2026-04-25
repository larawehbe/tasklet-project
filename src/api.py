"""FastAPI HTTP layer for the Tasklet support agent.

This module is a *thin* wrapper around the same Python code the CLI and
Streamlit UI use. It exposes the agent loop and services over HTTP so the
React dashboard in frontend/ can drive them.

Run with:
    python3 -m uvicorn src.api:app --reload --port 8000

Endpoints:
    GET  /api/users
    GET  /api/users/{user_id}/tickets[?status=&category=&priority=]
    GET  /api/users/{user_id}/conversation
    POST /api/users/{user_id}/chat
    POST /api/users/{user_id}/conversation/reset

Notes for students:
  * No auth here. user_id is just passed in from the URL — the React app
    picks it from a dropdown. In production you'd verify a session token
    and look up user_id from it. The security-critical bit (every service
    call uses user_id as its first parameter) is unchanged.
  * No streaming. /chat is a synchronous POST that runs the whole agent
    loop and returns the final text. Streaming SSE responses are a great
    next exercise; not needed for the demo.
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import run_turn
from src.conversation import Conversation
from src.db import get_connection
from src.models import Category, Priority, QueryFilters, Status
from src.query_service import list_tickets

load_dotenv()

app = FastAPI(title="Tasklet Support Agent API")

# CORS for safety. In dev the Vite proxy sends requests through localhost:5173
# so they look same-origin to the browser, but we keep this so curl from any
# origin still works.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_anthropic_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY is not set. Add it to .env.",
            )
        _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client


class ChatRequest(BaseModel):
    message: str


@app.get("/api/users")
def list_users():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, email, name FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/users/{user_id}/tickets")
def list_user_tickets(
    user_id: int,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
):
    conn = get_connection()

    try:
        filters = QueryFilters(
            status=Status(status) if status else None,
            category=Category(category) if category else None,
            priority=Priority(priority) if priority else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tickets = list_tickets(conn, user_id, filters)
    return [t.model_dump(mode="json") for t in tickets]


@app.get("/api/users/{user_id}/conversation")
def get_conversation(user_id: int):
    conn = get_connection()
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    conv = Conversation.load_or_create(conn, user_id)
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "messages": [m.model_dump(mode="json") for m in conv.messages],
    }


@app.post("/api/users/{user_id}/chat")
def chat(user_id: int, body: ChatRequest):
    conn = get_connection()
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    conversation = Conversation.load_or_create(conn, user_id)
    result = run_turn(
        client=_get_client(),
        conn=conn,
        conversation=conversation,
        user_input=body.message,
    )
    return {
        "final_text": result.final_text,
        "tool_call_count": result.tool_call_count,
        "messages": [m.model_dump(mode="json") for m in conversation.messages],
    }


@app.post("/api/users/{user_id}/conversation/reset")
def reset_conversation(user_id: int):
    conn = get_connection()
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    conv = Conversation.load_or_create(conn, user_id)
    conv.reset()
    return {"ok": True}
