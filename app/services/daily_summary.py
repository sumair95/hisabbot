"""
Daily summary: compute aggregates for a shop on a given date, format a
WhatsApp-ready message, persist to daily_summaries, and (optionally) send
it via WhatsApp.
"""
from __future__ import annotations
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..utils.logging import get_logger
from . import db, replies, whatsapp

log = get_logger("daily_summary")


async def build_daily_summary_text(shopkeeper: dict, day: date | None = None) -> str:
    sk_id = str(shopkeeper["id"])
    tz = shopkeeper.get("timezone", "Asia/Karachi")
    lang = shopkeeper.get("language_pref") or "roman_urdu"
    day = day or datetime.now(ZoneInfo(tz)).date()

    agg = await db.compute_daily_aggregates(sk_id, day, tz)

    customers = await db.get_contact_balances(sk_id, contact_type="customer")
    top_debtors = sorted(
        [r for r in customers if float(r["balance"]) > 0],
        key=lambda r: -float(r["balance"]),
    )

    suppliers = await db.get_contact_balances(sk_id, contact_type="supplier")
    top_suppliers = sorted(
        [r for r in suppliers if float(r["balance"]) < 0],
        key=lambda r: float(r["balance"]),
    )

    text = replies.format_daily_summary(
        summary_date=day,
        cash_sales=agg["cash_sales"],
        credit_sales=agg["credit_sales"],
        payments_received=agg["payments_received"],
        payments_made=agg["payments_made"],
        top_debtors=top_debtors,
        top_suppliers=top_suppliers,
        lang=lang,
    )

    await db.save_daily_summary(sk_id, day, agg, text)
    return text


async def run_daily_summary_for_all() -> int:
    """
    Iterate all active shopkeepers and send their daily summary.

    Note on WhatsApp 24h rule: proactively-initiated messages outside the
    user's 24h window require an approved template. In MVP we try to send
    plain text; if the recipient messaged today (most active shops do),
    this works. If not, we save the summary to DB and it will be
    delivered the next time the shopkeeper messages, or via a pre-approved
    template once one is registered (see docs/WHATSAPP_SETUP.md).
    """
    sent = 0
    async with db.conn() as c:
        rows = await c.fetch(
            "SELECT * FROM shopkeepers WHERE onboarding_state = 'done'"
        )
    for r in rows:
        sk = dict(r)
        try:
            text = await build_daily_summary_text(sk)
            try:
                await whatsapp.send_text(sk["phone_number"], text)
                sent += 1
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "daily_summary.send_failed",
                    shop=str(sk["id"]), error=str(e),
                    note="likely outside 24h window — template needed",
                )
        except Exception as e:  # noqa: BLE001
            log.error("daily_summary.build_failed", shop=str(sk["id"]), error=str(e))
    log.info("daily_summary.batch_done", sent=sent, total=len(rows))
    return sent
