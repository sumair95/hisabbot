"""
Thin async Postgres wrapper over asyncpg.
Intentionally no ORM — queries are few, simple, and better read as SQL.
"""
from __future__ import annotations
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
import asyncpg

from ..config import get_settings
from ..utils.logging import get_logger
from ..utils.names import normalize_name

log = get_logger("db")

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    settings = get_settings()
    if not settings.supabase_db_url or "YOUR-PROJECT" in settings.supabase_db_url:
        log.warning("SUPABASE_DB_URL not configured — DB is disabled")
        return
    _pool = await asyncpg.create_pool(
        dsn=settings.supabase_db_url,
        min_size=1,
        max_size=5,
        statement_cache_size=0,  # Supabase pgbouncer compatibility
        command_timeout=15,
        ssl="require",
    )
    log.info("db.pool.ready")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def conn():
    if _pool is None:
        raise RuntimeError("DB pool not initialised. Set SUPABASE_DB_URL and restart.")
    async with _pool.acquire() as c:
        yield c


# =====================================================
# Shopkeeper ops
# =====================================================

async def get_or_create_shopkeeper(phone_number: str) -> dict[str, Any]:
    async with conn() as c:
        row = await c.fetchrow(
            "SELECT * FROM shopkeepers WHERE phone_number = $1", phone_number
        )
        if row:
            return dict(row)
        row = await c.fetchrow(
            """
            INSERT INTO shopkeepers (phone_number, onboarding_state, subscription_status)
            VALUES ($1, 'new', 'trial')
            RETURNING *
            """,
            phone_number,
        )
        log.info("shopkeeper.created", phone=phone_number)
        return dict(row)


async def update_shopkeeper(sk_id: str, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields.keys()))
    async with conn() as c:
        await c.execute(
            f"UPDATE shopkeepers SET {sets} WHERE id = $1",
            sk_id,
            *fields.values(),
        )


# =====================================================
# Contact ops
# =====================================================

async def get_contact_by_id(contact_id: str) -> dict[str, Any] | None:
    async with conn() as c:
        row = await c.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
    return dict(row) if row else None


async def create_contact(
    shopkeeper_id: str, name: str, contact_type: str = "customer",
) -> dict[str, Any]:
    from ..utils.names import normalize_name as _norm
    from .contact_matching import _invalidate
    norm = _norm(name)
    async with conn() as c:
        row = await c.fetchrow(
            """
            INSERT INTO contacts (shopkeeper_id, name, normalized_name, type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (shopkeeper_id, normalized_name, type) DO UPDATE
              SET name = EXCLUDED.name
            RETURNING *
            """,
            shopkeeper_id, name.strip(), norm, contact_type,
        )
    _invalidate(shopkeeper_id)
    return dict(row)


async def find_or_create_contact(
    shopkeeper_id: str,
    name: str,
    contact_type: str = "customer",
) -> dict[str, Any]:
    """Find by exact normalized name, else fuzzy match, else create."""
    from .contact_matching import resolve_contact  # local import avoids cycle
    return await resolve_contact(shopkeeper_id, name, contact_type)


async def get_contacts(shopkeeper_id: str, contact_type: str | None = None) -> list[dict]:
    async with conn() as c:
        if contact_type:
            rows = await c.fetch(
                "SELECT * FROM contacts WHERE shopkeeper_id = $1 AND type = $2",
                shopkeeper_id, contact_type,
            )
        else:
            rows = await c.fetch(
                "SELECT * FROM contacts WHERE shopkeeper_id = $1", shopkeeper_id
            )
    return [dict(r) for r in rows]


async def get_contact_balances(
    shopkeeper_id: str, contact_type: str | None = None, min_balance: float | None = None,
) -> list[dict]:
    q = "SELECT * FROM v_contact_balances WHERE shopkeeper_id = $1"
    params: list[Any] = [shopkeeper_id]
    if contact_type:
        params.append(contact_type)
        q += f" AND type = ${len(params)}"
    if min_balance is not None:
        params.append(min_balance)
        q += f" AND balance >= ${len(params)}"
    q += " ORDER BY balance DESC"
    async with conn() as c:
        rows = await c.fetch(q, *params)
    return [dict(r) for r in rows]


