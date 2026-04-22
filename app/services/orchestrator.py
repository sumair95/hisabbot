"""
Message orchestrator.

Given a shopkeeper and an incoming message (text or transcribed voice),
decide what to do: log a transaction, answer a query, run a correction,
or walk through onboarding. Return a plain-text reply string.

This is deliberately a single file so the full conversational flow is
visible in one place.
"""
from __future__ import annotations
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..models import (
    ExtractionResult, Intent, QueryType, TransactionType,
)
from ..utils.logging import get_logger
from . import db, llm, replies
from .contact_matching import (
    AmbiguousContact, UnconfirmedContact,
    find_contact_by_name, mark_confirmed, resolve_contact,
)

log = get_logger("orchestrator")


async def handle_message(
    shopkeeper: dict,
    text: str,
    *,
    source: str = "text",
    transcript: str | None = None,
    raw_message: str | None = None,
) -> tuple[str, dict | None, str | None]:
    """
    Main entry point. Returns (reply_text, extraction_json, transaction_id).
    The extraction_json and transaction_id are returned so the caller can
    store them in the `messages` audit table.
    """
    lang = shopkeeper.get("language_pref") or "roman_urdu"

    # ---- Onboarding: shop name collection ------------------
    if shopkeeper.get("onboarding_state") == "new":
        await db.update_shopkeeper(
            str(shopkeeper["id"]), onboarding_state="awaiting_shop_name"
        )
        return replies.onboarding_welcome(lang), None, None

    if shopkeeper.get("onboarding_state") == "awaiting_shop_name":
        shop_name = (text or "").strip()[:100]
        if len(shop_name) < 2:
            return replies.onboarding_ask_shop_name(lang), None, None
        await db.update_shopkeeper(
            str(shopkeeper["id"]),
            shop_name=shop_name,
            onboarding_state="done",
        )
        return replies.onboarding_done(shop_name, lang), None, None

    # ---- Pending contact confirmation or disambiguation --------------------
    if shopkeeper.get("bot_state") == "awaiting_contact_confirm":
        return await _handle_contact_confirm(shopkeeper, text, lang)
    if shopkeeper.get("bot_state") == "awaiting_disambiguation":
        return await _handle_disambiguation(shopkeeper, text, lang)

    # ---- Cheap shortcut: 'undo' keyword --------------------
    low = (text or "").strip().lower()
    if low in {"undo", "galat", "ghalat", "galat hai", "ghalat hai", "cancel", "delete"}:
        removed = await db.soft_delete_last_transaction(str(shopkeeper["id"]))
        return (
            replies.undo_success(lang) if removed else replies.undo_nothing(lang),
            {"intent": "CORRECTION", "action": "undo_last"},
            None,
        )

    # ---- Run LLM extraction --------------------------------
    try:
        extraction: ExtractionResult = await llm.extract(text, is_voice=(source == "voice"))
    except Exception as e:  # noqa: BLE001
        log.error("orchestrator.extract_failed", error=str(e))
        return replies.generic_error(lang), None, None

    extraction_json = extraction.model_dump()

    if extraction.needs_clarification and extraction.clarification_question:
        return replies.need_clarification(extraction.clarification_question, lang), extraction_json, None

    # ---- Dispatch on intent --------------------------------
    if extraction.intent == Intent.TRANSACTION and extraction.transaction:
        reply, txn_id = await _handle_transaction(
            shopkeeper, extraction, lang,
            raw_message=raw_message, transcript=transcript, source=source,
        )
        return reply, extraction_json, txn_id

    if extraction.intent == Intent.QUERY and extraction.query:
        reply = await _handle_query(shopkeeper, extraction, lang)
        return reply, extraction_json, None

    if extraction.intent == Intent.CORRECTION:
        removed = await db.soft_delete_last_transaction(str(shopkeeper["id"]))
        return (
            replies.undo_success(lang) if removed else replies.undo_nothing(lang),
            extraction_json, None,
        )

    # Greeting / other
    if extraction.clarification_question:
        return extraction.clarification_question, extraction_json, None

    # Friendly default
    default = (
        "Assalam-o-alaikum! Aap koi transaction likhein ya 'aaj ki sales' pooch lein."
        if lang != "english"
        else "Hi! Log a transaction or ask 'today's sales'."
    )
    return default, extraction_json, None


