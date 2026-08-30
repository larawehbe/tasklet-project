"""Pydantic models for the personal finance agent.

Every input the LLM produces (tool inputs) and every record we store
(transactions) is one of these models.

These models are the contract between three layers:
  1. The LLM — its tool inputs must validate as TransactionFilters.
  2. The service layer — it accepts and returns these models.
  3. The database — rows materialize back into Transaction objects.

If the LLM emits a bad enum or an out-of-range amount, Pydantic raises a
ValidationError and the agent loop turns that into a tool_result so Claude
can self-correct on the next iteration.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCategory(str, Enum):
    FOOD = "food"
    SHOPPING = "shopping"
    TRANSPORT = "transport"
    ENTERTAINMENT = "entertainment"
    HOUSING = "housing"
    HEALTHCARE = "healthcare"
    UTILITIES = "utilities"
    SALARY = "salary"
    TRANSFER = "transfer"
    OTHER = "other"


class Transaction(BaseModel):
    """A persisted transaction. amount is always positive; type distinguishes
    income from expense so arithmetic stays unambiguous."""

    id: int
    user_id: int
    amount: float
    type: TransactionType
    category: TransactionCategory
    merchant: str
    description: Optional[str] = None
    date: date
    created_at: datetime


class TransactionFilters(BaseModel):
    """Tool input for list_transactions. All fields optional.

    merchant_query is a case-insensitive substring match applied to both
    merchant name and description — use it for queries like 'Amazon' or
    'coffee'.
    """

    type: Optional[TransactionType] = None
    category: Optional[TransactionCategory] = None
    date_after: Optional[date] = None
    date_before: Optional[date] = None
    min_amount: Optional[float] = Field(default=None, ge=0)
    max_amount: Optional[float] = Field(default=None, ge=0)
    merchant_query: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1, le=500)
