"""
Reminder scheduler — runs at 9 AM PKT to send due reminders.
"""
from __future__ import annotations
from datetime import date

from ..utils.logging import get_logger
from . import db, whatsapp, replies

log = get_logger("reminders")


async def run_reminders_for_all() -> None:
    today = date.today()
    due = await db.get_due_reminders(today)
    log.info("reminders.run", date=str(today), count=len(due))

    for r in due:
        try:
            lang = r.get("language_pref", "roman_urdu")
            person = r.get("contact_name")  # may be None
            text = replies.reminder_notification(
                description=r["description"],
                amount=float(r["amount"]) if r.get("amount") else None,
                person=person,
                lang=lang,
            )
            await whatsapp.send_text(r["phone_number"], text)
            await db.mark_reminder_sent(str(r["id"]))
            log.info("reminder.sent", id=str(r["id"]), phone=r["phone_number"])
        except Exception as exc:
            log.error("reminder.send_failed", id=str(r["id"]), error=str(exc))
