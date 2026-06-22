"""Ticket creation. The only write path in this app.

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


class TicketAccessDenied(Exception):
    """Raised when a user attempts to modify a ticket they do not own."""


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
    conn: sqlite3.Connection, user_id: int, ticket_id: int, new_status: Status
) -> Ticket | None:
    """Update the status of a ticket owned by user_id.

    Returns the updated Ticket on success, or None if the ticket does not exist.
    Raises TicketAccessDenied if the ticket exists but belongs to another user.
    """
    exists_row = conn.execute(
        "SELECT user_id FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()

    if exists_row is None:
        return None

    if exists_row["user_id"] != user_id:
        raise TicketAccessDenied(ticket_id)

    conn.execute(
        "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND user_id = ?",
        (new_status.value, ticket_id, user_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id, user_id, title, description, category, priority, status, "
        "       created_at, updated_at "
        "FROM tickets WHERE id = ? AND user_id = ?",
        (ticket_id, user_id),
    ).fetchone()
    return Ticket(**dict(row))