# --------------------------------------------------------
# Transaction handler
# --------------------------------------------------------

async def _handle_transaction(
    shopkeeper: dict,
    extraction: ExtractionResult,
    lang: str,
    *,
    raw_message: str | None,
    transcript: str | None,
    source: str,
) -> tuple[str, str | None]:
    txn = extraction.transaction
    assert txn is not None
    sk_id = str(shopkeeper["id"])
    ttype = txn.transaction_type

    # Resolve contact if one is named / required
    contact = None
    needs_contact = ttype in {
        TransactionType.SALE_CREDIT,
        TransactionType.PAYMENT_RECEIVED,
        TransactionType.PAYMENT_MADE,
        TransactionType.SUPPLIER_PURCHASE,
    }

    if txn.customer_name:
        contact_type = (
            "supplier"
            if ttype in {TransactionType.PAYMENT_MADE, TransactionType.SUPPLIER_PURCHASE}
            else "customer"
        )
        try:
            contact = await resolve_contact(sk_id, txn.customer_name, contact_type)
        except UnconfirmedContact as exc:
            pending = {
                "mode": "confirmation",
                "ttype": ttype.value,
                "amount": txn.amount,
                "items": [i.model_dump() for i in txn.items] if txn.items else None,
                "notes": txn.notes,
                "contact_type": contact_type,
                "source": source,
                "raw_message": raw_message,
                "transcript": transcript,
                "new_name": txn.customer_name,
                "existing": {"id": str(exc.match["id"]), "name": exc.match["name"]},
            }
            await db.update_shopkeeper(
                sk_id,
                bot_state="awaiting_contact_confirm",
                pending_tx=json.dumps(pending),
            )
            return replies.ask_contact_confirm(
                txn.customer_name, exc.match["name"], lang
            ), None
        except AmbiguousContact as exc:
            # Fetch balances for each candidate so we can show them
            bal_rows = await db.get_contact_balances(sk_id)
            bal_map = {str(r["contact_id"]): float(r["balance"]) for r in bal_rows}
            candidates = [
                {**c, "balance": bal_map.get(str(c["id"]), 0.0)}
                for c in exc.matches
            ]
            pending = {
                "ttype": ttype.value,
                "amount": txn.amount,
                "items": [i.model_dump() for i in txn.items] if txn.items else None,
                "notes": txn.notes,
                "contact_type": contact_type,
                "source": source,
                "raw_message": raw_message,
                "transcript": transcript,
                "candidates": [
                    {"id": str(c["id"]), "name": c["name"], "balance": c["balance"]}
                    for c in candidates
                ],
            }
            await db.update_shopkeeper(
                sk_id,
                bot_state="awaiting_disambiguation",
                pending_tx=json.dumps(pending),
            )
            return replies.ask_disambiguation(candidates, lang), None
    elif needs_contact:
        # LLM flagged as credit/payment but didn't give a name — ask.
        q = (
            "Kis ka naam likhoon? (e.g. 'Ahmed')"
            if lang != "english"
            else "Which customer/supplier? (please give a name)"
        )
        return q, None

    # Insert the transaction
    items = [i.model_dump() for i in txn.items] if txn.items else None
    new_row = await db.insert_transaction(
        shopkeeper_id=sk_id,
        contact_id=str(contact["id"]) if contact else None,
        type_=ttype.value,
        amount=txn.amount,
        items=items,
        notes=txn.notes,
        raw_message=raw_message,
        transcript=transcript,
        source=source,
    )
    txn_id = str(new_row["id"])

    # Compose reply based on type
    if ttype == TransactionType.SALE_CASH:
        today = date.today()
        agg = await db.compute_daily_aggregates(sk_id, today, shopkeeper.get("timezone", "Asia/Karachi"))
        return replies.confirm_sale_cash(txn.amount, agg["cash_sales"], lang), txn_id

    # All other types have a contact
    assert contact is not None
    bal_row = await db.get_contact_balances(sk_id, min_balance=None)
    # Find this contact's updated balance
    this_bal = next(
        (r for r in bal_row if str(r["contact_id"]) == str(contact["id"])),
        None,
    )
    balance = float(this_bal["balance"]) if this_bal else 0.0

    name = contact["name"]
    if ttype == TransactionType.SALE_CREDIT:
        return replies.confirm_sale_credit(name, txn.amount, balance, lang), txn_id
    if ttype == TransactionType.PAYMENT_RECEIVED:
        return replies.confirm_payment_received(name, txn.amount, balance, lang), txn_id
    if ttype == TransactionType.PAYMENT_MADE:
        return replies.confirm_payment_made(name, txn.amount, balance, lang), txn_id
    if ttype == TransactionType.SUPPLIER_PURCHASE:
        return replies.confirm_supplier_purchase(name, txn.amount, balance, lang), txn_id

    return replies.generic_error(lang), txn_id


