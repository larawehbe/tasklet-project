"""Tests for finance_dispatch — the bridge between LLM tool calls and the service layer.

The most important tests here are labeled SECURITY. They prove:
  1. user_id in tool input is ignored — dispatch uses the caller-supplied user_id.
  2. is_admin or similar fields in tool input are ignored.
  3. A user cannot access another user's transaction even if they supply the right id.
  4. Unknown tool names return an error result, not an exception.

Filter correctness is also verified for category, date range, amount range,
and merchant_query — matching the coverage in test_finance_service.py but
exercised through the dispatch() layer to confirm the two are wired together
correctly.
"""

import json
from datetime import date

from src.finance_models import TransactionCategory, TransactionType
from src.finance_tools import finance_dispatch
from src.models import ToolUse


# ---------- helpers ----------


def tool_use(name: str, **kwargs) -> ToolUse:
    return ToolUse(id="test-id", name=name, input=kwargs)


def result_payload(tr) -> dict:
    return json.loads(tr.content)


# ---------- list_transactions dispatch ----------


def test_dispatch_list_no_filters_returns_all_user_transactions(conn, seed_transactions):
    tr = finance_dispatch(conn, user_id=1, tool_use=tool_use("list_transactions"))
    assert tr.is_error is False
    payload = result_payload(tr)
    assert payload["count"] == 6


def test_dispatch_list_filters_by_type(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", type="expense"),
    )
    payload = result_payload(tr)
    assert payload["count"] == 4
    assert all(t["type"] == "expense" for t in payload["transactions"])


def test_dispatch_list_filters_by_category(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", category="food"),
    )
    payload = result_payload(tr)
    assert payload["count"] == 1
    assert payload["transactions"][0]["merchant"] == "Trader Joe's"


def test_dispatch_list_filters_by_date_range(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use(
            "list_transactions",
            date_after="2026-04-07",
            date_before="2026-04-11",
        ),
    )
    payload = result_payload(tr)
    merchants = {t["merchant"] for t in payload["transactions"]}
    assert merchants == {"Amazon", "Netflix"}


def test_dispatch_list_filters_by_amount_range(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", min_amount=1000),
    )
    payload = result_payload(tr)
    assert all(t["amount"] >= 1000 for t in payload["transactions"])


def test_dispatch_list_filters_by_merchant_query(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", merchant_query="amazon"),
    )
    payload = result_payload(tr)
    assert payload["count"] == 1
    assert payload["transactions"][0]["merchant"] == "Amazon"


def test_dispatch_list_respects_limit(conn, seed_transactions):
    tr = finance_dispatch(
        conn, user_id=1, tool_use=tool_use("list_transactions", limit=2)
    )
    payload = result_payload(tr)
    assert payload["count"] == 2


# ---------- get_transaction_by_id dispatch ----------


def test_dispatch_get_returns_owned_transaction(conn, seed_transactions):
    txn_id = conn.execute(
        "SELECT id FROM transactions WHERE user_id = 1 ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    tr = finance_dispatch(
        conn, user_id=1, tool_use=tool_use("get_transaction_by_id", transaction_id=txn_id)
    )
    assert tr.is_error is False
    payload = result_payload(tr)
    assert payload["found"] is True
    assert payload["transaction"]["user_id"] == 1


def test_dispatch_get_returns_not_found_for_nonexistent(conn, seed_transactions):
    tr = finance_dispatch(
        conn, user_id=1, tool_use=tool_use("get_transaction_by_id", transaction_id=99999)
    )
    assert tr.is_error is False
    payload = result_payload(tr)
    assert payload["found"] is False


# ---------- SECURITY tests ----------


def test_dispatch_ignores_user_id_in_tool_input(conn, seed_transactions):
    """SECURITY: even if the LLM passes user_id=2 in the tool input, dispatch
    must use the caller-supplied user_id=1 and return user 1's transactions only."""
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", user_id=2),  # attacker-supplied field
    )
    assert tr.is_error is False
    payload = result_payload(tr)
    for t in payload["transactions"]:
        assert t["user_id"] == 1


