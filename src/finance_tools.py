"""Finance tool definitions and dispatch.

This module is the bridge between the LLM and the finance service layer.
It owns:

  1. FINANCE_TOOL_SCHEMAS — the JSON sent to Anthropic on every API call.
     Descriptions here are some of the most behavior-influential prompts in
     the finance agent; tweak them to change agent behavior before touching
     code.

  2. finance_dispatch() — given a parsed ToolUse from a Claude response,
     executes the right service function and packages the result as a
     ToolResult to feed back on the next agent loop iteration.

Security: finance_dispatch() ALWAYS uses the user_id passed in by the
caller (the authenticated session) and NEVER reads user_id from the LLM's
tool input. If the LLM tries to pass user_id, it is silently dropped
(Pydantic ignores extra fields by default in v2).
"""

import json
import sqlite3

from pydantic import ValidationError

from src.finance_models import TransactionFilters
from src.finance_service import get_transaction_by_id, list_transactions
from src.models import ToolResult, ToolUse

FINANCE_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_transactions",
        "description": (
            "Return transactions belonging to the current user, optionally filtered. "
            "Use this for questions like 'how much did I spend on food?', "
            "'show my Amazon purchases', 'what were my biggest expenses this month?', "
            "'list my income this year', or any question about transaction history. "
            "All filters are optional — omit a filter to leave that dimension "
            "unconstrained. Results are automatically scoped to the current user; "
            "you do not need to (and cannot) specify a user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["income", "expense"],
                    "description": (
                        "Restrict to income or expense transactions only. "
                        "Omit to return both."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "food",
                        "shopping",
                        "transport",
                        "entertainment",
                        "housing",
                        "healthcare",
                        "utilities",
                        "salary",
                        "transfer",
                        "other",
                    ],
                    "description": "Restrict to transactions in this category.",
                },
                "date_after": {
                    "type": "string",
                    "format": "date",
                    "description": (
                        "ISO 8601 date. Only return transactions on or after this date. "
                        "Example: '2026-01-01'."
                    ),
                },
                "date_before": {
                    "type": "string",
                    "format": "date",
                    "description": (
                        "ISO 8601 date. Only return transactions on or before this date. "
                        "Example: '2026-01-31'."
                    ),
                },
                "min_amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Only return transactions with amount >= this value.",
                },
                "max_amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Only return transactions with amount <= this value.",
                },
                "merchant_query": {
                    "type": "string",
                    "description": (
                        "Substring to search for in the merchant name or description "
                        "(case-insensitive). Use this for queries like 'Amazon', "
                        "'Starbucks', 'coffee', or any keyword."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "description": (
                        "Optional cap on the number of results. Useful for "
                        "'my 5 most recent transactions'. Omit to return all matches."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_transaction_by_id",
        "description": (
            "Look up one specific transaction by its numeric id. "
            "Returns the full transaction if it exists and belongs to the current user, "
            "otherwise returns a 'not found' response. Use this when the user references "
            "a specific transaction id (e.g., 'tell me about transaction 42')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "integer",
                    "description": "The numeric id of the transaction to look up.",
                },
            },
            "required": ["transaction_id"],
        },
    },
]


def finance_dispatch(
    conn: sqlite3.Connection, user_id: int, tool_use: ToolUse
) -> ToolResult:
    """Execute the named finance tool and return a ToolResult.

    The user_id parameter is the authenticated user's id. This function NEVER
    reads user_id from tool_use.input — even if the LLM tries to pass one,
    it is ignored. Tests prove this.
    """
    name = tool_use.name
    raw_input = tool_use.input

    try:
        if name == "list_transactions":
            filters = TransactionFilters(**raw_input)
            transactions = list_transactions(conn, user_id, filters)
            return _ok(
                tool_use.id,
                {
                    "count": len(transactions),
                    "transactions": [t.model_dump(mode="json") for t in transactions],
                },
            )

        if name == "get_transaction_by_id":
            transaction_id = raw_input.get("transaction_id")
            if not isinstance(transaction_id, int) or isinstance(transaction_id, bool):
                return _err(
                    tool_use.id,
                    "transaction_id is required and must be an integer.",
                )
            txn = get_transaction_by_id(conn, user_id, transaction_id)
            if txn is None:
                return _ok(
                    tool_use.id,
                    {"found": False, "transaction_id": transaction_id},
                )
            return _ok(
                tool_use.id,
                {"found": True, "transaction": txn.model_dump(mode="json")},
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
