"""Ticket write paths for the Tasklet support agent.

`create_ticket` is the implementation behind the LLM tool of the same name.
It accepts an authenticated `user_id` (always passed in by the caller, never
by the LLM) and a `TicketCreate` that has already been validated by Pydantic.

The new row uses schema defaults for `status` ('open'), `created_at`, and
`updated_at` (CURRENT_TIMESTAMP). After insert we re-SELECT the row and
return it as a `Ticket` so the caller (and the LLM) sees the fully populated
record, including the server-assigned id and timestamps.

`user_id` is the FIRST required parameter — by convention in this codebase,
every function that touches the tickets table starts with user_id, so it
is impossible to write a query that forgets to scope.
"""

import sqlite3

from src.models import Status, Ticket, TicketCreate


def create_ticket(
    conn: sqlite3.Connection, user_id: int, ticket: TicketCreate
) -> Ticket:
    cursor = conn.execute(
        "INSERT INTO tickets (user_id, title, description, category, priority) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            ticket.title,
            ticket.description,
            ticket.category.value,
            ticket.priority.value,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid

    row = conn.execute(
        "SELECT id, user_id, title, description, category, priority, status, "
        "       created_at, updated_at "
        "FROM tickets WHERE id = ?",
        (new_id,),
    ).fetchone()
    return Ticket(**dict(row))


def update_ticket_status(
    conn: sqlite3.Connection,
    user_id: int,
    ticket_id: int,
    new_status: Status,
) -> Ticket | None:
    """Second write path in the app. Follows the same user_id-first scoping as
    create_ticket: the UPDATE filters on both user_id AND ticket_id, so a user
    can never modify another user's ticket. Returns None if no row was updated
    (wrong user or ticket does not exist — intentionally indistinguishable).
    On success, re-SELECTs and returns the fully-populated Ticket.
    """
    cursor = conn.execute(
        "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND user_id = ?",
        (new_status.value, ticket_id, user_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return None

    row = conn.execute(
        "SELECT id, user_id, title, description, category, priority, status, "
        "       created_at, updated_at "
        "FROM tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    return Ticket(**dict(row))
