"""Read paths for transactions. Every function here is scoped to user_id.

Two functions:

  * list_transactions — applies optional filters from TransactionFilters and
    returns every matching transaction owned by user_id, newest-date first.
  * get_transaction_by_id — returns one transaction if it exists AND is owned
    by user_id, otherwise None.

The hard rule: user_id is the FIRST required parameter on every function
in this module. There is no overload that accepts only a transaction_id.
Making cross-tenant access impossible at the function signature level is
more important than any minor convenience.
"""

import sqlite3
from typing import Optional

from src.finance_models import Transaction, TransactionFilters


def list_transactions(
    conn: sqlite3.Connection, user_id: int, filters: TransactionFilters
) -> list[Transaction]:
    """Return all of user_id's transactions matching `filters`, newest-date first."""
    sql_parts = [
        "SELECT id, user_id, amount, type, category, merchant, description, date, created_at "
        "FROM transactions WHERE user_id = ?"
    ]
    params: list = [user_id]

    if filters.type is not None:
        sql_parts.append("AND type = ?")
        params.append(filters.type.value)
    if filters.category is not None:
        sql_parts.append("AND category = ?")
        params.append(filters.category.value)
    if filters.date_after is not None:
        sql_parts.append("AND date >= ?")
        params.append(filters.date_after.isoformat())
    if filters.date_before is not None:
        sql_parts.append("AND date <= ?")
        params.append(filters.date_before.isoformat())
    if filters.min_amount is not None:
        sql_parts.append("AND amount >= ?")
        params.append(filters.min_amount)
    if filters.max_amount is not None:
        sql_parts.append("AND amount <= ?")
        params.append(filters.max_amount)
    if filters.merchant_query is not None:
        sql_parts.append("AND (merchant LIKE ? OR description LIKE ?)")
        q = f"%{filters.merchant_query}%"
        params.extend([q, q])

    sql_parts.append("ORDER BY date DESC, id DESC")
    if filters.limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(filters.limit)

    rows = conn.execute(" ".join(sql_parts), params).fetchall()
    return [Transaction(**dict(row)) for row in rows]


def get_transaction_by_id(
    conn: sqlite3.Connection, user_id: int, transaction_id: int
) -> Optional[Transaction]:
    """Return the transaction if owned by user_id, else None.

    We deliberately do NOT distinguish "transaction does not exist" from
    "transaction exists but belongs to another user" — both return None.
    Returning different errors for the two cases would leak existence info.
    """
    row = conn.execute(
        "SELECT id, user_id, amount, type, category, merchant, description, date, created_at "
        "FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, user_id),
    ).fetchone()
    return Transaction(**dict(row)) if row else None
