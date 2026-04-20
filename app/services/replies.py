"""
Reply formatting.

We use simple string templates rather than another LLM call for replies.
This keeps latency low, makes behaviour deterministic, and saves cost.
Three language variants are supported: roman_urdu (default), urdu, english.
"""
from __future__ import annotations
from datetime import date

Lang = str  # 'roman_urdu' | 'urdu' | 'english'


def _fmt_money(amount: float) -> str:
    # PKR values are typically whole numbers; show decimals only if needed.
    if amount == int(amount):
        return f"PKR {int(amount):,}"
    return f"PKR {amount:,.2f}"


# ============================================================
# Transaction confirmations
# ============================================================

def confirm_sale_credit(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(balance)
    if lang == "urdu":
        return f"✅ {name} ko {m} udhaar. Kul udhaar: {b}\n\nGhalat hai? 'undo' likhein."
    if lang == "english":
        return f"✅ Credit sale to {name}: {m}. Total owed by {name}: {b}\n\nWrong? Reply 'undo'."
    return f"✅ {name} ko {m} udhaar. Kul udhaar {name} ka: {b}\n\nGhalat hai? 'undo' likhein."


def confirm_sale_cash(amount: float, today_total: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    t = _fmt_money(today_total)
    if lang == "english":
        return f"✅ Cash sale {m}. Today's cash total: {t}\n\nWrong? Reply 'undo'."
    return f"✅ Cash sale {m} likh di. Aaj ki cash sales: {t}\n\nGhalat hai? 'undo' likhein."


def confirm_payment_received(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(balance)
    if lang == "english":
        tail = f"{name} still owes {b}." if balance > 0 else f"{name}'s balance is clear. ✅"
        return f"✅ Received {m} from {name}. {tail}\n\nWrong? Reply 'undo'."
    tail = (
        f"{name} ka baqi udhaar: {b}" if balance > 0
        else f"{name} ka hisaab clear ho gaya. ✅"
    )
    return f"✅ {name} se {m} received. {tail}\n\nGhalat hai? 'undo' likhein."


def confirm_payment_made(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(abs(balance))
    if lang == "english":
        tail = f"You still owe {name} {b}." if balance < 0 else "Balance clear."
        return f"✅ Paid {m} to {name}. {tail}\n\nWrong? Reply 'undo'."
    tail = (
        f"Aap ko {name} ko abhi aur {b} dene hain." if balance < 0
        else f"{name} ka hisaab clear."
    )
    return f"✅ {name} ko {m} diye. {tail}\n\nGhalat hai? 'undo' likhein."


def confirm_supplier_purchase(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(abs(balance))
    if lang == "english":
        return f"✅ Purchased {m} from {name} on credit. You owe {name} {b}.\n\nWrong? Reply 'undo'."
    return f"✅ {name} se {m} ka maal udhaar liya. {name} ko dena hai: {b}\n\nGhalat hai? 'undo' likhein."


# ============================================================
# Query replies
# ============================================================

def reply_daily_sales(cash: float, credit: float, lang: Lang = "roman_urdu") -> str:
    c = _fmt_money(cash)
    u = _fmt_money(credit)
    total = _fmt_money(cash + credit)
    if lang == "english":
        return f"📊 Today's sales:\n• Cash: {c}\n• Credit: {u}\n• Total: {total}"
    return f"📊 Aaj ki sales:\n• Cash: {c}\n• Udhaar: {u}\n• Total: {total}"


def reply_who_owes_me(rows: list[dict], lang: Lang = "roman_urdu") -> str:
    if not rows:
        return (
            "Abhi kisi ka udhaar baqi nahi. ✅"
            if lang != "english"
            else "No one owes you money right now. ✅"
        )
    header = "🔴 Udhaar lene wale:" if lang != "english" else "🔴 Customers who owe you:"
    lines = [header]
    total = 0.0
    for r in rows[:15]:
        bal = float(r["balance"])
        total += bal
        lines.append(f"• {r['name']} — {_fmt_money(bal)}")
    if len(rows) > 15:
        lines.append(f"... aur {len(rows) - 15} log" if lang != "english" else f"... and {len(rows)-15} more")
    lines.append("")
    lines.append(
        f"Kul: {_fmt_money(total)}" if lang != "english" else f"Total: {_fmt_money(total)}"
    )
    return "\n".join(lines)


def reply_who_i_owe(rows: list[dict], lang: Lang = "roman_urdu") -> str:
    if not rows:
        return (
            "Aap par kisi supplier ka baqi nahi. ✅"
            if lang != "english"
            else "You don't owe any supplier right now. ✅"
        )
    header = "🟢 Supplier ko dene hain:" if lang != "english" else "🟢 Suppliers you owe:"
    lines = [header]
    total = 0.0
    for r in rows[:15]:
        bal = abs(float(r["balance"]))
        total += bal
        lines.append(f"• {r['name']} — {_fmt_money(bal)}")
    lines.append("")
    lines.append(
        f"Kul: {_fmt_money(total)}" if lang != "english" else f"Total: {_fmt_money(total)}"
    )
    return "\n".join(lines)


def reply_customer_balance(name: str, balance: float, lang: Lang = "roman_urdu") -> str:
    if balance == 0:
        return (
            f"{name} ka hisaab clear hai. ✅"
            if lang != "english"
            else f"{name}'s balance is clear. ✅"
        )
    if balance > 0:
        return (
            f"{name} ne aap ko {_fmt_money(balance)} dene hain."
            if lang != "english"
            else f"{name} owes you {_fmt_money(balance)}."
        )
    return (
        f"Aap ko {name} ko {_fmt_money(abs(balance))} dene hain."
        if lang != "english"
        else f"You owe {name} {_fmt_money(abs(balance))}."
    )


def reply_customer_not_found(name: str, lang: Lang = "roman_urdu") -> str:
    return (
        f"'{name}' naam ka koi customer nahi mila. Spelling check karein."
        if lang != "english"
        else f"No customer found with name '{name}'. Please check the spelling."
    )


# ============================================================
# Daily summary
# ============================================================

def format_daily_summary(
    summary_date: date,
    cash_sales: float,
    credit_sales: float,
    payments_received: float,
    payments_made: float,
    top_debtors: list[dict],
    top_suppliers: list[dict],
    lang: Lang = "roman_urdu",
) -> str:
    net = cash_sales + payments_received - payments_made
    is_en = lang == "english"
    title = "🧾 Daily Summary" if is_en else "🧾 Aaj ka Hisaab"
    lines = [
        f"{title} — {summary_date.strftime('%d %b %Y')}",
        "",
        f"💰 {'Cash sales' if is_en else 'Cash Sales'}: {_fmt_money(cash_sales)}",
        f"📝 {'Credit sales' if is_en else 'Udhaar Sales'}: {_fmt_money(credit_sales)}",
        f"💵 {'Payments received' if is_en else 'Paisay Mile'}: {_fmt_money(payments_received)}",
        f"📦 {'Paid to suppliers' if is_en else 'Supplier ko Diye'}: {_fmt_money(payments_made)}",
    ]
    if top_debtors:
        lines.append("")
        lines.append("🔴 " + ("Top people who owe you:" if is_en else "Udhaar Lene Wale (Top):"))
        for r in top_debtors[:5]:
            lines.append(f"• {r['name']} — {_fmt_money(float(r['balance']))}")
    if top_suppliers:
        lines.append("")
        lines.append("🟢 " + ("Top suppliers you owe:" if is_en else "Supplier ko Dene Hain:"))
        for r in top_suppliers[:5]:
            lines.append(f"• {r['name']} — {_fmt_money(abs(float(r['balance'])))}")
    lines.append("")
    lines.append(
        f"{'Net today' if is_en else 'Net aaj'}: {'+' if net >= 0 else ''}{_fmt_money(net)}"
    )
    lines.append("")
    lines.append("Barkat ho! 🌙" if not is_en else "Have a good evening! 🌙")
    return "\n".join(lines)


# ============================================================
# Onboarding & misc
# ============================================================

def onboarding_welcome(lang: Lang = "roman_urdu") -> str:
    return (
        "Assalam-o-alaikum! 🌙\n\n"
        "Main aap ka WhatsApp hisaab-assistant hoon. Aap mujhe text ya voice note bhej "
        "sakte hain — main sab kuch likh lunga.\n\n"
        "Examples:\n"
        "• \"Ahmed ko 500 udhaar diya\"\n"
        "• \"Bilal se 1200 wapas mile\"\n"
        "• \"2 kg cheeni 300 cash\"\n"
        "• \"aaj ki sales kitni hai?\"\n"
        "• \"kaun kaun udhaar par hai?\"\n\n"
        "Pehle mujhe apni dukaan ka naam bata dein."
    )


def onboarding_ask_shop_name(lang: Lang = "roman_urdu") -> str:
    return "Apni dukaan ka naam likhein (e.g. 'Ahmed General Store')."


def onboarding_done(shop_name: str, lang: Lang = "roman_urdu") -> str:
    return (
        f"✅ {shop_name} — set ho gaya.\n\n"
        "Ab jab bhi koi sale, udhaar, ya payment ho, mujhe bata dein. "
        "Shaam ko 9 baje main aap ko full hisaab bhejunga.\n\n"
        "Kabhi bhi 'aaj ki sales' ya 'kaun udhaar par hai' pooch lein."
    )


def undo_success(lang: Lang = "roman_urdu") -> str:
    return (
        "✅ Last entry hata di."
        if lang != "english"
        else "✅ Last entry removed."
    )


def undo_nothing(lang: Lang = "roman_urdu") -> str:
    return (
        "Koi entry nahi mili jisay hata sakein."
        if lang != "english"
        else "No entry found to remove."
    )


def need_clarification(q: str, lang: Lang = "roman_urdu") -> str:
    return q


def generic_error(lang: Lang = "roman_urdu") -> str:
    return (
        "Maaf kijiye, abhi chhoti si dikkat hai. Thori dair baad try karein."
        if lang != "english"
        else "Sorry, something went wrong. Please try again in a moment."
    )