# --------------------------------------------------------
# Query handler
# --------------------------------------------------------

async def _handle_query(
    shopkeeper: dict, extraction: ExtractionResult, lang: str,
) -> str:
    q = extraction.query
    assert q is not None
    sk_id = str(shopkeeper["id"])
    tz = shopkeeper.get("timezone", "Asia/Karachi")

    if q.query_type == QueryType.DAILY_SALES:
        day = _date_from_range(q.date_range, tz)
        agg = await db.compute_daily_aggregates(sk_id, day, tz)
        return replies.reply_daily_sales(agg["cash_sales"], agg["credit_sales"], lang)

    if q.query_type == QueryType.WHO_OWES_ME:
        rows = await db.get_contact_balances(sk_id, contact_type="customer", min_balance=0.01)
        rows = [r for r in rows if float(r["balance"]) > 0]
        return replies.reply_who_owes_me(rows, lang)

    if q.query_type == QueryType.WHO_I_OWE:
        rows = await db.get_contact_balances(sk_id, contact_type="supplier")
        rows = [r for r in rows if float(r["balance"]) < 0]
        # Sort by abs
        rows.sort(key=lambda r: float(r["balance"]))
        return replies.reply_who_i_owe(rows, lang)

    if q.query_type == QueryType.CUSTOMER_BALANCE:
        if not q.customer_name:
            return (
                "Kis ka balance? Naam bata dein."
                if lang != "english"
                else "Whose balance? Please provide a name."
            )
        row = await db.get_contact_balance_by_name(sk_id, q.customer_name)
        if not row:
            return replies.reply_customer_not_found(q.customer_name, lang)
        return replies.reply_customer_balance(row["name"], float(row["balance"]), lang)

    if q.query_type == QueryType.DAILY_SUMMARY:
        from .daily_summary import build_daily_summary_text
        day = _date_from_range(q.date_range, tz)
        return await build_daily_summary_text(shopkeeper, day)

    return replies.generic_error(lang)


