# Tasklet Support Agent

A teaching reference implementation for building production AI agents with the Anthropic Claude API.

The "Tasklet" support agent is a multi-turn conversational assistant for a fictional B2B project management SaaS. It demonstrates:

- Native Claude tool use — no LangChain, LlamaIndex, or framework abstractions
- Strict per-user data scoping enforced at the service layer
- Pre-defined query functions chosen by the LLM (no LLM-generated SQL)
- Multi-turn conversation state managed explicitly, persisted to SQLite
- Raw parameterized SQL via Python's `sqlite3` module — no ORM

## Quickstart

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    uv sync --extra dev
    cp .env.example .env       # then edit and add your ANTHROPIC_API_KEY
    uv run support-agent init-db

After init you have `data/tasklet.db` populated with 5 demo users and 100 sample tickets.

### CLI

    uv run support-agent list-users                    # see who you can chat as
    uv run support-agent chat --user-id 1              # interactive chat (resumes history)
    uv run support-agent chat --user-id 1 --new        # start a fresh conversation
    uv run support-agent chat --user-id 1 --verbose    # print every tool call inline

### Streamlit UI

    uv run streamlit run src/app.py

Pick a user from the sidebar, chat in the main panel. Each tool call is shown in a collapsible expander so you can see exactly what the agent did. The sidebar table refreshes after every turn so you can watch DB changes happen live.

### React dashboard (FastAPI + Vite)

A polished dashboard, useful as a course demo of "how to ship a real frontend without knowing the framework yet." The Python agent is unchanged — the React UI just talks to it over HTTP.

Two terminals:

**Terminal 1 — backend (FastAPI):**

    .venv/bin/python3 -m uvicorn src.api:app --reload --port 8000

**Terminal 2 — frontend (Vite):**

    cd frontend
    npm install         # only the first time
    npm run dev

Open http://localhost:5173. The Vite dev server proxies `/api/*` to the FastAPI backend, so the React code never has to know what host the API is on.

What students see: the same agent loop, the same tools, the same security model — driven from a different UI. The lesson is that *the agent is a Python service, and any frontend that speaks HTTP can drive it*.

### Tests

    uv run pytest                       # full suite
    uv run pytest -k security           # just the security tests
    uv run pytest tests/test_agent.py   # agent loop only

The suite has no live API calls — `tests/test_agent.py` mocks the Anthropic client. Routing behavior (does Claude pick the right tool for a given user prompt?) is verified interactively via the demo walkthrough below.

## How it works

### The agent loop

The agent is implemented in [src/agent.py](src/agent.py) and is small enough to read in one sitting:

1. Append the user's message to the conversation.
2. Call Claude with the full message history, the tool schemas, and the system prompt.
3. If the response is text only — done, return it to the user.
4. If the response includes a `tool_use` block — execute the tool, append the result, loop back to step 2.
5. Cap at 5 tool calls per turn to prevent runaway behavior.

The system prompt instructs Claude to issue at most one tool call per turn (sequential mode), so the loop iterates linearly: text → tool → result → text → tool → result ... until Claude is done.

### The three tools

| Tool                | Purpose                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------- |
| `create_ticket`     | File a new ticket. Asks clarifying questions (in plain text) if any required field is missing. |
| `list_tickets`      | Return the user's tickets, optionally filtered by status, category, priority, or date range. |
| `get_ticket_by_id`  | Look up one ticket by id. Returns "not found" if it doesn't exist or belongs to another user. |

The LLM picks among them based on the system prompt and tool descriptions in [src/tools.py](src/tools.py). Those descriptions are some of the most behavior-influential code in the whole app — when you tweak how the agent acts, you are usually tweaking those, not the algorithm.

### The security model

Three layers of defense, all tested:

1. **The LLM never sees `user_id` in any tool schema.** It is not an input parameter to any of the three tools. The LLM cannot ask for it.
2. **`dispatch()` ignores any `user_id` the LLM tries to inject.** Every service call uses the authenticated `user_id` parameter the dispatch function received. Pydantic v2's default `extra="ignore"` would already drop a stray `user_id`, but `dispatch()` also never references it directly — defense in depth. See [tests/test_tool_dispatch.py](tests/test_tool_dispatch.py) for the proofs.
3. **The service layer takes `user_id` as the first required parameter on every read and write.** There is no overload that takes only a `ticket_id`. It is impossible to write a query that crosses tenant boundaries by accident.

`get_ticket_by_id` returns the same `found: false` response whether the ticket doesn't exist OR belongs to another user. This avoids leaking existence information.

### Conversation persistence

