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

        piece = name.capitalize()
        if qty and unit:
            piece += f" {qty} {unit}"
        elif qty:
            piece += f" x{int(qty)}"
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
        return f"✅ {name} کو {m} ادھار دیا۔{item_line}\nکل ادھار {name} کا: {b}\n\nغلط ہے؟ 'undo' لکھیں۔"
    if lang == "english":
        return f"✅ Credit sale to {name}: {m}.{item_line}\nTotal owed by {name}: {b}\n\nWrong? Reply 'undo'."
    return f"✅ {name} ko {m} udhaar.{item_line}\nKul udhaar {name} ka: {b}\n\nGhalat hai? 'undo' likhein."


def confirm_sale_cash(amount: float, today_total: float, lang: Lang = "roman_urdu", items: list | None = None) -> str:
    m = _fmt_money(amount)
    t = _fmt_money(today_total)
    item_line = f"\n📦 {_fmt_items(items, lang)}" if items else ""
    if lang == "urdu":
        return f"✅ {m} نقد فروخت لکھ دی۔{item_line}\nآج کی نقد فروخت: {t}\n\nغلط ہے؟ 'undo' لکھیں۔"
    if lang == "english":
        return f"✅ Cash sale {m}.{item_line}\nToday's cash total: {t}\n\nWrong? Reply 'undo'."
    return f"✅ Cash sale {m} likh di.{item_line}\nAaj ki cash sales: {t}\n\nGhalat hai? 'undo' likhein."


def confirm_payment_received(name: str, amount: float, balance: float, lang: Lang = "roman_urdu") -> str:
    m = _fmt_money(amount)
    b = _fmt_money(balance)
    if lang == "urdu":
        tail = f"{name} کا باقی ادھار: {b}" if balance > 0 else f"{name} کا حساب صاف ہو گیا۔ ✅"
        return f"✅ {name} سے {m} ملے۔\n{tail}\n\nغلط ہے؟ 'undo' لکھیں۔"
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
    if lang == "urdu":
        tail = f"آپ کو {name} کو ابھی {b} اور دینے ہیں۔" if balance < 0 else f"{name} کا حساب صاف۔"
        return f"✅ {name} کو {m} دیے۔\n{tail}\n\nغلط ہے؟ 'undo' لکھیں۔"
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
    if lang == "urdu":
        return f"✅ {name} سے {m} کا مال ادھار لیا۔\n{name} کو دینا ہے: {b}\n\nغلط ہے؟ 'undo' لکھیں۔"
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
    net = cash_sales + payments_received - payments_made
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
        lines += ["", f"خالص آج: {'+' if net >= 0 else ''}{_fmt_money(net)}", "", "برکت ہو! 🌙"]
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
    lines += ["", f"{'Net today' if is_en else 'Net aaj'}: {'+' if net >= 0 else ''}{_fmt_money(net)}", ""]
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