async def get_contact_balance_by_name(
    shopkeeper_id: str, name: str,
) -> dict | None:
    """Look up a named contact's balance, using the same matcher used at write time."""
    from .contact_matching import find_contact_by_name
    contact = await find_contact_by_name(shopkeeper_id, name)
    if not contact:
        return None
    async with conn() as c:
        row = await c.fetchrow(
            "SELECT * FROM v_contact_balances WHERE contact_id = $1",
            contact["id"],
        )
    return dict(row) if row else None


# =====================================================
# Transaction ops
# =====================================================

async def insert_transaction(
    shopkeeper_id: str,
    contact_id: str | None,
    type_: str,
    amount: float,
    *,
    items: list[dict] | None = None,
    notes: str | None = None,
    raw_message: str | None = None,
    transcript: str | None = None,
    source: str = "text",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    occurred_at = occurred_at or datetime.now(timezone.utc)
    async with conn() as c:
        row = await c.fetchrow(
            """
            INSERT INTO transactions
              (shopkeeper_id, contact_id, type, amount, items, notes,
               raw_message, transcript, source, occurred_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING *
            """,
            shopkeeper_id, contact_id, type_, amount,
            json.dumps(items) if items else None,
            notes, raw_message, transcript, source, occurred_at,
        )
    return dict(row)


async def soft_delete_last_transaction(
    shopkeeper_id: str, reason: str = "user_undo",
) -> dict | None:
    async with conn() as c:
        row = await c.fetchrow(
            """
            UPDATE transactions
               SET is_deleted = TRUE, deleted_at = NOW(), deleted_reason = $2
             WHERE id = (
                 SELECT id FROM transactions
                  WHERE shopkeeper_id = $1 AND is_deleted = FALSE
                  ORDER BY created_at DESC
                  LIMIT 1
             )
            RETURNING *
            """,
            shopkeeper_id, reason,
        )
    return dict(row) if row else None


# =====================================================
# Message log (audit trail)
# =====================================================

async def log_message(
    *,
    shopkeeper_id: str | None,
    wa_message_id: str | None,
    direction: str,
    kind: str = "text",
    content: str | None = None,
    media_url: str | None = None,
    transcript: str | None = None,
    intent: str | None = None,
    extraction_json: dict | None = None,
    transaction_id: str | None = None,
) -> str:
    async with conn() as c:
        row = await c.fetchrow(
            """
            INSERT INTO messages
              (shopkeeper_id, wa_message_id, direction, kind, content,
               media_url, transcript, intent, extraction_json, transaction_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id
            """,
            shopkeeper_id, wa_message_id, direction, kind, content,
            media_url, transcript, intent,
            json.dumps(extraction_json) if extraction_json else None,
            transaction_id,
        )
    return str(row["id"])


async def was_wa_message_processed(wa_message_id: str) -> bool:
    """Idempotency check — Meta retries webhooks."""
    if not wa_message_id:
        return False
    async with conn() as c:
        row = await c.fetchrow(
            "SELECT 1 FROM messages WHERE wa_message_id = $1 AND direction = 'inbound' LIMIT 1",
            wa_message_id,
        )
    return row is not None


# =====================================================
# Daily summary ops
# =====================================================

async def compute_daily_aggregates(
    shopkeeper_id: str, day: date, tz: str = "Asia/Karachi",
) -> dict[str, float]:
    """Totals for a specific local-date, in the shop's timezone."""
    async with conn() as c:
        row = await c.fetchrow(
            """
            SELECT
              COALESCE(SUM(CASE WHEN type='sale_cash'        THEN amount END),0) AS cash_sales,
              COALESCE(SUM(CASE WHEN type='sale_credit'      THEN amount END),0) AS credit_sales,
              COALESCE(SUM(CASE WHEN type='payment_received' THEN amount END),0) AS payments_received,
              COALESCE(SUM(CASE WHEN type='payment_made'     THEN amount END),0) AS payments_made
              FROM transactions
             WHERE shopkeeper_id = $1
               AND is_deleted = FALSE
               AND (occurred_at AT TIME ZONE $3)::date = $2
            """,
            shopkeeper_id, day, tz,
        )
    return {k: float(v or 0) for k, v in dict(row).items()}


# =====================================================
# Reminder ops
# =====================================================

async def create_reminder(
    shopkeeper_id: str,
    description: str,
    remind_on: date,
    contact_id: str | None = None,
    amount: float | None = None,
) -> dict[str, Any]:
    async with conn() as c:
        row = await c.fetchrow(
            """
            INSERT INTO reminders (shopkeeper_id, contact_id, amount, description, remind_on)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            shopkeeper_id, contact_id, amount, description, remind_on,
        )
    return dict(row)


async def get_due_reminders(remind_on: date) -> list[dict[str, Any]]:
    async with conn() as c:
        rows = await c.fetch(
            """
            SELECT r.*, s.phone_number, s.language_pref, s.timezone
              FROM reminders r
              JOIN shopkeepers s ON s.id = r.shopkeeper_id
             WHERE r.remind_on = $1 AND r.is_sent = FALSE
            """,
            remind_on,
        )
    return [dict(r) for r in rows]


async def mark_reminder_sent(reminder_id: str) -> None:
    async with conn() as c:
        await c.execute(
            "UPDATE reminders SET is_sent = TRUE, sent_at = NOW() WHERE id = $1",
            reminder_id,
        )


async def get_category_breakdown(
    shopkeeper_id: str, day: date, tz: str = "Asia/Karachi",
) -> list[dict]:
    """
    Returns per-product totals grouped by category for a given local date.
    Only includes transactions that have item-level data (items not null/empty).
    """
    async with conn() as c:
        rows = await c.fetch(
            """
            SELECT
                COALESCE(item->>'category', 'other')   AS category,
                COALESCE(item->>'name',     'unknown') AS product,
                COALESCE(SUM((item->>'price')::numeric), 0) AS total_price,
                COALESCE(SUM((item->>'quantity')::numeric), 0) AS total_qty,
                MAX(item->>'unit') AS unit
            FROM transactions,
                 jsonb_array_elements(items) AS item
            WHERE shopkeeper_id = $1
              AND is_deleted = FALSE
              AND items IS NOT NULL
              AND items != 'null'::jsonb
              AND jsonb_array_length(items) > 0
              AND (occurred_at AT TIME ZONE $2)::date = $3
            GROUP BY category, product
            ORDER BY category, total_price DESC
            """,
            shopkeeper_id, tz, day,
        )
    return [dict(r) for r in rows]


async def count_voice_today(shopkeeper_id: str, tz: str = "Asia/Karachi") -> int:
    today = datetime.now(ZoneInfo(tz)).date()
    async with conn() as c:
        row = await c.fetchrow(
            """
            SELECT COUNT(*) AS cnt FROM messages
             WHERE shopkeeper_id = $1
               AND direction = 'inbound'
               AND kind = 'voice'
               AND (created_at AT TIME ZONE $2)::date = $3
            """,
            shopkeeper_id, tz, today,
        )
    return int(row["cnt"])


async def save_daily_summary(
    shopkeeper_id: str, day: date, aggregates: dict, summary_text: str,
) -> None:
    net = (
        aggregates["cash_sales"]
        + aggregates["payments_received"]
        - aggregates["payments_made"]
    )
    async with conn() as c:
        await c.execute(
            """
            INSERT INTO daily_summaries
              (shopkeeper_id, summary_date, total_cash_sales, total_credit_sales,
               total_payments_received, total_payments_made, net_for_day, summary_text)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (shopkeeper_id, summary_date) DO UPDATE SET
              total_cash_sales        = EXCLUDED.total_cash_sales,
              total_credit_sales      = EXCLUDED.total_credit_sales,
              total_payments_received = EXCLUDED.total_payments_received,
              total_payments_made     = EXCLUDED.total_payments_made,
              net_for_day             = EXCLUDED.net_for_day,
              summary_text            = EXCLUDED.summary_text
            """,
            shopkeeper_id, day,
            aggregates["cash_sales"], aggregates["credit_sales"],
            aggregates["payments_received"], aggregates["payments_made"],
            net, summary_text,
        )
