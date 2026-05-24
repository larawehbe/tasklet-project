"""The agent loop — the heart of this app.

Algorithm:

  1. Append the user's message to the conversation.
  2. Call Claude with the full message history + tool schemas + system prompt.
  3. Parse the response:
        - text only → return it to the user; turn done.
        - text + tool_use → execute the tool, append the result, loop.
  4. Hard cap: at most MAX_TOOL_CALLS tool executions per user turn, so a
     mis-prompted Claude cannot put us in an infinite loop.

The system prompt asks Claude to issue at most ONE tool call per turn
(sequential mode). The loop here defensively handles 0-or-many tool_use
blocks per response anyway — better to handle the general case than to
crash if a future model version returns parallel calls.

run_turn takes an optional `on_tool_call` callback. The CLI uses it to
print tool calls when --verbose is on; the Streamlit UI uses it to capture
the per-turn log for the "thinking" panel.
"""

import sqlite3
from typing import Callable, Optional

from anthropic import Anthropic
from pydantic import BaseModel

from src.conversation import Conversation
from src.models import AgentMessage, ToolResult, ToolUse
from src.prompts import MODEL, SUMMARY_PROMPT, SYSTEM_PROMPT
from src.tools import TOOL_SCHEMAS, dispatch

MAX_TOKENS = 1024
MAX_TOOL_CALLS = 5
SUMMARY_THRESHOLD = 20   # summarize when conversation exceeds this many messages
SUMMARY_KEEP_RECENT = 6  # number of recent messages to keep verbatim


def _format_messages_as_text(messages: list[dict]) -> str:
    """Render Anthropic-format messages as plain text for the summarizer."""
    lines = []
    for m in messages:
        role = m["role"].upper()
        content = m["content"]
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
        elif isinstance(content, list):
            for block in content:
                t = block.get("type", "")
                if t == "text":
                    lines.append(f"{role}: {block['text']}")
                elif t == "tool_use":
                    lines.append(f"{role}: [called {block['name']}]")
                elif t == "tool_result":
                    lines.append(f"{role}: [tool result: {block.get('content', '')}]")
    return "\n".join(lines)


def _summarize_old_turns(client: Anthropic, old_messages: list[dict]) -> str:
    """Ask Claude to summarize older turns so they fit in a compact context note."""
    conversation_text = _format_messages_as_text(old_messages)
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": conversation_text}],
    )
    return response.content[0].text


class AgentTurnResult(BaseModel):
    """What one user turn produced."""

    final_text: str
    tool_call_count: int


def run_turn(
    client: Anthropic,
    conn: sqlite3.Connection,
    conversation: Conversation,
    user_input: str,
    on_tool_call: Optional[Callable[[ToolUse, ToolResult], None]] = None,
) -> AgentTurnResult:
    """Run one user turn from input through to the assistant's final text.

    The conversation is mutated in place: every new message (user, assistant
    text, tool_use, tool_result) is appended and persisted as we go. Even if
    we crash partway through, what was already written is durable.
    """
    conversation.append(AgentMessage(role="user", content=user_input))

    # If the history has grown long, summarize the older turns once before
    # entering the loop. The summary travels with every API call this turn,
    # replacing the old turns with a compact context note.
    summary: str | None = None
    if len(conversation.messages) > SUMMARY_THRESHOLD:
        old = conversation.to_anthropic_messages()[:-SUMMARY_KEEP_RECENT]
        summary = _summarize_old_turns(client, old)

    tool_call_count = 0

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=conversation.to_anthropic_messages(
                summary=summary, keep_recent=SUMMARY_KEEP_RECENT
            ),
        )

        text_parts: list[str] = []
        tool_uses: list[ToolUse] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(
                    ToolUse(id=block.id, name=block.name, input=dict(block.input))
                )

        assistant_text = "\n".join(text_parts) if text_parts else None
        conversation.append(
            AgentMessage(
                role="assistant",
                content=assistant_text,
                tool_calls=tool_uses,
            )
        )

        if response.stop_reason != "tool_use" or not tool_uses:
            return AgentTurnResult(
                final_text=assistant_text or "",
                tool_call_count=tool_call_count,
            )

        for tu in tool_uses:
            tool_call_count += 1
            tool_result = dispatch(conn, conversation.user_id, tu)
            if on_tool_call is not None:
                on_tool_call(tu, tool_result)
            conversation.append(AgentMessage(role="tool", tool_result=tool_result))

        if tool_call_count >= MAX_TOOL_CALLS:
            cap_msg = (
                f"I have reached my maximum of {MAX_TOOL_CALLS} tool calls "
                "for this turn. Could you refine your question or ask me to "
                "try again?"
            )
            conversation.append(AgentMessage(role="assistant", content=cap_msg))
            return AgentTurnResult(
                final_text=cap_msg, tool_call_count=tool_call_count
            )
