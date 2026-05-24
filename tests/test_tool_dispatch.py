"""Tests for tools.dispatch() — routing and security.

Each tool gets a happy-path test and an error-path test. The three tests
marked SECURITY prove the core invariant: user_id is never read from the
LLM's tool input. See CLAUDE.md § "The security invariant" for details.
"""

import json

import pytest

from src.models import Status, ToolUse
from src.tools import dispatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_use(name: str, **kwargs) -> ToolUse:
    return ToolUse(id="test-id", name=name, input=kwargs)


def _result(tool_use, conn, user_id=1):
    return dispatch(conn, user_id, tool_use)


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------

def test_create_ticket_dispatch_returns_new_ticket(conn, seed_users):
    tu = _tool_use(
        "create_ticket",
        title="Dispatch test ticket",
        description="Filed via dispatch.",
        category="bug_report",
        priority="high",
    )
    result = _result(tu, conn)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["title"] == "Dispatch test ticket"
    assert payload["status"] == "open"
    assert payload["user_id"] == 1


def test_create_ticket_dispatch_validation_error(conn, seed_users):
    tu = _tool_use(
        "create_ticket",
        title="Bad ticket",
        description="x",
        category="not_a_real_category",
        priority="high",
    )
    result = _result(tu, conn)
    assert result.is_error
    assert "validation" in result.content.lower()


# SECURITY: user_id injected by LLM is silently ignored; ticket is still
# created for the authenticated user (user_id=1), not the injected user_id=2.
def test_create_ticket_ignores_injected_user_id(conn, seed_users):
    tu = _tool_use(
        "create_ticket",
        title="Injection attempt",
        description="Trying to file as user 2.",
        category="bug_report",
        priority="low",
        user_id=2,  # LLM tries to inject a different user
    )
    result = dispatch(conn, user_id=1, tool_use=tu)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["user_id"] == 1  # must be the authenticated user


# ---------------------------------------------------------------------------
# list_tickets
# ---------------------------------------------------------------------------

def test_list_tickets_dispatch_returns_user_tickets(conn, seed_tickets):
    tu = _tool_use("list_tickets")
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["count"] == 5
    for t in payload["tickets"]:
        assert t["user_id"] == 1


def test_list_tickets_dispatch_filters_by_status(conn, seed_tickets):
    tu = _tool_use("list_tickets", status="open")
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["count"] == 1
    assert payload["tickets"][0]["status"] == "open"


# SECURITY: user 1 calls list_tickets; must not see user 2's tickets even
# though user 2 also has open tickets that would otherwise match the filter.
def test_list_tickets_scoped_to_authenticated_user(conn, seed_tickets):
    tu = _tool_use("list_tickets", status="open")
    result = dispatch(conn, user_id=1, tool_use=tu)
    assert not result.is_error
    payload = json.loads(result.content)
    for t in payload["tickets"]:
        assert t["user_id"] == 1  # user 2's open tickets must not appear


# ---------------------------------------------------------------------------
# get_ticket_by_id
# ---------------------------------------------------------------------------

def test_get_ticket_by_id_dispatch_found(conn, seed_tickets):
    ticket_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 1 LIMIT 1"
    ).fetchone()["id"]
    tu = _tool_use("get_ticket_by_id", ticket_id=ticket_id)
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["found"] is True
    assert payload["ticket"]["id"] == ticket_id


def test_get_ticket_by_id_dispatch_not_found(conn, seed_tickets):
    tu = _tool_use("get_ticket_by_id", ticket_id=9999)
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["found"] is False


# SECURITY: user 1 tries to look up a ticket owned by user 2 — must get
# found=False, indistinguishable from a ticket that doesn't exist at all.
def test_get_ticket_by_id_cannot_read_other_users_ticket(conn, seed_tickets):
    other_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 2 LIMIT 1"
    ).fetchone()["id"]
    tu = _tool_use("get_ticket_by_id", ticket_id=other_id)
    result = dispatch(conn, user_id=1, tool_use=tu)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["found"] is False  # must not reveal existence


# ---------------------------------------------------------------------------
# update_ticket_status
# ---------------------------------------------------------------------------

def test_update_ticket_status_happy_path(conn, seed_tickets):
    ticket_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 1 AND status = 'open' LIMIT 1"
    ).fetchone()["id"]
    tu = _tool_use("update_ticket_status", ticket_id=ticket_id, status="resolved")
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["updated"] is True
    assert payload["ticket"]["status"] == "resolved"
    assert payload["ticket"]["id"] == ticket_id


def test_update_ticket_status_nonexistent_ticket(conn, seed_tickets):
    tu = _tool_use("update_ticket_status", ticket_id=9999, status="closed")
    result = _result(tu, conn, user_id=1)
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["updated"] is False


def test_update_ticket_status_validation_error(conn, seed_tickets):
    ticket_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 1 LIMIT 1"
    ).fetchone()["id"]
    tu = _tool_use("update_ticket_status", ticket_id=ticket_id, status="not_a_status")
    result = _result(tu, conn, user_id=1)
    assert result.is_error
    assert "validation" in result.content.lower()


# SECURITY: user 1 tries to update a ticket belonging to user 2 — must get
# updated=False and the ticket's status in the DB must be unchanged.
def test_update_ticket_status_cannot_update_other_users_ticket(conn, seed_tickets):
    other_id = conn.execute(
        "SELECT id FROM tickets WHERE user_id = 2 LIMIT 1"
    ).fetchone()["id"]
    original_status = conn.execute(
        "SELECT status FROM tickets WHERE id = ?", (other_id,)
    ).fetchone()["status"]

    tu = _tool_use("update_ticket_status", ticket_id=other_id, status="closed")
    result = dispatch(conn, user_id=1, tool_use=tu)

    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["updated"] is False  # must not report success

    # confirm the row was not actually modified
    current_status = conn.execute(
        "SELECT status FROM tickets WHERE id = ?", (other_id,)
    ).fetchone()["status"]
    assert current_status == original_status
