"""
Pydantic models for LLM extraction output and internal DTOs.
Keeping these separate from DB models — these represent the shape of data
*in flight* between the LLM, business logic, and DB layer.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class Intent(str, Enum):
    TRANSACTION = "TRANSACTION"
    QUERY = "QUERY"
    CORRECTION = "CORRECTION"
    REMINDER = "REMINDER"
    ONBOARDING = "ONBOARDING"
    GREETING_OR_OTHER = "GREETING_OR_OTHER"


class TransactionType(str, Enum):
    SALE_CASH = "sale_cash"
    SALE_CREDIT = "sale_credit"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_MADE = "payment_made"
    SUPPLIER_PURCHASE = "supplier_purchase"


class QueryType(str, Enum):
    DAILY_SALES = "daily_sales"
    WHO_OWES_ME = "who_owes_me"
    WHO_I_OWE = "who_i_owe"
    CUSTOMER_BALANCE = "customer_balance"
    DAILY_SUMMARY = "daily_summary"


class ItemLine(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None       # 'kg', 'packet', 'piece', etc.
    price: float | None = None    # total price for this item line (not per-unit)
    category: str | None = None   # grains|drinks|snacks|oil_ghee|spices|soap_cleaning|tobacco|dairy_eggs|sweets|other


class ExtractedTransaction(BaseModel):
    transaction_type: TransactionType
    customer_name: str | None = None
    amount: float = Field(ge=0)
    items: list[ItemLine] = Field(default_factory=list)
    notes: str | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class ExtractedQuery(BaseModel):
    query_type: QueryType
    customer_name: str | None = None
    date_range: Literal["today", "yesterday", "this_week", "this_month", "all"] = "today"


class ExtractedReminder(BaseModel):
    description: str
    person_name: str | None = None
    amount: float | None = None
    remind_date: str | None = None  # "tomorrow", "YYYY-MM-DD", or null → defaults to tomorrow


class ExtractionResult(BaseModel):
    """Top-level output from the extraction LLM call."""
    intent: Intent
    transaction: ExtractedTransaction | None = None
    query: ExtractedQuery | None = None
    reminder: ExtractedReminder | None = None
    correction_hint: str | None = None
    language_detected: Literal["urdu", "roman_urdu", "english", "mixed"] = "roman_urdu"
    needs_clarification: bool = False
    clarification_question: str | None = None


# --------- DB-facing DTOs ---------

class Shopkeeper(BaseModel):
    id: str
    phone_number: str
    shop_name: str | None = None
    owner_name: str | None = None
    language_pref: str = "roman_urdu"
    timezone: str = "Asia/Karachi"
    onboarding_state: str = "new"
    subscription_status: str = "trial"


class Contact(BaseModel):
    id: str
    shopkeeper_id: str
    name: str
    normalized_name: str
    type: Literal["customer", "supplier"]


class ContactWithBalance(Contact):
    balance: float


class Transaction(BaseModel):
    id: str
    shopkeeper_id: str
    contact_id: str | None
    type: TransactionType
    amount: float
    items: list[dict] | None = None
    notes: str | None = None
    raw_message: str | None = None
    transcript: str | None = None
    source: Literal["text", "voice"] = "text"
    occurred_at: datetime