async def _handle_contact_confirm(
    shopkeeper: dict, text: str, lang: str,
) -> tuple[str, dict | None, str | None]:
    sk_id = str(shopkeeper["id"])
    raw_pending = shopkeeper.get("pending_tx")
    if not raw_pending:
        await db.update_shopkeeper(sk_id, bot_state="idle")
        return replies.generic_error(lang), None, None

    pending = json.loads(raw_pending) if isinstance(raw_pending, str) else raw_pending
    choice = text.strip().lower()
    yes = choice in {"1", "haan", "han", "ha", "yes", "y", "same", "wohi"}
    no  = choice in {"2", "nahi", "nai", "no", "n", "naya", "new"}

    if not yes and not no:
        return replies.ask_contact_confirm(
            pending["new_name"], pending["existing"]["name"], lang
        ), None, None

    await db.update_shopkeeper(sk_id, bot_state="idle", pending_tx=None)

    if yes:
        contact_name = pending["existing"]["name"]
    else:
        contact_name = pending["new_name"]

    contact_row = await db.find_or_create_contact(
        sk_id, contact_name, pending["contact_type"]
    )
    mark_confirmed(sk_id, str(contact_row["id"]))
    ttype = TransactionType(pending["ttype"])
    new_row = await db.insert_transaction(
        shopkeeper_id=sk_id,
        contact_id=str(contact_row["id"]),
        type_=ttype.value,
        amount=pending["amount"],
        items=pending.get("items"),
        notes=pending.get("notes"),
        raw_message=pending.get("raw_message"),
        transcript=pending.get("transcript"),
        source=pending.get("source", "text"),
    )
    txn_id = str(new_row["id"])
    bal_rows = await db.get_contact_balances(sk_id)
    bal_map = {str(r["contact_id"]): float(r["balance"]) for r in bal_rows}
    balance = bal_map.get(str(contact_row["id"]), 0.0)
    name = contact_row["name"]

    if ttype == TransactionType.SALE_CREDIT:
        return replies.confirm_sale_credit(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.PAYMENT_RECEIVED:
        return replies.confirm_payment_received(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.PAYMENT_MADE:
        return replies.confirm_payment_made(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.SUPPLIER_PURCHASE:
        return replies.confirm_supplier_purchase(name, pending["amount"], balance, lang), None, txn_id
    return replies.generic_error(lang), None, txn_id


async def _handle_disambiguation(
    shopkeeper: dict, text: str, lang: str,
) -> tuple[str, dict | None, str | None]:
    sk_id = str(shopkeeper["id"])
    raw_pending = shopkeeper.get("pending_tx")
    if not raw_pending:
        await db.update_shopkeeper(sk_id, bot_state="idle")
        return replies.generic_error(lang), None, None

    pending = json.loads(raw_pending) if isinstance(raw_pending, str) else raw_pending
    candidates = pending.get("candidates", [])

    # Try numeric choice first, then name match
    choice = text.strip()
    selected = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(candidates):
            selected = candidates[idx]
    else:
        from ..utils.names import normalize_name
        norm = normalize_name(choice)
        for c in candidates:
            if normalize_name(c["name"]) == norm:
                selected = c
                break

    if not selected:
        # Ask again
        return replies.ask_disambiguation(candidates, lang), None, None

    await db.update_shopkeeper(sk_id, bot_state="idle", pending_tx=None)

    contact_row = await db.find_or_create_contact(
        sk_id, selected["name"], pending["contact_type"]
    )
    mark_confirmed(sk_id, str(contact_row["id"]))
    ttype = TransactionType(pending["ttype"])
    new_row = await db.insert_transaction(
        shopkeeper_id=sk_id,
        contact_id=str(contact_row["id"]),
        type_=ttype.value,
        amount=pending["amount"],
        items=pending.get("items"),
        notes=pending.get("notes"),
        raw_message=pending.get("raw_message"),
        transcript=pending.get("transcript"),
        source=pending.get("source", "text"),
    )
    txn_id = str(new_row["id"])

    bal_rows = await db.get_contact_balances(sk_id)
    bal_map = {str(r["contact_id"]): float(r["balance"]) for r in bal_rows}
    balance = bal_map.get(str(contact_row["id"]), 0.0)
    name = contact_row["name"]

    if ttype == TransactionType.SALE_CREDIT:
        return replies.confirm_sale_credit(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.PAYMENT_RECEIVED:
        return replies.confirm_payment_received(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.PAYMENT_MADE:
        return replies.confirm_payment_made(name, pending["amount"], balance, lang), None, txn_id
    if ttype == TransactionType.SUPPLIER_PURCHASE:
        return replies.confirm_supplier_purchase(name, pending["amount"], balance, lang), None, txn_id
    return replies.generic_error(lang), None, txn_id


def _date_from_range(rng: str, tz: str) -> date:
    now = datetime.now(ZoneInfo(tz))
    if rng == "yesterday":
        from datetime import timedelta
        return (now - timedelta(days=1)).date()
    return now.date()
