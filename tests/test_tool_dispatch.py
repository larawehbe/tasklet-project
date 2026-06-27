"""Structural security tests for dispatch().

These tests prove two invariants that cannot be inferred from reading the
service layer alone:

  1. dispatch() NEVER reads user_id from the LLM's tool input. Even if the
     LLM (or an attacker who has injected text into the conversation) tries
     to pass a different user_id, dispatch() uses the authenticated User
     object from its caller.

  2. dispatch() NEVER reads is_admin from the LLM's tool input. A malicious
     prompt cannot elevate privileges by injecting is_admin=True into the
     tool arguments.

Both invariants are structural: Pydantic models drop extra fields by default
(extra="ignore" in v2), and dispatch() extracts user_id/is_admin from the
User parameter, not from tool_use.input. These tests pin that behavior so a
future refactor cannot accidentally break it.
"""

import json

import pytest

from src.models import ToolUse, User
from src.ticket_service import create_ticket
from src.models import Category, Priority, TicketCreate
from src.tools import dispatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(conn, user_id: int) -> int:
    t = create_ticket(
        conn,
        user_id=user_id,
        ticket=TicketCreate(
            title="Dispatch test ticket",
            description="For dispatch security tests.",
            category=Category.BUG_REPORT,
            priority=Priority.LOW,
        ),
    )
    return t.id


# ---------------------------------------------------------------------------
# Invariant 1: user_id injected in tool input is ignored
# ---------------------------------------------------------------------------

def test_dispatch_ignores_user_id_injected_in_list_tickets(conn, seed_tickets):
    """LLM tries to pass user_id=2 in tool input while authenticated as user 1.

    The result must be scoped to user 1's tickets only, not user 2's.
    """
    user1 = User(id=1, email="test1@example.com", name="Test One", is_admin=False)

    # Craft a ToolUse as if the LLM tried to inject a different user_id.
    tool_use = ToolUse(
        id="tu-inject-uid",
        name="list_tickets",
        input={"user_id": 2},  # malicious injection — must be silently dropped
    )

    result = dispatch(conn, user1, tool_use)
    assert not result.is_error

    payload = json.loads(result.content)
    ticket_user_ids = {t["user_id"] for t in payload["tickets"]}
    # Should only contain user 1's tickets, never user 2's.
    assert ticket_user_ids <= {1}
    assert 2 not in ticket_user_ids


def test_dispatch_ignores_user_id_injected_in_get_ticket_by_id(conn, seed_tickets):
    """LLM injects user_id=1 when authenticated as user 2 to probe user 1's tickets."""
    user2 = User(id=2, email="test2@example.com", name="Test Two", is_admin=False)

    user1_ticket_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 1 ORDER BY id LIMIT 1"
    ).fetchone()["id"]

    tool_use = ToolUse(
        id="tu-inject-uid-get",
        name="get_ticket_by_id",
        input={"ticket_id": user1_ticket_id, "user_id": 1},  # injection
    )

    result = dispatch(conn, user2, tool_use)
    assert not result.is_error

    payload = json.loads(result.content)
    # User 2 cannot see user 1's ticket — must come back as not found.
    assert payload["found"] is False


# ---------------------------------------------------------------------------
# Invariant 2: is_admin injected in tool input does not grant admin access
# ---------------------------------------------------------------------------

def test_dispatch_ignores_is_admin_injected_in_list_tickets(conn, seed_tickets):
    """LLM tries to pass is_admin=True in tool input while authenticated as a regular user.

    Must have no effect — the result must still be scoped to user 2's tickets.
    """
    user2 = User(id=2, email="test2@example.com", name="Test Two", is_admin=False)

    tool_use = ToolUse(
        id="tu-inject-admin",
        name="list_tickets",
        input={"is_admin": True},  # privilege escalation attempt — must be ignored
    )

    result = dispatch(conn, user2, tool_use)
    assert not result.is_error

    payload = json.loads(result.content)
    # Regular user 2 should only see their own 2 tickets, not all 7.
    assert payload["count"] == 2
    ticket_user_ids = {t["user_id"] for t in payload["tickets"]}
    assert ticket_user_ids == {2}


def test_dispatch_ignores_is_admin_injected_in_get_ticket_by_id(conn, seed_tickets):
    """LLM injects is_admin=True to try to read another user's ticket."""
    user2 = User(id=2, email="test2@example.com", name="Test Two", is_admin=False)

    user1_ticket_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 1 ORDER BY id LIMIT 1"
    ).fetchone()["id"]

    tool_use = ToolUse(
        id="tu-inject-admin-get",
        name="get_ticket_by_id",
        input={"ticket_id": user1_ticket_id, "is_admin": True},  # injection
    )

    result = dispatch(conn, user2, tool_use)
    assert not result.is_error

    payload = json.loads(result.content)
    # is_admin in tool input must be ignored — user 2 still cannot see this ticket.
    assert payload["found"] is False


# ---------------------------------------------------------------------------
# Sanity: legitimate admin access works through the User object, not tool input
# ---------------------------------------------------------------------------

def test_admin_access_via_user_object_not_tool_input(conn, seed_tickets):
    """Admin sees all tickets only when the authenticated User has is_admin=True.

    This is the positive-path companion to the injection tests above. It proves
    the right channel (User object) does work as expected.
    """
    admin_user = User(id=1, email="test1@example.com", name="Test One", is_admin=True)

    tool_use = ToolUse(
        id="tu-admin-legit",
        name="list_tickets",
        input={},  # no is_admin in input — privilege comes from the User object
    )

    result = dispatch(conn, admin_user, tool_use)
    assert not result.is_error

    payload = json.loads(result.content)
    assert payload["count"] == 7  # all fixture tickets across both users
