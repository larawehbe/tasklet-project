"""The finance agent loop.

Same algorithm as the support agent (src/agent.py), applied to the finance
domain. Compare the two files side by side to see how swapping out the
prompt, tool schemas, and dispatch function produces a completely different
agent persona with identical loop mechanics.

Algorithm:

  1. Append the user's message to the conversation.
  2. Call Claude with the full message history + finance tool schemas + prompt.
  3. Parse the response:
        - text only → return it to the user; turn done.
        - text + tool_use → execute the finance tool, append the result, loop.
  4. Hard cap: at most MAX_TOOL_CALLS tool executions per user turn.
"""

import sqlite3
from typing import Callable, Optional

from anthropic import Anthropic
from pydantic import BaseModel

from src.conversation import Conversation
from src.finance_prompts import MODEL, SYSTEM_PROMPT
from src.finance_tools import FINANCE_TOOL_SCHEMAS, finance_dispatch
from src.models import AgentMessage, ToolResult, ToolUse

MAX_TOKENS = 1024
MAX_TOOL_CALLS = 5


class AgentTurnResult(BaseModel):
    """What one user turn produced."""

    final_text: str
    tool_call_count: int


def run_finance_turn(
    client: Anthropic,
    conn: sqlite3.Connection,
    conversation: Conversation,
    user_input: str,
    on_tool_call: Optional[Callable[[ToolUse, ToolResult], None]] = None,
) -> AgentTurnResult:
    """Run one user turn from input through to the assistant's final text.

    The conversation is mutated in place: every new message (user, assistant
    text, tool_use, tool_result) is appended and persisted as we go.
    """
    conversation.append(AgentMessage(role="user", content=user_input))

    tool_call_count = 0

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=FINANCE_TOOL_SCHEMAS,
            messages=conversation.to_anthropic_messages(),
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
            tool_result = finance_dispatch(conn, conversation.user_id, tu)
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
