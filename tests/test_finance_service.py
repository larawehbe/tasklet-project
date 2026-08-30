"""Tests for list_transactions and get_transaction_by_id.

The most important tests in this file are those that prove user_id scoping
works — there must be no way to read another user's transaction via either
function. Those tests are clearly labeled SECURITY.
"""

from datetime import date

from src.finance_models import (
    TransactionCategory,
    TransactionFilters,
    TransactionType,
)
from src.finance_service import get_transaction_by_id, list_transactions


# ---------- list_transactions ----------


def test_list_returns_all_user_transactions_when_no_filters(conn, seed_transactions):
    results = list_transactions(conn, user_id=1, filters=TransactionFilters())
    assert len(results) == 6  # user 1 has 6 in the fixture


def test_list_excludes_other_users_transactions(conn, seed_transactions):
    """SECURITY: user 1 must never see user 2's transactions with no filter."""
    results = list_transactions(conn, user_id=1, filters=TransactionFilters())
    for t in results:
        assert t.user_id == 1
    merchants = {t.merchant for t in results}
    assert "Globex Corp" not in merchants
    assert "Whole Foods" not in merchants


def test_list_orders_newest_date_first(conn, seed_transactions):
    results = list_transactions(conn, user_id=1, filters=TransactionFilters())
    dates = [t.date for t in results]
    assert dates == sorted(dates, reverse=True)


def test_list_filters_by_type_expense(conn, seed_transactions):
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(type=TransactionType.EXPENSE)
    )
    assert all(t.type == TransactionType.EXPENSE for t in results)
    assert len(results) == 4


def test_list_filters_by_type_income(conn, seed_transactions):
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(type=TransactionType.INCOME)
    )
    assert all(t.type == TransactionType.INCOME for t in results)
    assert len(results) == 2


def test_list_filters_by_category(conn, seed_transactions):
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(category=TransactionCategory.FOOD),
    )
    assert len(results) == 1
    assert results[0].merchant == "Trader Joe's"


def test_list_filters_by_date_range(conn, seed_transactions):
    """Fixture spans 2026-04-01 .. 2026-04-15. Window catches 3 transactions."""
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(
            date_after=date(2026, 4, 7),
            date_before=date(2026, 4, 11),
        ),
    )
    merchants = {t.merchant for t in results}
    assert merchants == {"Amazon", "Netflix"}


def test_list_filters_by_min_amount(conn, seed_transactions):
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(min_amount=1000)
    )
    assert all(t.amount >= 1000 for t in results)
    amounts = {t.amount for t in results}
    assert amounts == {8500.00, 2400.00}


def test_list_filters_by_max_amount(conn, seed_transactions):
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(max_amount=50)
    )
    assert all(t.amount <= 50 for t in results)
    assert len(results) == 2  # Amazon $45, Netflix $15.99


def test_list_filters_by_merchant_query(conn, seed_transactions):
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(merchant_query="amazon")
    )
    assert len(results) == 1
    assert results[0].merchant == "Amazon"


def test_list_merchant_query_is_case_insensitive(conn, seed_transactions):
    results_lower = list_transactions(
        conn, user_id=1, filters=TransactionFilters(merchant_query="trader")
    )
    results_upper = list_transactions(
        conn, user_id=1, filters=TransactionFilters(merchant_query="TRADER")
    )
    assert len(results_lower) == 1
    assert len(results_lower) == len(results_upper)


def test_list_merchant_query_matches_description(conn, seed_transactions):
    """merchant_query is also checked against description."""
    results = list_transactions(
        conn, user_id=1, filters=TransactionFilters(merchant_query="salary")
    )
    # "Monthly salary" is in the description for the Acme Corp row
    assert any(t.merchant == "Acme Corp" for t in results)


def test_list_combines_multiple_filters(conn, seed_transactions):
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(
            type=TransactionType.EXPENSE,
            category=TransactionCategory.FOOD,
        ),
    )
    assert len(results) == 1
    assert results[0].merchant == "Trader Joe's"


def test_list_returns_empty_when_no_match(conn, seed_transactions):
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(category=TransactionCategory.HEALTHCARE),
    )
    assert results == []


def test_list_respects_limit(conn, seed_transactions):
    results = list_transactions(conn, user_id=1, filters=TransactionFilters(limit=2))
    assert len(results) == 2


def test_list_filter_does_not_break_user_scope(conn, seed_transactions):
    """SECURITY: user 2 has a food expense. User 1 querying food must not see it —
    scope must compose with filters, never replace them."""
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(category=TransactionCategory.FOOD),
    )
    for t in results:
        assert t.user_id == 1
    merchants = {t.merchant for t in results}
    assert "Whole Foods" not in merchants


def test_list_income_filter_does_not_break_user_scope(conn, seed_transactions):
    """SECURITY: user 2 has income. User 1 filtering by income must not see it."""
    results = list_transactions(
        conn,
        user_id=1,
        filters=TransactionFilters(type=TransactionType.INCOME),
    )
    for t in results:
        assert t.user_id == 1
    merchants = {t.merchant for t in results}
    assert "Globex Corp" not in merchants


# ---------- get_transaction_by_id ----------


def test_get_returns_owned_transaction(conn, seed_transactions):
    user1_txn_id = conn.execute(
        "SELECT id FROM transactions WHERE user_id = 1 ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    t = get_transaction_by_id(conn, user_id=1, transaction_id=user1_txn_id)
    assert t is not None
    assert t.user_id == 1


def test_get_returns_none_for_nonexistent(conn, seed_transactions):
    assert get_transaction_by_id(conn, user_id=1, transaction_id=99999) is None


def test_get_returns_none_for_other_users_transaction(conn, seed_transactions):
    """SECURITY: requesting user 2's transaction as user 1 returns None.

    We do NOT distinguish 'not found' from 'not yours' — both return None
    so the caller cannot probe for the existence of another user's record.
    """
    user2_txn_id = conn.execute(
        "SELECT id FROM transactions WHERE user_id = 2 ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    t = get_transaction_by_id(conn, user_id=1, transaction_id=user2_txn_id)
    assert t is None
