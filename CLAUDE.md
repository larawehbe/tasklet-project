# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A teaching reference implementation of a multi-turn AI support agent, built for a paid course aimed at software engineers learning to build agents on the Anthropic API. The codebase is the primary teaching artifact — a student should be able to read any file top-to-bottom and understand it.

The agent uses five tools — `create_ticket`, `list_tickets`, `get_ticket_by_id`, `update_ticket_status`, and `search_knowledge_base` (RAG) — for the fictional SaaS "Tasklet". One Python core, three UIs (CLI, Streamlit, React via FastAPI).

## Common commands

```bash
# install (first time)
uv sync --extra dev
cp .env.example .env        # add ANTHROPIC_API_KEY

# database
uv run support-agent init-db                           # destructive: wipes + reseeds

# knowledge base (RAG index) — run once after install, or after editing articles in data/knowledge/
uv run python scripts/build_knowledge_base.py          # first run downloads ~80MB model

# run a UI
uv run support-agent list-users                        # see seeded user ids
uv run support-agent chat --user-id 1                  # CLI, resumes last conversation
uv run support-agent chat --user-id 1 --new            # CLI, force a fresh conversation
uv run support-agent chat --user-id 1 --verbose        # CLI, prints every tool call
uv run streamlit run src/app.py                        # Streamlit (port 8501)
uv run python -m uvicorn src.api:app --reload --port 8000   # FastAPI backend
( cd frontend && npm install && npm run dev )          # React dashboard (port 5173)

# tests
uv run pytest                                          # all 49 tests
uv run pytest -k security                              # just the security tests
uv run pytest tests/test_agent.py::test_run_turn_caps_tool_calls   # one test
```

The CLI also works as plain Python after activating the venv: `source .venv/bin/activate && python -m src.cli ...`.

## Architecture

The agent core is a small set of Python modules. Three UIs drive the same core; do not duplicate logic into a UI layer.

```
            CLI (cli.py) ──┐
       Streamlit (app.py) ─┼──> agent.run_turn ──> tools.dispatch ──┬──> {ticket,query}_service ──> sqlite
       React (api.py + frontend/)                                    └──> knowledge_service ──> chromadb
```

- **agent.py** owns the loop: append user message → call Claude → if tool_use, dispatch and append result, loop → return final text. Hard cap of 5 tool calls per turn.
- **tools.py** owns *both* the JSON tool schemas Claude sees and the `dispatch()` function that routes a `ToolUse` to the right service. Tool descriptions in this file are some of the most behavior-influential prompts in the system — when changing agent behavior, edit them before touching code.
- **conversation.py** owns persistence and the conversion between our internal three-role message log (`user`/`assistant`/`tool`) and Anthropic's two-role API shape. The `tool` role collapses to `user` + `tool_result` block at the API boundary.
- **prompts.py** holds `MODEL` and `SYSTEM_PROMPT`. The model id is pinned (`claude-sonnet-4-6`) — update it deliberately, not via "-latest" aliases.
- **models.py** is the contract layer: every LLM tool input (`TicketCreate`, `QueryFilters`, `TicketStatusUpdate`) and every DB record (`Ticket`, `User`, `AgentMessage`) is a Pydantic model. If the LLM emits a bad enum or date, `ValidationError` propagates as a `tool_result` so Claude can self-correct.
- **api.py** is a *thin* FastAPI wrapper. It must not contain agent logic. If you find yourself adding business logic here, it belongs in agent.py / tools.py / a service.
- **knowledge_service.py** owns the RAG pipeline: `build_index()` (offline, reads `data/knowledge/*.md`, embeds with `all-MiniLM-L6-v2`, stores in ChromaDB) and `search(query)` (runtime, embeds query and returns top-k chunks). Does not use `user_id` — knowledge base is shared across all users.

### The security invariant

This is the single most important rule in the codebase, and it spans multiple files:

