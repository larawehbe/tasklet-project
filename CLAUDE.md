# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A teaching reference implementation of two multi-turn AI agents, built for a paid course aimed at software engineers learning to build agents on the Anthropic API. The codebase is the primary teaching artifact — a student should be able to read any file top-to-bottom and understand it.

**Support agent:** Files three tools — `create_ticket`, `list_tickets`, `get_ticket_by_id` — for the fictional SaaS "Tasklet". One Python core, three UIs (CLI, Streamlit, React via FastAPI).

**Finance agent:** A personal finance assistant with two read-only tools — `list_transactions`, `get_transaction_by_id` — for querying the user's transaction history. CLI only. Shares the same database, conversation, and security infrastructure as the support agent. Intended as a "same loop, different tools" teaching comparison.

## Common commands

```bash
# install (first time)
uv sync --extra dev
cp .env.example .env        # add ANTHROPIC_API_KEY

# database
uv run support-agent init-db                           # destructive: wipes + reseeds

# run support agent UIs
uv run support-agent chat --user-id 1 --verbose        # CLI, prints every tool call
uv run streamlit run src/app.py                        # Streamlit (port 8501)
uv run python -m uvicorn src.api:app --reload --port 8000   # FastAPI backend
( cd frontend && npm install && npm run dev )          # React dashboard (port 5173)

# run finance agent
uv run finance-agent chat --user-id 1                  # CLI
uv run finance-agent chat --user-id 1 --verbose        # prints every tool call
uv run finance-agent chat --user-id 1 --new            # start fresh conversation
uv run streamlit run src/finance_app.py                # Streamlit (port 8501)

# tests
uv run pytest                                          # all tests (support + finance)
uv run pytest -k security                              # just the security tests
uv run pytest tests/test_agent.py::test_run_turn_caps_tool_calls   # one test
uv run pytest tests/test_finance_service.py            # finance service tests only
uv run pytest tests/test_finance_tools.py              # finance tool dispatch tests only
```

The CLI also works as plain Python after activating the venv: `source .venv/bin/activate && python -m src.cli ...`.

## Architecture

### Support agent

Three UIs drive the same core; do not duplicate logic into a UI layer.

```
            CLI (cli.py) ──┐
       Streamlit (app.py) ─┼──> agent.run_turn ──> tools.dispatch ──> {ticket,query}_service ──> sqlite
       React (api.py + frontend/)
```

- **agent.py** owns the loop: append user message → call Claude → if tool_use, dispatch and append result, loop → return final text. Hard cap of 5 tool calls per turn.
- **tools.py** owns *both* the JSON tool schemas Claude sees and the `dispatch()` function that routes a `ToolUse` to the right service. Tool descriptions in this file are some of the most behavior-influential prompts in the system — when changing agent behavior, edit them before touching code.
- **conversation.py** owns persistence and the conversion between our internal three-role message log (`user`/`assistant`/`tool`) and Anthropic's two-role API shape. The `tool` role collapses to `user` + `tool_result` block at the API boundary.
- **prompts.py** holds `MODEL` and `SYSTEM_PROMPT`. The model id is pinned (`claude-sonnet-4-6`) — update it deliberately, not via "-latest" aliases.
- **api.py** is a *thin* FastAPI wrapper. It must not contain agent logic. If you find yourself adding business logic here, it belongs in agent.py / tools.py / a service.

### Finance agent

CLI only. Runs the identical agent loop with a different prompt, tool schemas, and service layer — compare these two files to see the teaching point:

```
       CLI (finance_cli.py) ──> finance_agent.run_finance_turn ──> finance_tools.finance_dispatch ──> finance_service ──> sqlite
```

- **finance_agent.py** — same loop algorithm as `agent.py`. Read them side by side.
- **finance_tools.py** — owns `FINANCE_TOOL_SCHEMAS` and `finance_dispatch()`. Two read-only tools: `list_transactions` and `get_transaction_by_id`. The security invariant (caller-supplied `user_id`, never from LLM input) is identical to the support agent.
- **finance_service.py** — raw parameterized SQL for reading transactions. `user_id` is always the first required parameter on every function; no overload accepts only a `transaction_id`.
- **finance_prompts.py** — `MODEL` and `SYSTEM_PROMPT` for the finance persona.
- **finance_models.py** — `Transaction`, `TransactionType`, `TransactionCategory`, `TransactionFilters` (Pydantic v2).
- **finance_cli.py** — thin CLI entry point (`finance-agent chat --user-id N`).

