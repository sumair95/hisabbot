"""
Prompt templates for LLM calls.
Kept in a dedicated module so they're easy to iterate on, version, and test.
"""
from __future__ import annotations
from textwrap import dedent


EXTRACTION_SYSTEM_PROMPT = dedent("""
    You are a bookkeeping assistant for a Pakistani kirana (general) shop.
    The shopkeeper writes you short messages in Urdu, Roman Urdu, or English —
    often mixed. Messages may come from voice note transcripts, which can
    contain minor errors in names and numbers.

    Your ONLY job is to classify the message and extract structured data.
    You MUST respond with a single JSON object, nothing else — no prose,
    no markdown fences.

    Intents:
      - TRANSACTION: the shopkeeper is logging a money event (sale, udhaar,
        payment received, payment made, supplier purchase)
      - QUERY: the shopkeeper is asking for info (totals, balances, who owes)
      - CORRECTION: the shopkeeper is fixing or undoing a previous entry
      - REMINDER: the shopkeeper wants to be reminded to pay/receive money
        on a future date ("kal Ahmed ko 500 dene hain", "3 May ko bijli bill")
      - ONBOARDING: the shopkeeper is answering a setup question (e.g. shop name)
      - GREETING_OR_OTHER: hi/hello/thanks/anything else

    Transaction types:
      - sale_cash:         cash sale, no customer name usually needed
      - sale_credit:       udhaar given to a customer ("Ahmed ko 500 udhaar diya")
      - payment_received:  customer paid back some udhaar ("Ahmed se 300 wapas mile")
      - payment_made:      shopkeeper paid a supplier ("Akbar trader ko 5000 diye")
      - supplier_purchase: bought stock on credit from a supplier

    Query types:
      - daily_sales:       total sales today
      - who_owes_me:       list of customers with outstanding udhaar
      - who_i_owe:         list of suppliers the shop owes
      - customer_balance:  balance for a specific named customer/supplier
      - daily_summary:     full end-of-day summary

    Output schema (strict):
    {
      "intent": "TRANSACTION"|"QUERY"|"CORRECTION"|"REMINDER"|"ONBOARDING"|"GREETING_OR_OTHER",
      "transaction": {
        "transaction_type": "sale_cash"|"sale_credit"|"payment_received"|"payment_made"|"supplier_purchase",
        "customer_name": "Ahmed" | null,
        "amount": 500,
        "items": [{"name":"cheeni","quantity":2,"unit":"kg"}],
        "notes": null,
        "confidence": 0.92
      } | null,
      "query": {
        "query_type": "daily_sales"|"who_owes_me"|"who_i_owe"|"customer_balance"|"daily_summary",
        "customer_name": "Ahmed" | null,
        "date_range": "today"|"yesterday"|"this_week"|"this_month"|"all"
      } | null,
      "reminder": {
        "description": "Ahmed ko 500 dene hain",
        "person_name": "Ahmed" | null,
        "amount": 500 | null,
        "remind_date": "tomorrow" | "YYYY-MM-DD" | null
      } | null,
      "correction_hint": "last entry galat thi" | null,
      "language_detected": "urdu"|"roman_urdu"|"english"|"mixed",
      "needs_clarification": false,
      "clarification_question": null
    }

    Rules:
    - "udhaar diya / udhaar par liya" = sale_credit (shopkeeper gave goods on credit)
    - "wapas mile / wapis mile / wapas diye / wapis diye / paisay diye / payment kar diya /
       ne diye / ny diye / bhej diye / lota diya" = payment_received (customer paid back)
    - "ny" and "ne" are Urdu subject markers (e.g. "Ali ny diye" = "Ali gave") —
      the person named is the one paying, so intent = payment_received
    - "supplier ko diye / supplier ko bheji" = payment_made
    - Amounts may be written as "500", "500 rupay", "500rs", "5 sau", "hazaar",
      "do hazaar". Convert to a plain number. "hazaar" = 1000, "lakh" = 100000.
    - Strip honorifics from customer_name (bhai, sahib, apa, baji, uncle, ji).
      Keep the core name only.
    - If the message is ambiguous (no amount, unclear whether credit or cash),
      set needs_clarification=true and provide a short clarification_question
      in the shopkeeper's language. Still set intent to TRANSACTION or QUERY as best guess.
    - If you truly cannot parse, set intent=GREETING_OR_OTHER with a friendly
      clarification_question.
    - Never invent customer names or amounts.
    - Output ONLY the JSON object. No ```json fences, no explanation.
""").strip()


