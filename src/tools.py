"""Tool definitions and dispatch.

This module is the bridge between the LLM and the service layer. It owns:

  1. TOOL_SCHEMAS — the JSON sent to Anthropic on every API call. The
     schemas tell Claude what tools exist, what arguments they take, and
     (most importantly) WHEN to use each one. The descriptions here are
     among the most influential prompts in the whole system; tweak them
     to change agent behavior.

  2. dispatch() — given a parsed ToolUse from a Claude response, executes
     the right service function and packages the result as a ToolResult to
     feed back on the next agent loop iteration.

Security: dispatch() ALWAYS uses the user_id passed in by the caller (the
authenticated session) and NEVER reads user_id from the LLM's tool input.
A test in tests/test_query_service.py asserts this directly. If the LLM
tries to pass user_id, it is silently dropped (Pydantic ignores extra
fields by default in v2, and dispatch() never references the raw input
for user_id either way).

Note: search_knowledge_base does not use user_id at all — the knowledge
base is shared product documentation, not per-user data. This is intentional.
"""

import json
import sqlite3

from pydantic import ValidationError

from src.models import (
    QueryFilters,
    Status,
    TicketCreate,
    TicketStatusUpdate,
    ToolResult,
    ToolUse,
)
from src.query_service import get_ticket_by_id, list_tickets
from src.ticket_service import create_ticket, update_ticket_status

