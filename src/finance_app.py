"""Streamlit UI for the personal finance agent.

Run with:
    uv run streamlit run src/finance_app.py

Layout:
  * Sidebar: pick which seed user to log in as, and a live table of that
    user's recent transactions (updates after every turn).
  * Main panel: the chat with the finance agent. Each tool call and tool
    result is shown in a collapsible expander — same teaching feature as
    the support agent UI.
  * "Reset conversation" wipes message history but keeps the conversation
    row (so resuming works on the next page load).

Compare this file with src/app.py to see how swapping run_turn for
run_finance_turn (and tickets for transactions in the sidebar) produces a
completely different agent experience with identical Streamlit mechanics.
"""

import json
import os

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from src.conversation import Conversation
from src.db import get_connection
from src.finance_agent import run_finance_turn
from src.finance_models import TransactionFilters
from src.finance_service import list_transactions
from src.models import AgentMessage, ToolResult, ToolUse

load_dotenv()

st.set_page_config(page_title="Finance Agent", layout="wide")

conn = get_connection()


def _render_message(msg: AgentMessage) -> None:
    """Render one message in the chat history."""
    if msg.role == "user":
        with st.chat_message("user"):
            st.write(msg.content)
    elif msg.role == "assistant":
        with st.chat_message("assistant"):
            if msg.content:
                st.write(msg.content)
            for tu in msg.tool_calls:
                with st.expander(f"Tool call: {tu.name}", expanded=False):
                    st.code(json.dumps(tu.input, indent=2), language="json")
    elif msg.role == "tool":
        tr = msg.tool_result
        label = "Tool result" + (" (error)" if tr and tr.is_error else "")
        with st.expander(label, expanded=False):
            content = tr.content if tr else ""
            try:
                pretty = json.dumps(json.loads(content), indent=2)
                st.code(pretty, language="json")
            except json.JSONDecodeError:
                st.write(content)


# ---------- sidebar: user selection + live transaction table ----------

users = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
if not users:
    st.error(
        "No seed users found. Run `uv run support-agent init-db` first, then "
        "reload this page."
    )
    st.stop()

with st.sidebar:
    st.title("Finance Agent")
    options = {f"{u['name']} (id {u['id']})": u["id"] for u in users}
    chosen_label = st.selectbox("Logged in as", list(options.keys()))
    user_id = options[chosen_label]

    if st.button("Reset conversation", use_container_width=True):
        if "finance_conversation" in st.session_state:
            st.session_state.finance_conversation.reset()
        st.rerun()

    st.divider()
    st.subheader("Transactions")
    recent = list_transactions(conn, user_id, TransactionFilters())
    if recent:
        st.caption(f"{len(recent)} total — newest first")
        st.dataframe(
            [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "type": t.type.value,
                    "category": t.category.value,
                    "merchant": t.merchant or "",
                    "amount": f"${t.amount:.2f}",
                }
                for t in recent
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.write("No transactions found.")


# ---------- main panel: chat ----------

if (
    "finance_conversation" not in st.session_state
    or st.session_state.get("finance_active_user_id") != user_id
):
    st.session_state.finance_conversation = Conversation.load_or_create(conn, user_id)
    st.session_state.finance_active_user_id = user_id

conversation: Conversation = st.session_state.finance_conversation

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    st.error(
        "ANTHROPIC_API_KEY is not set. Add it to .env and restart Streamlit."
    )
    st.stop()

client = Anthropic(api_key=api_key)

st.title(f"Hi, {chosen_label.split(' (')[0]}")
st.caption(
    "Ask about your transactions — spending by category, merchant lookups, "
    "income history, date-range summaries, and more. "
    "Tool calls are shown inline so you can see exactly what the agent did."
)

for msg in conversation.messages:
    _render_message(msg)


def _on_tool_call(_tu: ToolUse, _tr: ToolResult) -> None:
    pass


if prompt := st.chat_input("Ask the finance agent..."):
    with st.spinner("Thinking..."):
        try:
            run_finance_turn(
                client=client,
                conn=conn,
                conversation=conversation,
                user_input=prompt,
                on_tool_call=_on_tool_call,
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"{type(e).__name__}: {e}")
    st.rerun()