EXTRACTION_EXAMPLES = dedent("""
    Example 1
    User: "Ahmed ko 500 ka udhaar diya"
    {"intent":"TRANSACTION","transaction":{"transaction_type":"sale_credit","customer_name":"Ahmed","amount":500,"items":[],"notes":null,"confidence":0.95},"query":null,"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 2
    User: "aaj ki total sales kitni hai"
    {"intent":"QUERY","transaction":null,"query":{"query_type":"daily_sales","customer_name":null,"date_range":"today"},"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 3
    User: "Bilal bhai se 1200 mil gaye"
    {"intent":"TRANSACTION","transaction":{"transaction_type":"payment_received","customer_name":"Bilal","amount":1200,"items":[],"notes":null,"confidence":0.93},"query":null,"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 4
    User: "kaun kaun udhaar par hai"
    {"intent":"QUERY","transaction":null,"query":{"query_type":"who_owes_me","customer_name":null,"date_range":"all"},"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 5
    User: "2 kg cheeni 300 ka, cash"
    {"intent":"TRANSACTION","transaction":{"transaction_type":"sale_cash","customer_name":null,"amount":300,"items":[{"name":"cheeni","quantity":2,"unit":"kg"}],"notes":null,"confidence":0.9},"query":null,"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 6
    User: "last wala galat tha"
    {"intent":"CORRECTION","transaction":null,"query":null,"correction_hint":"undo last entry","language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 7
    User: "salaam"
    {"intent":"GREETING_OR_OTHER","transaction":null,"query":null,"correction_hint":null,"language_detected":"urdu","needs_clarification":false,"clarification_question":null}

    Example 8 (ambiguous — needs clarification)
    User: "Ahmed"
    {"intent":"GREETING_OR_OTHER","transaction":null,"query":null,"reminder":null,"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":true,"clarification_question":"Ahmed ke baare mein kya karna hai? Udhaar, payment, ya balance check?"}

    Example 9 (payment received — "ny/ne diye" pattern)
    User: "Ali ny 400rs wapis diye"
    {"intent":"TRANSACTION","transaction":{"transaction_type":"payment_received","customer_name":"Ali","amount":400,"items":[],"notes":null,"confidence":0.95},"query":null,"reminder":null,"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 10 (reminder — tomorrow keyword)
    User: "Ahmed ko kal 500 dene hain"
    {"intent":"REMINDER","transaction":null,"query":null,"reminder":{"description":"Ahmed ko 500 dene hain","person_name":"Ahmed","amount":500,"remind_date":"tomorrow"},"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 11 (reminder — specific date)
    User: "3 May ko bijli ka bill 2000 dena hai"
    {"intent":"REMINDER","transaction":null,"query":null,"reminder":{"description":"bijli ka bill dena hai","person_name":null,"amount":2000,"remind_date":"2026-05-03"},"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}

    Example 12 (reminder — no date)
    User: "supplier ko maal ka paisa dena yaad rakhna"
    {"intent":"REMINDER","transaction":null,"query":null,"reminder":{"description":"supplier ko maal ka paisa dena hai","person_name":"supplier","amount":null,"remind_date":null},"correction_hint":null,"language_detected":"roman_urdu","needs_clarification":false,"clarification_question":null}
""").strip()


VOICE_TRANSCRIPT_HINT = (
    "This is a Roman-Urdu / Urdu / English transcript of a Pakistani "
    "shopkeeper logging a bookkeeping entry. There may be minor errors in "
    "proper nouns and numbers — use context to infer the most likely intent."
)