def test_dispatch_ignores_is_admin_in_tool_input(conn, seed_transactions):
    """SECURITY: is_admin in the tool input must have no effect — dispatch ignores it."""
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", is_admin=True),  # attacker-supplied field
    )
    assert tr.is_error is False
    payload = result_payload(tr)
    for t in payload["transactions"]:
        assert t["user_id"] == 1


def test_dispatch_get_ignores_user_id_override(conn, seed_transactions):
    """SECURITY: supplying user_id=1 in the tool input cannot retrieve user 2's
    transaction when dispatch was called with user_id=2."""
    user2_txn_id = conn.execute(
        "SELECT id FROM transactions WHERE user_id = 2 ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    tr = finance_dispatch(
        conn,
        user_id=1,  # authenticated as user 1
        tool_use=tool_use(
            "get_transaction_by_id",
            transaction_id=user2_txn_id,
            user_id=1,  # LLM tries to claim ownership
        ),
    )
    assert tr.is_error is False
    payload = result_payload(tr)
    # Should be not found — user 1 does not own this transaction
    assert payload["found"] is False


def test_dispatch_get_user2_transaction_as_user1_returns_not_found(conn, seed_transactions):
    """SECURITY: user 1 cannot retrieve user 2's transaction by id, even without
    any injection attempt — the ownership check must be unconditional."""
    user2_txn_id = conn.execute(
        "SELECT id FROM transactions WHERE user_id = 2 ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("get_transaction_by_id", transaction_id=user2_txn_id),
    )
    payload = result_payload(tr)
    assert payload["found"] is False


def test_dispatch_unknown_tool_returns_error(conn, seed_transactions):
    tr = finance_dispatch(
        conn, user_id=1, tool_use=tool_use("delete_transaction", transaction_id=1)
    )
    assert tr.is_error is True
    assert "Unknown tool" in tr.content


def test_dispatch_invalid_category_returns_validation_error(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("list_transactions", category="not_a_category"),
    )
    assert tr.is_error is True
    assert "validation" in tr.content.lower()


def test_dispatch_missing_transaction_id_returns_error(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=tool_use("get_transaction_by_id"),  # missing transaction_id
    )
    assert tr.is_error is True


def test_dispatch_non_integer_transaction_id_returns_error(conn, seed_transactions):
    tr = finance_dispatch(
        conn,
        user_id=1,
        tool_use=ToolUse(id="t", name="get_transaction_by_id", input={"transaction_id": "abc"}),
    )
    assert tr.is_error is True


# ---------- finance agent loop ----------


def test_finance_agent_loop_executes_tool_then_finishes(conn, seed_transactions):
    """Verify run_finance_turn wires dispatch correctly using the same fake
    client pattern as test_agent.py."""
    from src.conversation import Conversation
    from src.finance_agent import run_finance_turn

    class _Block:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _Response:
        def __init__(self, content, stop_reason):
            self.content = content
            self.stop_reason = stop_reason

    class _Messages:
        def __init__(self, factory):
            self._factory = factory

        def create(self, **kwargs):
            return self._factory(kwargs)

    responses = iter([
        _Response(
            content=[
                _Block(type="tool_use", id="t1", name="list_transactions", input={})
            ],
            stop_reason="tool_use",
        ),
        _Response(
            content=[_Block(type="text", text="You have 6 transactions.")],
            stop_reason="end_turn",
        ),
    ])

    class FakeClient:
        def __init__(self):
            self.messages = _Messages(lambda kw: next(responses))

    conv = Conversation.load_or_create(conn, user_id=1)
    result = run_finance_turn(
        client=FakeClient(),
        conn=conn,
        conversation=conv,
        user_input="show my transactions",
    )
    assert result.tool_call_count == 1
    assert result.final_text == "You have 6 transactions."
    assert conv.messages[2].role == "tool"
    assert conv.messages[2].tool_result.is_error is False