### The security invariant

This is the single most important rule in the codebase, and it applies to **both agents**:

1. The LLM never sees `user_id` in any tool schema — not in [src/tools.py](src/tools.py) nor in [src/finance_tools.py](src/finance_tools.py).
2. `dispatch()` / `finance_dispatch()` never reads `user_id` from `tool_use.input` — it uses the `user_id` parameter the caller passed in. Pydantic v2's default `extra="ignore"` also drops a stray `user_id` field, but dispatch is the load-bearing layer.
3. Every function in [src/ticket_service.py](src/ticket_service.py), [src/query_service.py](src/query_service.py), and [src/finance_service.py](src/finance_service.py) takes `user_id` as the **first required parameter**. There is no overload that accepts only a `ticket_id` or `transaction_id`. Do not add one.
4. `get_ticket_by_id` and `get_transaction_by_id` both return the same `None` whether the record doesn't exist OR belongs to another user. Do not "improve" the error message — the indistinguishability is intentional, to prevent existence leaks.

The SECURITY-labeled tests in [tests/test_tool_dispatch.py](tests/test_tool_dispatch.py) and [tests/test_finance_tools.py](tests/test_finance_tools.py) prove these invariants. Do not delete or weaken them.

## Hard constraints

These are pedagogical decisions, not historical accidents. Do not "modernize" past them:

- **No agent frameworks.** No LangChain, LlamaIndex, CrewAI, AutoGen. Direct Anthropic SDK with native tool use only — students must understand the agent loop themselves.
- **No ORM.** Raw `sqlite3` with parameterized SQL only. Students must see the SQL and the security model.
- **No LLM-generated SQL.** The LLM picks among pre-defined query functions via tool use. Adding a "free-form query" tool is a regression.
- **Sequential tool use.** The system prompt instructs Claude to issue one tool call per turn; the agent loop handles the general case defensively. Do not "optimize" by encouraging parallel tool calls.
- **Three support tools, no more.** `create_ticket`, `list_tickets`, `get_ticket_by_id`. Adding `update_ticket` or `delete_ticket` requires explicit user approval — refusal of those is part of the agent's specified behavior.
- **Two finance tools, read-only.** `list_transactions`, `get_transaction_by_id`. The finance agent cannot write, edit, or delete transactions — this is intentional. Do not add write tools.
- **No mocking the database in tests.** Tests use an in-memory SQLite from the same `schema.sql`. Real DB behavior, no mock-vs-prod drift.

## Things that look wrong but aren't

- **`check_same_thread=False`** in [src/db.py](src/db.py) is required for Streamlit. SQLite is single-writer; a teaching app has one user per process.
- **Custom `register_adapter`/`register_converter` for datetime** in [src/db.py](src/db.py) is required because Python 3.12 deprecated and 3.14 removed the implicit defaults. Removing them breaks `Ticket(**row)` parsing.
- **`messages.content` is a JSON blob**, not a relational structure. The conversation log is treated as an append-only event stream and never queried into.
- **CHECK constraints duplicate the Pydantic enums.** Defense in depth, on purpose.
- **Tailwind via CDN** in [frontend/index.html](frontend/index.html) is a pedagogical shortcut, not a missing build step. The course treats the React dashboard as a "ship a real frontend without knowing the framework" demo, so build setup is intentionally minimal.
- **`agent.run_turn` re-prompts even when Claude returns text + tool_use simultaneously.** This is correct: if there are tool_uses, the loop runs them and continues; the text from that turn is preserved in the assistant message.

## Testing notes

- No live API calls anywhere. [tests/test_agent.py](tests/test_agent.py) uses a tiny ducktyped fake Anthropic client — keep it tiny so students can read it.
- [tests/conftest.py](tests/conftest.py) provides an in-memory `conn` fixture, plus `seed_users`, `seed_tickets` (7-ticket controlled dataset), and `seed_transactions` (8-transaction controlled dataset across two users). All fixtures are distinct from `data/seed.sql`'s 100-item demo data.
- Finance tests live in [tests/test_finance_service.py](tests/test_finance_service.py) (20 tests, service layer) and [tests/test_finance_tools.py](tests/test_finance_tools.py) (18 tests, dispatch + security).
- Routing behavior (does Claude pick the right tool for a given prompt?) is verified interactively via the demo walkthrough in [README.md](README.md), not in pytest. Do not add a test that requires a live API key to CI.