1. The LLM never sees `user_id` in any tool schema in [src/tools.py](src/tools.py).
2. `dispatch()` never reads `user_id` from `tool_use.input` — it uses the `user_id` parameter the caller passed in. Pydantic v2's default `extra="ignore"` also drops a stray `user_id` field, but dispatch is the load-bearing layer.
3. Every function in [src/ticket_service.py](src/ticket_service.py) and [src/query_service.py](src/query_service.py) takes `user_id` as the **first required parameter**. There is no overload that accepts only a `ticket_id`. Do not add one.
4. `get_ticket_by_id` returns the same `None` whether the ticket doesn't exist OR belongs to another user. Do not "improve" the error message — the indistinguishability is intentional, to prevent existence leaks.
5. `search_knowledge_base` intentionally receives no `user_id` — it queries shared product docs, not per-user data. This is the one tool where tenant scoping does not apply.

The three SECURITY-labeled tests in [tests/test_query_service.py](tests/test_query_service.py) prove (1)–(3). Do not delete or weaken them.

## Hard constraints

These are pedagogical decisions, not historical accidents. Do not "modernize" past them:

- **No agent frameworks.** No LangChain, LlamaIndex, CrewAI, AutoGen. Direct Anthropic SDK with native tool use only — students must understand the agent loop themselves.
- **No ORM.** Raw `sqlite3` with parameterized SQL only. Students must see the SQL and the security model.
- **No LLM-generated SQL.** The LLM picks among pre-defined query functions via tool use. Adding a "free-form query" tool is a regression.
- **Sequential tool use.** The system prompt instructs Claude to issue one tool call per turn; the agent loop handles the general case defensively. Do not "optimize" by encouraging parallel tool calls.
- **Five tools, no more.** `create_ticket`, `list_tickets`, `get_ticket_by_id`, `update_ticket_status`, `search_knowledge_base`. Adding `delete_ticket` or any new mutation tool requires explicit user approval — the agent deliberately cannot delete data.
- **No mocking the database in tests.** Tests use an in-memory SQLite from the same `schema.sql`. Real DB behavior, no mock-vs-prod drift.

## Things that look wrong but aren't

- **`check_same_thread=False`** in [src/db.py](src/db.py) is required for Streamlit. SQLite is single-writer; a teaching app has one user per process.
- **Custom `register_adapter`/`register_converter` for datetime** in [src/db.py](src/db.py) is required because Python 3.12 deprecated and 3.14 removed the implicit defaults. Removing them breaks `Ticket(**row)` parsing.
- **`messages.content` is a JSON blob**, not a relational structure. The conversation log is treated as an append-only event stream and never queried into.
- **CHECK constraints duplicate the Pydantic enums.** Defense in depth, on purpose.
- **Tailwind via CDN** in [frontend/index.html](frontend/index.html) is a pedagogical shortcut, not a missing build step. The course treats the React dashboard as a "ship a real frontend without knowing the framework" demo, so build setup is intentionally minimal.
- **`agent.run_turn` re-prompts even when Claude returns text + tool_use simultaneously.** This is correct: if there are tool_uses, the loop runs them and continues; the text from that turn is preserved in the assistant message.
- **`data/chroma/` is committed to the repo.** The pre-built ChromaDB index is checked in so the app works immediately after `uv sync` without running `build_knowledge_base.py`. Re-run the build script only if you edit articles in `data/knowledge/`.
- **The embedding model in `knowledge_service.py` is a lazy singleton.** `_model` and `_collection` start as `None` and are initialized on first use to avoid loading the 80MB model at every CLI invocation (e.g., `init-db`). This is intentional, not a threading oversight.

## Testing notes

- 49 tests, no live API calls. [tests/test_agent.py](tests/test_agent.py) uses a tiny ducktyped fake Anthropic client — keep it tiny so students can read it.
- [tests/conftest.py](tests/conftest.py) provides an in-memory `conn` fixture, plus `seed_users` and `seed_tickets` (a 7-ticket controlled dataset, distinct from `data/seed.sql`'s 100-ticket demo data).
- [tests/test_knowledge_service.py](tests/test_knowledge_service.py) patches `KNOWLEDGE_DIR` and `CHROMA_DIR` to use `tmp_path` — tests are self-contained and don't touch `data/chroma/`. These tests load the embedding model locally (~1–2s extra).
- Routing behavior (does Claude pick the right tool for a given prompt?) is verified interactively via the demo walkthrough in [README.md](README.md), not in pytest. Do not add a test that requires a live API key to CI.
