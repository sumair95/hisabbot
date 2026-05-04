"""
Reply formatting.

We use simple string templates rather than another LLM call for replies.
This keeps latency low, makes behaviour deterministic, and saves cost.
Three language variants are supported: roman_urdu (default), urdu, english.
"""
from __future__ import annotations
from datetime import date

Lang = str  # 'roman_urdu' | 'urdu' | 'english'


_CATEGORY_ROMAN = {
    "grains":        "Anaj",
    "drinks":        "Drinks",
    "snacks":        "Snacks",
    "oil_ghee":      "Ghee/Oil",
    "spices":        "Masalay",
    "soap_cleaning": "Sabun/Safai",
    "tobacco":       "Cigarette",
    "dairy_eggs":    "Dairy/Anda",
    "sweets":        "Mithai",
    "other":         "Doosri Cheez",
}
_CATEGORY_URDU = {
    "grains":        "اناج",
    "drinks":        "مشروبات",
    "snacks":        "اسنیکس",
    "oil_ghee":      "گھی/تیل",
    "spices":        "مسالے",
    "soap_cleaning": "صابن/صفائی",
    "tobacco":       "سگریٹ",
    "dairy_eggs":    "ڈیری/انڈے",
    "sweets":        "مٹھائی",
    "other":         "دیگر",
}


def _fmt_items(items: list, lang: Lang) -> str:
    """One-line summary of items for use in confirmations."""
    if not items:
        return ""
    parts = []
    for it in items[:3]:
        name = it.get("name", "") if isinstance(it, dict) else getattr(it, "name", "")
        cat  = it.get("category") if isinstance(it, dict) else getattr(it, "category", None)
        qty  = it.get("quantity") if isinstance(it, dict) else getattr(it, "quantity", None)
        unit = it.get("unit") if isinstance(it, dict) else getattr(it, "unit", None)

        if lang == "urdu":
            cat_label = _CATEGORY_URDU.get(cat, "") if cat else ""
        else:
            cat_label = _CATEGORY_ROMAN.get(cat, "") if cat else ""

        price = it.get("price") if isinstance(it, dict) else getattr(it, "price", None)

        piece = name.capitalize()
        if qty and unit:
            piece += f" {int(qty) if qty == int(qty) else qty} {unit}"
        elif qty:
            piece += f" x{int(qty)}"
        if price:
            piece += f" — {_fmt_money(price)}"
        if cat_label:
            piece += f" ({cat_label})"
        parts.append(piece)
    return ", ".join(parts)


def _fmt_money(amount: float) -> str:
    if amount == int(amount):
        return f"PKR {int(amount):,}"
    return f"PKR {amount:,.2f}"


# ============================================================
# Transaction confirmations
# ============================================================

def confirm_sale_credit(name: str, amount: float, balance: float, lang: Lang = "roman_urdu", items: list | None = None) -> str:
    m = _fmt_money(amount)
    b = _fmt_money(balance)
    item_line = f"\n📦 {_fmt_items(items, lang)}" if items else ""
    if lang == "urdu":
        return f"✅ {name} کو {m} ادھار دیا۔{item_line}\nکل ادھار {name} کا: {b}"
    if lang == "english":
        return f"✅ Credit sale to {name}: {m}.{item_line}\nTotal owed by {name}: {b}"
    return f"✅ {name} ko {m} udhaar.{item_line}\nKul udhaar {name} ka: {b}"


def confirm_sale_cash(amount: float, today_total: float, lang: Lang = "roman_urdu", items: list | None = None) -> str:
    """today_total is accepted for backwards compatibility but no longer shown — see daily summary at 10pm."""
    del today_total  # no longer displayed per shopkeeper UX preference
    m = _fmt_money(amount)
    item_line = f"\n📦 {_fmt_items(items, lang)}" if items else ""
    if lang == "urdu":
        return f"✅ {m} نقد فروخت لکھ دی۔{item_line}"
    if lang == "english":
        return f"✅ Cash sale {m}.{item_line}"
    return f"✅ Cash sale {m} likh di.{item_line}"


