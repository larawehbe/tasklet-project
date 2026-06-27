"""Tests for ticket_service write paths: create_ticket and update_ticket_status."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models import Category, Priority, Status, TicketCreate
from src.ticket_service import TicketAccessDenied, create_ticket, update_ticket_status


def test_create_ticket_returns_populated_ticket(conn, seed_users):
    new = TicketCreate(
        title="Login button greyed out",
        description="Cannot log in — the submit button stays disabled.",
        category=Category.BUG_REPORT,
        priority=Priority.HIGH,
    )
    t = create_ticket(conn, user_id=1, ticket=new)

    assert t.id is not None
    assert t.user_id == 1
    assert t.title == "Login button greyed out"
    assert t.description == "Cannot log in — the submit button stays disabled."
    assert t.category == Category.BUG_REPORT
    assert t.priority == Priority.HIGH
    assert t.status == Status.OPEN  # schema default
    assert isinstance(t.created_at, datetime)
    assert isinstance(t.updated_at, datetime)


def test_create_ticket_persists_to_db(conn, seed_users):
    new = TicketCreate(
        title="Recurring billing",
        description="Want monthly invoices instead of quarterly.",
        category=Category.BILLING,
        priority=Priority.LOW,
    )
    t = create_ticket(conn, user_id=2, ticket=new)

    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (t.id,)).fetchone()
    assert row["user_id"] == 2
    assert row["title"] == "Recurring billing"
    assert row["category"] == "billing"
    assert row["status"] == "open"


def test_create_ticket_does_not_leak_across_users(conn, seed_users):
    """User 1 creates a ticket; user 2's queries must not see it."""
    create_ticket(
        conn,
        user_id=1,
        ticket=TicketCreate(
            title="Private to user 1",
            description="Only user 1 should see this.",
            category=Category.HOW_TO_QUESTION,
            priority=Priority.LOW,
        ),
    )
    other = conn.execute(
        "SELECT COUNT(*) AS n FROM tickets WHERE user_id = 2"
    ).fetchone()
    assert other["n"] == 0


def test_invalid_category_rejected_by_pydantic():
    """Bad enum values fail at the model layer, never reaching SQL.

    This is the teaching beat the agent loop relies on: when the LLM hands
    us a string that isn't a real category, we get a structured
    ValidationError that we can serialize and feed back as a tool_result
    so Claude can self-correct.
    """
    with pytest.raises(ValidationError):
        TicketCreate(
            title="x",
            description="x",
            category="not_a_category",  # type: ignore[arg-type]
            priority=Priority.LOW,
        )


def test_invalid_priority_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        TicketCreate(
            title="x",
            description="x",
            category=Category.BUG_REPORT,
            priority="extreme",  # type: ignore[arg-type]
        )


def test_empty_title_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        TicketCreate(
            title="",
            description="x",
            category=Category.BUG_REPORT,
            priority=Priority.LOW,
        )


# ---------------------------------------------------------------------------
# update_ticket_status
# ---------------------------------------------------------------------------


def _make_ticket(conn, user_id: int) -> int:
    """Helper: insert a ticket for user_id and return its id."""
    t = create_ticket(
        conn,
        user_id=user_id,
        ticket=TicketCreate(
            title="Test ticket",
            description="For update tests.",
            category=Category.BUG_REPORT,
            priority=Priority.MEDIUM,
        ),
    )
    return t.id


def test_update_ticket_status_success(conn, seed_users):
    ticket_id = _make_ticket(conn, user_id=1)

    updated = update_ticket_status(conn, user_id=1, ticket_id=ticket_id, new_status=Status.RESOLVED)

    assert updated is not None
    assert updated.id == ticket_id
    assert updated.user_id == 1
    assert updated.status == Status.RESOLVED
    assert isinstance(updated.updated_at, datetime)


def test_update_ticket_status_does_not_affect_other_users_ticket(conn, seed_users):
    """User 2 cannot update a ticket owned by user 1 — raises TicketAccessDenied."""
    ticket_id = _make_ticket(conn, user_id=1)

    with pytest.raises(TicketAccessDenied):
        update_ticket_status(conn, user_id=2, ticket_id=ticket_id, new_status=Status.CLOSED)

    # The original row must be unchanged.
    row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    assert row["status"] == "open"