# ---------- NEW: import the knowledge base search function ----------
from src.knowledge_service import search as search_knowledge_base
# This is the function that embeds the query and searches ChromaDB.
# It returns a list of dicts with "text", "source", and "score" keys.
# No user_id needed — knowledge base is shared across all users.
# --------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "create_ticket",
        "description": (
            "Create a new support ticket on behalf of the current user. "
            "Use this when the user wants to file a new issue, request, or question. "
            "Before calling this tool, make sure you have collected all four required "
            "fields: a clear short title, a detailed description, the right category, "
            "and an appropriate priority. If anything is missing or ambiguous, ask the "
            "user a clarifying question instead of calling the tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short, specific title for the ticket. Max 200 characters.",
                },
                "description": {
                    "type": "string",
                    "description": "Full description of the issue, request, or question.",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "bug_report",
                        "feature_request",
                        "billing",
                        "integration_issue",
                        "how_to_question",
                    ],
                    "description": (
                        "Category of the ticket. Pick the closest match: "
                        "bug_report for things that are broken; "
                        "feature_request for new capabilities; "
                        "billing for invoices, plans, or payment; "
                        "integration_issue for problems with external systems "
                        "(GitHub, Slack, Jira, etc.); "
                        "how_to_question for usage questions where nothing is broken."
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": (
                        "Priority. Pick urgent for outages or anything blocking the user "
                        "right now; high for serious problems with workarounds; "
                        "medium for normal day-to-day issues; low for nice-to-haves "
                        "and minor questions."
                    ),
                },
            },
            "required": ["title", "description", "category", "priority"],
        },
    },
    {
        "name": "list_tickets",
        "description": (
            "Return tickets belonging to the current user, optionally filtered. "
            "Use this for 'show me my tickets', 'what's open', 'any urgent bugs', "
            "and similar lookups. All filters are optional — omit a filter to leave "
            "that dimension unconstrained. Results are automatically scoped to the "
            "current user; you do not need to (and cannot) specify a user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "open",
                        "in_progress",
                        "waiting_on_customer",
                        "resolved",
                        "closed",
                    ],
                    "description": "Restrict to tickets with this status.",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "bug_report",
                        "feature_request",
                        "billing",
                        "integration_issue",
                        "how_to_question",
                    ],
                    "description": "Restrict to tickets in this category.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Restrict to tickets at this priority.",
                },
                "created_after": {
                    "type": "string",
                    "format": "date-time",
                    "description": (
                        "ISO 8601 datetime. Only return tickets created at or after "
                        "this moment. Example: '2026-04-01T00:00:00'."
                    ),
                },
                "created_before": {
                    "type": "string",
                    "format": "date-time",
                    "description": (
                        "ISO 8601 datetime. Only return tickets created at or before "
                        "this moment. Example: '2026-04-25T23:59:59'."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "description": (
                        "Optional cap on number of results, useful for "
                        "'my 5 most recent'. Omit to return all matches."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_ticket_by_id",
        "description": (
            "Look up one specific ticket by its numeric id. "
            "Returns the full ticket if it exists and is owned by the current user, "
            "otherwise returns a 'not found' response. Use this when the user "
            "references a specific ticket id (e.g., 'what's the status of ticket 42')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "integer",
                    "description": "The numeric id of the ticket to look up.",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "update_ticket_status",
        "description": (
            "Update the status of an existing ticket owned by the current user. "
            "Use this when the user asks to close a ticket, mark it resolved, "
            "reopen it, or move it to any other status. "
            "Always confirm the ticket id and intended new status with the user "
            "before calling this tool — a status change cannot be undone from chat. "
            "Returns the updated ticket on success, or 'not found' if the ticket "
            "does not exist or belongs to another user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "integer",
                    "description": "The numeric id of the ticket to update.",
                },
                "new_status": {
                    "type": "string",
                    "enum": [
                        "open",
                        "in_progress",
                        "waiting_on_customer",
                        "resolved",
                        "closed",
                    ],
                    "description": (
                        "The status to set. "
                        "open — ticket is active and unassigned; "
                        "in_progress — someone is actively working on it; "
                        "waiting_on_customer — blocked on a response from the user; "
                        "resolved — the issue has been fixed or answered; "
                        "closed — ticket is done and archived."
                    ),
                },
            },
            "required": ["ticket_id", "new_status"],
        },
    },
    # ------------------------------------------------------------------
    # NEW TOOL: search_knowledge_base
    #
    # This is the RAG tool. When Claude sees a product question like
    # "how do I connect Jira?" it calls this tool instead of filing a
    # ticket or saying "I don't know."
    #
    # The description is critical — it tells Claude WHEN to use this
    # tool vs the others. Notice:
    #   - "how do I..." → search_knowledge_base
    #   - "my Jira sync is broken" → create_ticket (something is wrong)
    #   - "show me my tickets" → list_tickets (user data, not docs)
    #
    # The query parameter is a short search string, NOT the full user
    # message. Claude should extract the key topic. For example, if the
    # user says "hey can you tell me how to set up the slack integration
    # for my team?" Claude should pass query="Slack integration setup".
    # ------------------------------------------------------------------
    {
        "name": "search_knowledge_base",
        "description": (
            "Search Tasklet's product documentation and help articles. "
            "Use this when the user asks a how-to question about Tasklet features, "
            "setup instructions, integration guides, billing policies, or general "
            "product knowledge — anything where the answer is in the docs rather "
            "than in the user's own ticket data. "
            "Do NOT use this for ticket lookups, ticket creation, or status updates. "
            "Pass a short, specific search query — extract the key topic from the "
            "user's question rather than passing the full message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Short search query describing what the user wants to know. "
                        "Examples: 'Jira integration setup', 'billing seat management', "
                        "'API rate limits', 'SCIM Okta provisioning'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
]


def dispatch(
    conn: sqlite3.Connection, user_id: int, tool_use: ToolUse
) -> ToolResult:
    """Execute the named tool and return a ToolResult to feed back to the LLM.

    The user_id parameter is the authenticated user's id. This function NEVER
    reads user_id from tool_use.input — even if the LLM tries to pass one,
    it is ignored. Tests prove this.

    Note: search_knowledge_base does not use user_id or conn at all.
    The knowledge base is shared product documentation. This is the one
    tool where tenant scoping does not apply — and that's correct,
    because there's no user data involved.
    """
    name = tool_use.name
    raw_input = tool_use.input

    try:
        if name == "create_ticket":
            ticket_create = TicketCreate(**raw_input)
            ticket = create_ticket(conn, user_id, ticket_create)
            return _ok(tool_use.id, ticket.model_dump(mode="json"))

        if name == "list_tickets":
            filters = QueryFilters(**raw_input)
            tickets = list_tickets(conn, user_id, filters)
            return _ok(
                tool_use.id,
                {
                    "count": len(tickets),
                    "tickets": [t.model_dump(mode="json") for t in tickets],
                },
            )

        if name == "get_ticket_by_id":
            ticket_id = raw_input.get("ticket_id")
            if not isinstance(ticket_id, int) or isinstance(ticket_id, bool):
                return _err(
                    tool_use.id,
                    "ticket_id is required and must be an integer.",
                )
            ticket = get_ticket_by_id(conn, user_id, ticket_id)
            if ticket is None:
                return _ok(
                    tool_use.id,
                    {"found": False, "ticket_id": ticket_id},
                )
            return _ok(
                tool_use.id,
                {"found": True, "ticket": ticket.model_dump(mode="json")},
            )

        if name == "update_ticket_status":
            params = TicketStatusUpdate(**raw_input)
            ticket = update_ticket_status(
                conn, user_id, params.ticket_id, params.new_status
            )
            if ticket is None:
                return _ok(
                    tool_use.id,
                    {"found": False, "ticket_id": params.ticket_id},
                )
            return _ok(
                tool_use.id,
                {"found": True, "ticket": ticket.model_dump(mode="json")},
            )

        # ----------------------------------------------------------
        # NEW: search_knowledge_base dispatch
        #
        # Notice: no user_id, no conn. The knowledge base is shared.
        # We just extract the query string, call search(), and return
        # the results as JSON — same pattern as every other tool.
        # ----------------------------------------------------------
        if name == "search_knowledge_base":
            query = raw_input.get("query", "")
            if not isinstance(query, str) or not query.strip():
                return _err(
                    tool_use.id,
                    "query is required and must be a non-empty string.",
                )
            results = search_knowledge_base(query.strip())
            return _ok(
                tool_use.id,
                {
                    "count": len(results),
                    "results": results,
                    # results is already a list of dicts with
                    # "text", "source", and "score" keys.
                },
            )

        return _err(tool_use.id, f"Unknown tool: {name!r}")

    except ValidationError as e:
        return _err(tool_use.id, f"Input validation failed: {e}")
    except sqlite3.Error as e:
        return _err(tool_use.id, f"Database error: {type(e).__name__}")


def _ok(tool_use_id: str, payload: object) -> ToolResult:
    return ToolResult(
        tool_use_id=tool_use_id,
        content=json.dumps(payload),
        is_error=False,
    )


def _err(tool_use_id: str, message: str) -> ToolResult:
    return ToolResult(
        tool_use_id=tool_use_id,
        content=message,
        is_error=True,
    )