def confirm_payment_received(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(balance)
    if lang == "urdu":
        tail = f"{name} کا باقی ادھار: {b}" if balance > 0 else f"{name} کا حساب صاف ہو گیا۔ ✅"
        return f"✅ {name} سے {m} ملے۔\n{tail}"
    if lang == "english":
        tail = f"{name} still owes {b}." if balance > 0 else f"{name}'s balance is clear. ✅"
        return f"✅ Received {m} from {name}. {tail}"
    tail = (
        f"{name} ka baqi udhaar: {b}" if balance > 0
        else f"{name} ka hisaab clear ho gaya. ✅"
    )
    return f"✅ {name} se {m} received. {tail}"


def confirm_payment_made(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(abs(balance))
    if lang == "urdu":
        if balance < 0:
            tail = f"ابھی باقی: {name} کو {b} اور دینے ہیں۔"
        elif balance == 0:
            tail = f"{name} کا حساب صاف ہو گیا۔"
        else:
            tail = f"Supplier payment record ہو گئی۔"  # balance > 0: no prior purchase on record
        return f"✅ {name} کو {m} دیے۔\n{tail}"
    if lang == "english":
        if balance < 0:
            tail = f"Still owe {name}: {b}."
        elif balance == 0:
            tail = f"{name}'s balance is now clear."
        else:
            tail = "Supplier payment recorded."
        return f"✅ Paid {m} to {name}. {tail}"
    if balance < 0:
        tail = f"Abhi baqi: {name} ko {b} aur dene hain."
    elif balance == 0:
        tail = f"{name} ka hisaab clear ho gaya."
    else:
        tail = "Supplier payment record ho gayi."
    return f"✅ {name} ko {m} diye. {tail}"


def confirm_supplier_purchase(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(abs(balance))
    if lang == "urdu":
        return f"✅ {name} سے {m} کا مال ادھار لیا۔\n{name} کو دینا ہے: {b}"
    if lang == "english":
        return f"✅ Purchased {m} from {name} on credit. You owe {name} {b}."
    return f"✅ {name} se {m} ka maal udhaar liya. {name} ko dena hai: {b}"


# ============================================================
# Query replies
# ============================================================

def reply_daily_sales(cash: float, credit: float, lang: Lang = "roman_urdu") -> str:
    c = _fmt_money(cash)
    u = _fmt_money(credit)
    total = _fmt_money(cash + credit)
    if lang == "urdu":
        return f"📊 آج کی فروخت:\n• نقد: {c}\n• ادھار: {u}\n• کل: {total}"
    if lang == "english":
        return f"📊 Today's sales:\n• Cash: {c}\n• Credit: {u}\n• Total: {total}"
    return f"📊 Aaj ki sales:\n• Cash: {c}\n• Udhaar: {u}\n• Total: {total}"


def reply_who_owes_me(rows: list[dict], lang: Lang = "roman_urdu") -> str:
    if not rows:
        if lang == "urdu":
            return "ابھی کسی کا ادھار باقی نہیں۔ ✅"
        if lang == "english":
            return "No one owes you money right now. ✅"
        return "Abhi kisi ka udhaar baqi nahi. ✅"
    if lang == "urdu":
        header = "🔴 ادھار لینے والے:"
    elif lang == "english":
        header = "🔴 Customers who owe you:"
    else:
        header = "🔴 Udhaar lene wale:"
    lines = [header]
    total = 0.0
    for r in rows[:15]:
        bal = float(r["balance"])
        total += bal
        lines.append(f"• {r['name']} — {_fmt_money(bal)}")
    if len(rows) > 15:
        lines.append(f"... aur {len(rows) - 15} log" if lang != "english" else f"... and {len(rows)-15} more")
    lines.append("")
    lines.append(f"کل: {_fmt_money(total)}" if lang == "urdu" else
                 f"Total: {_fmt_money(total)}" if lang == "english" else
                 f"Kul: {_fmt_money(total)}")
    return "\n".join(lines)


def reply_who_i_owe(rows: list[dict], lang: Lang = "roman_urdu") -> str:
    if not rows:
        if lang == "urdu":
            return "آپ پر کسی سپلائر کا باقی نہیں۔ ✅"
        if lang == "english":
            return "You don't owe any supplier right now. ✅"
        return "Aap par kisi supplier ka baqi nahi. ✅"
    if lang == "urdu":
        header = "🟢 سپلائر کو دینا ہے:"
    elif lang == "english":
        header = "🟢 Suppliers you owe:"
    else:
        header = "🟢 Supplier ko dene hain:"
    lines = [header]
    total = 0.0
    for r in rows[:15]:
        bal = abs(float(r["balance"]))
        total += bal
        lines.append(f"• {r['name']} — {_fmt_money(bal)}")
    lines.append("")
    lines.append(f"کل: {_fmt_money(total)}" if lang == "urdu" else
                 f"Total: {_fmt_money(total)}" if lang == "english" else
                 f"Kul: {_fmt_money(total)}")
    return "\n".join(lines)


def reply_customer_balance(name: str, balance: float, lang: Lang = "roman_urdu") -> str:
    if balance == 0:
        if lang == "urdu":
            return f"{name} کا حساب صاف ہے۔ ✅"
        if lang == "english":
            return f"{name}'s balance is clear. ✅"
        return f"{name} ka hisaab clear hai. ✅"
    if balance > 0:
        if lang == "urdu":
            return f"{name} نے آپ کو {_fmt_money(balance)} دینے ہیں۔"
        if lang == "english":
            return f"{name} owes you {_fmt_money(balance)}."
        return f"{name} ne aap ko {_fmt_money(balance)} dene hain."
    if lang == "urdu":
        return f"آپ کو {name} کو {_fmt_money(abs(balance))} دینے ہیں۔"
    if lang == "english":
        return f"You owe {name} {_fmt_money(abs(balance))}."
    return f"Aap ko {name} ko {_fmt_money(abs(balance))} dene hain."


def reply_customer_not_found(name: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return f"'{name}' نام کا کوئی کسٹمر نہیں ملا۔ ہجے چیک کریں۔"
    if lang == "english":
        return f"No customer found with name '{name}'. Please check the spelling."
    return f"'{name}' naam ka koi customer nahi mila. Spelling check karein."


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
    total_sales = cash_sales + credit_sales
    date_str = summary_date.strftime('%d %b %Y')

    if lang == "urdu":
        lines = [
            f"🧾 آج کا حساب — {date_str}", "",
            f"💰 نقد فروخت: {_fmt_money(cash_sales)}",
            f"📝 ادھار فروخت: {_fmt_money(credit_sales)}",
            f"💵 پیسے ملے: {_fmt_money(payments_received)}",
            f"📦 سپلائر کو دیے: {_fmt_money(payments_made)}",
        ]
        if top_debtors:
            lines += ["", "🔴 ادھار لینے والے (ٹاپ):"]
            for r in top_debtors[:5]:
                lines.append(f"• {r['name']} — {_fmt_money(float(r['balance']))}")
        if top_suppliers:
            lines += ["", "🟢 سپلائر کو دینا ہے:"]
            for r in top_suppliers[:5]:
                lines.append(f"• {r['name']} — {_fmt_money(abs(float(r['balance'])))}")
        lines += ["", f"کل فروخت: {_fmt_money(total_sales)}", "", "برکت ہو! 🌙"]
        return "\n".join(lines)

    is_en = lang == "english"
    title = "🧾 Daily Summary" if is_en else "🧾 Aaj ka Hisaab"
    lines = [
        f"{title} — {date_str}", "",
        f"💰 {'Cash sales' if is_en else 'Cash Sales'}: {_fmt_money(cash_sales)}",
        f"📝 {'Credit sales' if is_en else 'Udhaar Sales'}: {_fmt_money(credit_sales)}",
        f"💵 {'Payments received' if is_en else 'Paisay Mile'}: {_fmt_money(payments_received)}",
        f"📦 {'Paid to suppliers' if is_en else 'Supplier ko Diye'}: {_fmt_money(payments_made)}",
    ]
    if top_debtors:
        lines += ["", "🔴 " + ("Top people who owe you:" if is_en else "Udhaar Lene Wale (Top):")]
        for r in top_debtors[:5]:
            lines.append(f"• {r['name']} — {_fmt_money(float(r['balance']))}")
    if top_suppliers:
        lines += ["", "🟢 " + ("Top suppliers you owe:" if is_en else "Supplier ko Dene Hain:")]
        for r in top_suppliers[:5]:
            lines.append(f"• {r['name']} — {_fmt_money(abs(float(r['balance'])))}")
    lines += ["", f"{'Total sales' if is_en else 'Kul Sales'}: {_fmt_money(total_sales)}", ""]
    lines.append("Have a good evening! 🌙" if is_en else "Barkat ho! 🌙")
    return "\n".join(lines)


# ============================================================
# Onboarding & misc
# ============================================================

def onboarding_welcome(lang: Lang = "roman_urdu") -> str:
    lang_tip = (
        "🌐 زبان تبدیل کریں:\n"
        "• اردو رسم الخط کے لیے: 'اردو' لکھیں\n"
        "• رومن اردو کے لیے: 'roman urdu'\n"
        "• انگریزی کے لیے: 'english'\n\n"
    )
    if lang == "urdu":
        return (
            "السلام علیکم! 🌙\n\n"
            "میں آپ کا واٹس ایپ حساب کتاب ہوں۔ آپ مجھے ٹیکسٹ یا وائس نوٹ بھیج سکتے ہیں — میں سب کچھ لکھ لوں گا۔\n\n"
            "مثالیں:\n"
            "• \"احمد کو ۵۰۰ ادھار دیا\"\n"
            "• \"بلال سے ۱۲۰۰ واپس ملے\"\n"
            "• \"۲ کلو چینی ۳۰۰ نقد\"\n"
            "• \"آج کی سیلز کتنی ہے؟\"\n\n"
            f"{lang_tip}"
            "پہلے مجھے اپنی دکان کا نام بتائیں۔"
        )
    if lang == "english":
        return (
            "Assalam-o-alaikum! 🌙\n\n"
            "I'm your WhatsApp bookkeeping assistant. Send me text or voice notes — I'll record everything.\n\n"
            "Examples:\n"
            "• \"Ahmed ko 500 udhaar diya\"\n"
            "• \"Bilal se 1200 wapas mile\"\n"
            "• \"2 kg cheeni 300 cash\"\n"
            "• \"Today's sales?\"\n\n"
            "🌐 Change language: type 'اردو' for Urdu script, 'roman urdu', or 'english'\n\n"
            "First, tell me your shop name."
        )
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
        "🌐 Zaban tabdeel karein:\n"
        "• Urdu script ke liye: 'اردو' likhein\n"
        "• Roman Urdu: 'roman urdu'\n"
        "• English: 'english'\n\n"
        "Pehle mujhe apni dukaan ka naam bata dein."
    )


def onboarding_ask_shop_name(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "اپنی دکان کا نام لکھیں (مثلاً 'احمد جنرل اسٹور')۔"
    if lang == "english":
        return "Please type your shop name (e.g. 'Ahmed General Store')."
    return "Apni dukaan ka naam likhein (e.g. 'Ahmed General Store')."


def ask_new_shop_name(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "ٹھیک ہے! نیا دکان کا نام لکھیں۔"
    if lang == "english":
        return "OK! Please type the new shop name."
    return "Theek hai! Naya dukaan ka naam likhein."


def onboarding_done(shop_name: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return (
            f"✅ {shop_name} — سیٹ ہو گیا۔\n\n"
            "اب جب بھی کوئی سیل، ادھار، یا ادائیگی ہو، مجھے بتائیں۔ "
            "رات کو ۱۰ بجے میں آپ کو پورا حساب بھیجوں گا۔\n\n"
            "کبھی بھی 'آج کی سیلز' یا 'کون ادھار پر ہے' پوچھ لیں۔\n\n"
            "🔊 وائس نوٹ میں جواب چاہیے؟ 'voice on' لکھیں۔\n"
            "🔇 بند کرنے کے لیے: 'voice off' لکھیں۔"
        )
    if lang == "english":
        return (
            f"✅ {shop_name} — all set!\n\n"
            "Now whenever there's a sale, credit, or payment, just tell me. "
            "I'll send you a full summary at 10 PM every night.\n\n"
            "Ask anytime: 'today's sales' or 'who owes me'.\n\n"
            "🔊 Want voice replies? Type 'voice on'.\n"
            "🔇 To turn off: 'voice off'."
        )
    return (
        f"✅ {shop_name} — set ho gaya.\n\n"
        "Ab jab bhi koi sale, udhaar, ya payment ho, mujhe bata dein. "
        "Raat ko 10 baje main aap ko full hisaab bhejunga.\n\n"
        "Kabhi bhi 'aaj ki sales' ya 'kaun udhaar par hai' pooch lein.\n\n"
        "🔊 Voice note mein jawab chahiye? 'voice on' likhein.\n"
        "🔇 Band karne ke liye: 'voice off' likhein."
    )


def confirm_reminder(description: str, remind_on: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return f"⏰ یاد رکھوں گا! {remind_on} کو صبح ۹ بجے یاد دہانی بھیجوں گا:\n\"{description}\""
    if lang == "english":
        return f"⏰ Reminder saved! I'll remind you on {remind_on} at 9 AM:\n\"{description}\""
    return f"⏰ Yaad rakhoon ga! {remind_on} ko subah 9 baje reminder bhejunga:\n\"{description}\""


def reminder_notification(description: str, amount: float | None, person: str | None, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        parts = ["⏰ یاد دہانی:", f"\"{description}\""]
        if amount:
            parts.append(f"رقم: PKR {int(amount):,}")
        if person:
            parts.append(f"شخص: {person}")
        return "\n".join(parts)
    if lang == "english":
        parts = ["⏰ Reminder:", f"\"{description}\""]
        if amount:
            parts.append(f"Amount: PKR {int(amount):,}")
        if person:
            parts.append(f"Person: {person}")
        return "\n".join(parts)
    parts = ["⏰ Yaad dihani:", f"\"{description}\""]
    if amount:
        parts.append(f"Raqam: PKR {int(amount):,}")
    if person:
        parts.append(f"Shakhs: {person}")
    return "\n".join(parts)


def ask_contact_confirm(new_name: str, existing_name: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return (
            f"کیا *{new_name}* وہی *{existing_name}* ہے جو پہلے سے ریکارڈ میں ہے؟\n"
            "۱. ہاں، وہی ہے\n۲. نہیں، نیا بندہ"
        )
    if lang == "english":
        return (
            f"Is *{new_name}* the same person as *{existing_name}* already in your records?\n"
            "1. Yes, same person\n2. No, new person"
        )
    return (
        f"Kya *{new_name}* wohi *{existing_name}* hai jo pehle se record mein hai?\n"
        "1. Haan, wohi hai\n2. Nahi, naya banda"
    )


def ask_disambiguation(candidates: list[dict], lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        lines = ["کون سا؟ نمبر لکھیں:"]
    elif lang == "english":
        lines = ["Which one? Reply with the number:"]
    else:
        lines = ["Kaun sa? Number likhein:"]
    for i, c in enumerate(candidates, 1):
        bal = float(c.get("balance", 0))
        if bal > 0:
            bal_str = f" — PKR {int(bal):,} {'ادھار' if lang == 'urdu' else 'udhaar'}"
        elif bal < 0:
            bal_str = f" — PKR {int(abs(bal)):,} {'دینا ہے' if lang == 'urdu' else 'dena hai'}"
        else:
            bal_str = ""
        lines.append(f"{i}. {c['name']}{bal_str}")
    return "\n".join(lines)


def undo_success(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "✅ آخری اندراج ہٹا دیا۔"
    if lang == "english":
        return "✅ Last entry removed."
    return "✅ Last entry hata di."


def undo_nothing(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "کوئی اندراج نہیں ملا جسے ہٹا سکیں۔"
    if lang == "english":
        return "No entry found to remove."
    return "Koi entry nahi mili jisay hata sakein."


def need_clarification(q: str, lang: Lang = "roman_urdu") -> str:
    return q


def generic_error(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "معاف کریں، ابھی چھوٹی سی دقت ہے۔ تھوڑی دیر بعد کوشش کریں۔"
    if lang == "english":
        return "Sorry, something went wrong. Please try again in a moment."
    return "Maaf kijiye, abhi chhoti si dikkat hai. Thori dair baad try karein."


# ============================================================
# Voice reply toggle
# ============================================================

def voice_reply_enabled(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "🔊 وائس ریپلائی آن کر دی۔ جب آپ وائس نوٹ بھیجیں گے میں بھی آواز میں جواب دوں گا۔\nبند کرنے کے لیے: 'voice off' لکھیں۔"
    if lang == "english":
        return "🔊 Voice replies ON. I'll reply with audio when you send a voice note.\n\nTo turn off: reply 'voice off'."
    return "🔊 Voice reply on kar diya. Jab aap voice note bhejenge main bhi voice mein jawab dunga.\n\nBand karne ke liye: 'voice off' likhein."


def voice_reply_disabled(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "🔇 وائس ریپلائی بند کر دی۔ اب صرف ٹیکسٹ میں جواب ملے گا۔\nچالو کرنے کے لیے: 'voice on' لکھیں۔"
    if lang == "english":
        return "🔇 Voice replies OFF. I'll reply with text only.\n\nTo turn on: reply 'voice on'."
    return "🔇 Voice reply band kar diya. Ab sirf text mein jawab milega.\n\nChalu karne ke liye: 'voice on' likhein."


def voice_note_tip(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "💡 وائس نوٹ میں جواب چاہیے؟ *voice on* لکھیں۔ ٹیکسٹ چاہیے تو: *voice off*۔"
    if lang == "english":
        return "💡 Want voice replies? Reply *voice on*. To keep text only: *voice off*."
    return "💡 Voice note mein jawab chahiye? *voice on* likhein. Text chahiye to: *voice off* likhein."


# ============================================================
# Category breakdown (on-demand after daily summary)
# ============================================================

_CATEGORY_EMOJI = {
    "grains":        "🌾",
    "drinks":        "🥤",
    "snacks":        "🍪",
    "oil_ghee":      "🫙",
    "spices":        "🌶️",
    "soap_cleaning": "🧼",
    "tobacco":       "🚬",
    "dairy_eggs":    "🥚",
    "sweets":        "🍬",
    "other":         "📦",
}


def ask_category_breakdown(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "📊 کیا آپ category-wise breakdown چاہتے ہیں؟ (ہاں / نہیں)"
    if lang == "english":
        return "📊 Want a category-wise breakdown of today's sales? (yes / no)"
    return "📊 Category-wise breakdown chahiye? (haan / nahi)"


def format_category_breakdown(
    rows: list[dict],
    day: date,
    lang: Lang = "roman_urdu",
    supplier_payments: list[dict] | None = None,
) -> str:
    date_str = day.strftime("%d %b %Y")
    lines = [f"📊 Category Breakdown — {date_str}", ""]

    if not rows and not supplier_payments:
        if lang == "urdu":    lines.append("آج کوئی product-wise sale ریکارڈ نہیں ملی۔")
        elif lang == "english": lines.append("No product-level sales recorded today.")
        else: lines.append("Aaj koi product-wise sale record nahi mili.")
        return "\n".join(lines)

    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    grand_total = 0.0
    for cat, items in by_cat.items():
        emoji = _CATEGORY_EMOJI.get(cat, "📦")
        if lang == "urdu":
            cat_label = _CATEGORY_URDU.get(cat, cat)
        elif lang == "english":
            cat_label = cat.replace("_", " ").title()
        else:
            cat_label = _CATEGORY_ROMAN.get(cat, cat)
        lines.append(f"{emoji} *{cat_label}*")
        cat_total = 0.0
        for item in items:
            price = float(item["total_price"] or 0)
            cat_total += price
            name = item["product"].capitalize()
            qty  = float(item["total_qty"] or 0)
            unit = item["unit"] or ""
            qty_str = f" {int(qty)}{' '+unit if unit else ''}" if qty else ""
            lines.append(f"  • {name}{qty_str} — {_fmt_money(price)}")
        grand_total += cat_total

    # Supplier payments section
    if supplier_payments:
        lines.append("")
        if lang == "urdu":
            lines.append("💸 *سپلائر کو دیے گئے*")
        elif lang == "english":
            lines.append("💸 *Supplier Payments*")
        else:
            lines.append("💸 *Supplier ko Diye*")
        sup_total = 0.0
        for sp in supplier_payments:
            paid = float(sp["total_paid"] or 0)
            sup_total += paid
            lines.append(f"  • {sp['supplier_name']} — {_fmt_money(paid)}")

    lines.append("")
    if lang == "urdu":
        lines.append(f"*فروخت کل: {_fmt_money(grand_total)}*")
    elif lang == "english":
        lines.append(f"*Sales Total: {_fmt_money(grand_total)}*")
    else:
        lines.append(f"*Sales Kul: {_fmt_money(grand_total)}*")
    return "\n".join(lines)


# ============================================================
# Low-confidence transaction confirmation
# ============================================================

def tx_description(ttype: str, name: str | None, amount: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    if ttype == "sale_credit":
        if lang == "urdu":    return f"{name} کو {m} ادھار"
        if lang == "english": return f"Credit {m} to {name}"
        return f"{name} ko {m} udhaar"
    if ttype == "payment_received":
        if lang == "urdu":    return f"{name} سے {m} ملے"
        if lang == "english": return f"Received {m} from {name}"
        return f"{name} se {m} mile"
    if ttype == "sale_cash":
        if lang == "urdu":    return f"{m} نقد فروخت"
        if lang == "english": return f"Cash sale {m}"
        return f"{m} cash sale"
    if ttype == "payment_made":
        if lang == "urdu":    return f"{name} کو {m} دیے"
        if lang == "english": return f"Paid {m} to {name}"
        return f"{name} ko {m} diye"
    if ttype == "supplier_purchase":
        if lang == "urdu":    return f"{name} سے {m} کا مال ادھار"
        if lang == "english": return f"Stock {m} from {name} on credit"
        return f"{name} se {m} ka maal udhaar"
    return m


def ask_tx_confirm(description: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return f"میں نے سمجھا:\n*{description}*\n\nصحیح ہے؟ (ہاں / نہیں)"
    if lang == "english":
        return f"I understood:\n*{description}*\n\nIs this correct? (yes / no)"
    return f"Maine likha:\n*{description}*\n\nSahi hai? (haan / nahi)"


def ask_bulk_clear_confirm(count: int, total: float, lang: Lang = "roman_urdu") -> str:
    t = _fmt_money(total)
    if lang == "urdu":
        return (
            f"⚠️ آپ *{count}* کسٹمرز کا پورا ادھار ({t}) صاف کرنا چاہتے ہیں؟\n"
            "یہ ناقابلِ واپسی ہے — ہر کسٹمر کی payment received لکھی جائے گی۔\n\n"
            "پکا ہے؟ (ہاں / نہیں)"
        )
    if lang == "english":
        return (
            f"⚠️ You're about to clear ALL udhaar for *{count}* customers ({t}).\n"
            "A payment_received entry will be added for each. This cannot be undone easily.\n\n"
            "Are you sure? (yes / no)"
        )
    return (
        f"⚠️ Aap *{count}* customers ka poora udhaar ({t}) clear karna chahte hain?\n"
        "Har customer ki payment received likh di jayegi.\n\n"
        "Pakka hai? (haan / nahi)"
    )


def bulk_clear_done(count: int, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return f"✅ {count} کسٹمرز کا ادھار صاف کر دیا۔ سب کا حساب zero ہو گیا۔"
    if lang == "english":
        return f"✅ Cleared udhaar for {count} customers. All balances are now zero."
    return f"✅ {count} customers ka udhaar clear kar diya. Sab ka balance zero ho gaya."


def no_udhaar_to_clear(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "ابھی کسی کا ادھار باقی نہیں — سب صاف ہے۔ ✅"
    if lang == "english":
        return "No outstanding udhaar to clear — all balances are zero. ✅"
    return "Abhi kisi ka udhaar baqi nahi — sab clear hai. ✅"


def tx_one_liner(tx: dict, lang: Lang = "roman_urdu") -> str:
    """Short one-line summary of a transaction for correction menus."""
    ttype = tx.get("type", "")
    amount = float(tx.get("amount") or 0)
    name = tx.get("contact_name") or ""
    m = _fmt_money(amount)
    if ttype == "sale_credit":
        return f"{name} ko {m} udhaar" if lang != "english" else f"Credit to {name}: {m}"
    if ttype == "payment_received":
        return f"{name} se {m} mile" if lang != "english" else f"Received {m} from {name}"
    if ttype == "sale_cash":
        return f"Cash sale {m}" if lang != "english" else f"Cash sale {m}"
    if ttype == "payment_made":
        return f"{name} ko {m} diye" if lang != "english" else f"Paid {m} to {name}"
    if ttype == "supplier_purchase":
        return f"{name} se {m} ka maal" if lang != "english" else f"Stock {m} from {name}"
    return m


def ask_correction_action(summary: str, lang: Lang = "roman_urdu") -> str:
    """Single recent entry — ask delete or change."""
    if lang == "urdu":
        return (
            f"یہ اندراج ملا:\n*{summary}*\n\n"
            "کیا کرنا ہے؟\n۱. حذف کریں\n۲. تبدیل کریں (نئی تفصیل بھیجیں)"
        )
    if lang == "english":
        return (
            f"Found this entry:\n*{summary}*\n\n"
            "What do you want to do?\n1. Delete\n2. Change (send the new detail)"
        )
    return (
        f"Yeh entry mili:\n*{summary}*\n\n"
        "Kya karna hai?\n1. Delete karein\n2. Change karein (naye details bhejein)"
    )


def ask_correction_disambiguation(summaries: list[str], lang: Lang = "roman_urdu") -> str:
    """Multiple recent entries — list and ask which to fix. Takes pre-formatted summaries."""
    lines = []
    if lang == "urdu":
        header = f"پچھلی منٹ میں {len(summaries)} اندراج ہیں:"
        footer = "کس کو تبدیل کرنا ہے؟ نمبر بھیجیں۔"
    elif lang == "english":
        header = f"You have {len(summaries)} entries from the last minute:"
        footer = "Which one do you want to change? Reply with the number."
    else:
        header = f"Pichli minute mein {len(summaries)} entries hain:"
        footer = "Kis ko change karna hai? Number bhejein."
    lines.append(header)
    for i, s in enumerate(summaries, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def ask_correction_details(summary: str, lang: Lang = "roman_urdu") -> str:
    """User chose 'change' — ask for the new detail."""
    if lang == "urdu":
        return (
            f"ٹھیک ہے۔ *{summary}* میں کیا تبدیل کرنا ہے؟ "
            "مثلاً 'amount 600 تھا' یا 'احمد نہیں علی تھا' بھیجیں۔"
        )
    if lang == "english":
        return (
            f"OK. What do you want to change in *{summary}*? "
            "Send e.g. 'amount was 600' or 'it was Ali, not Ahmed'."
        )
    return (
        f"Theek hai. *{summary}* mein kya change karna hai? "
        "Naye details bhejein, jaise 'amount 600 tha' ya 'Ahmed nahi Ali tha'."
    )


def no_recent_correction(lang: Lang = "roman_urdu") -> str:
    """No transactions in the recent window."""
    if lang == "urdu":
        return (
            "پچھلی منٹ میں کوئی نیا اندراج نہیں ملا۔ "
            "تفصیل بتائیں — جیسے 'احمد والی غلط تھی' یا اصل اندراج کا حوالہ دیں۔"
        )
    if lang == "english":
        return (
            "No entry found in the last minute. "
            "Please be specific — e.g. 'Ahmed's was wrong' or describe the entry to fix."
        )
    return (
        "Pichli minute mein koi nayi entry nahi mili. "
        "Specific batayein, jaise 'Ahmed wali galat thi' ya entry ka reference dein."
    )


def correction_cancelled(lang: Lang = "roman_urdu") -> str:
    """Correction state cancelled (user changed their mind)."""
    if lang == "urdu":
        return "ٹھیک ہے، اندراج ویسے ہی رہنے دیا۔"
    if lang == "english":
        return "OK, leaving the entry as it is."
    return "Theek hai, entry waisi hi rehne di."


def correction_applied(description: str, lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return f"✅ ٹھیک کر دیا:\n{description}\n\nغلط ہے؟ 'undo' لکھیں۔"
    if lang == "english":
        return f"✅ Corrected:\n{description}\n\nWrong? Reply 'undo'."
    return f"✅ Theek kar diya:\n{description}\n\nGhalat hai? 'undo' likhein."


def correction_not_found(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "کوئی پچھلی اندراج نہیں ملی جسے ٹھیک کیا جا سکے۔"
    if lang == "english":
        return "No recent entry found to correct."
    return "Koi pichli entry nahi mili jisay theek kar sakein."


def tx_confirm_cancelled(lang: Lang = "roman_urdu") -> str:
    if lang == "urdu":
        return "ٹھیک ہے، یہ اندراج منسوخ کر دیا۔ دوبارہ واضح طور پر بھیجیں۔"
    if lang == "english":
        return "OK, entry cancelled. Please send it again more clearly."
    return "Theek hai, entry cancel kar di. Dobara clearly bhejein."


# ============================================================
# Language toggle
# ============================================================

def lang_switched(new_lang: Lang) -> str:
    if new_lang == "urdu":
        return (
            "✅ ٹھیک ہے! اب میں اردو میں جواب دوں گا۔\n\n"
            "تبدیل کرنے کے لیے:\n"
            "• رومن اردو: 'roman urdu' لکھیں\n"
            "• انگریزی: 'english' لکھیں"
        )
    if new_lang == "english":
        return (
            "✅ Done! I'll reply in English from now on.\n\n"
            "To change: type 'اردو' for Urdu script, or 'roman urdu'."
        )
    return (
        "✅ Theek hai! Ab Roman Urdu mein jawab dunga.\n\n"
        "Tabdeel karne ke liye:\n"
        "• Urdu script: 'اردو' likhein\n"
        "• English: 'english' likhein"
    )