Conversations live in the `conversations` and `messages` tables. Each turn appends to the message log. Reopening the CLI or refreshing the Streamlit page resumes the most recent conversation for that user. `--new` (CLI) or "Reset conversation" (Streamlit) clears the history.

The `messages.content` column stores a JSON-encoded `AgentMessage`. We treat the message log as an append-only event stream — never querying inside it — so a single TEXT blob is enough.

### Observability

This implementation does not include structured logging or tracing. It is a teaching reference, not a production deployment. In a real system you would:

- Log every tool call to a structured logger (JSON, with `conversation_id`, `user_id`, tool name, latency, success).
- Track Anthropic token usage per turn (`response.usage.input_tokens` / `output_tokens`) and forward to a metrics backend.
- Trace via OpenTelemetry: one span per agent turn, child spans per tool call.
- Sample full conversations for human review.

The `--verbose` flag on the CLI prints tool calls inline; the Streamlit UI shows them in collapsible expanders. Both are demo affordances — they help you watch one conversation, not many.

## Demo walkthrough

After `init-db`, run:

    uv run support-agent chat --user-id 1 --verbose

…and try these prompts in order. They exercise routing, multi-turn refinement, clarifying questions, and refusal:

1. **List**: `what tickets do I have?` — should call `list_tickets` with no filters and summarize ~20 tickets in plain English.
2. **Filter**: `just the urgent ones` — should call `list_tickets` again with priority=urgent.
3. **Refine**: `actually only the open ones` — should add status=open to the filter.
4. **Lookup by id**: `what is the status of ticket 5?` — should call `get_ticket_by_id`.
5. **Lookup of someone else's ticket**: `what about ticket 50?` (user 1 owns ids 1–20) — should report not found.
6. **Create with full info**: `Open a high priority bug: dashboard crashes on Firefox 130 when I open the sprint board` — should call `create_ticket` directly.
7. **Create with missing info**: `I want to file a ticket about my invoice` — should ask for more details before calling the tool.
8. **Refuse modification**: `delete ticket 1` — should refuse politely.
9. **Refuse out-of-scope**: `email this to support` — should say it cannot, suggest the web app.
10. **Ambiguous reference**: `what about that one?` (with no prior context) — should ask which ticket.

The same flow works in the Streamlit UI — flip "Logged in as" to a different user mid-session to verify isolation.

## Project layout

    .
    ├── pyproject.toml
    ├── README.md
    ├── data/
    │   ├── schema.sql                 # CREATE TABLE statements
    │   ├── seed.sql                   # 5 users, 100 tickets
    │   └── tasklet.db                 # gitignored, created by init-db
    ├── src/
    │   ├── models.py                  # Pydantic models — input contracts
    │   ├── db.py                      # connection management + init
    │   ├── ticket_service.py          # create_ticket
    │   ├── query_service.py           # list_tickets, get_ticket_by_id
    │   ├── tools.py                   # tool schemas + dispatch
    │   ├── prompts.py                 # system prompt, model id
    │   ├── conversation.py            # Conversation class with persistence
    │   ├── agent.py                   # the agent loop
    │   ├── cli.py                     # Typer CLI (`support-agent ...`)
    │   └── app.py                     # Streamlit UI
    ├── tests/
    │   ├── conftest.py                # in-memory DB fixtures
    │   ├── test_ticket_service.py
    │   ├── test_query_service.py
    │   ├── test_tool_dispatch.py      # routing + 3 SECURITY tests
    │   ├── test_conversation.py
    │   └── test_agent.py              # agent loop with mocked Anthropic client
    └── scripts/
        └── init_db.py                 # equivalent to `support-agent init-db`

## Future improvements (intentionally not implemented)

The current code is a teaching reference, not a production deployment. Things you would add for production:

- **Prompt caching.** Mark the system prompt and tool schemas as `cache_control={"type": "ephemeral"}` in the API call. ~90% cost reduction on multi-turn sessions. See the Anthropic docs for prompt caching.
- **Conversation history compaction.** Long sessions will eventually exceed the context window. In production you would summarize older turns and keep a sliding window of recent ones.
- **Token-budget enforcement.** Track cumulative input/output tokens per session and fail gracefully when hitting an org-level cap.
- **Structured logging + tracing.** See the Observability section above.
- **Real authentication.** The user dropdown in Streamlit is a demo affordance; in production you would integrate with whatever IdP your SaaS uses.
- **Refusal red-teaming.** The current refusal behavior depends entirely on the system prompt. A real deployment would add adversarial test cases and possibly a content filter on outputs.
