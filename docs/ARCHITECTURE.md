# Architecture

## One-paragraph summary

A FastAPI backend receives WhatsApp webhooks from the Meta Cloud API. Text
messages go straight to a Claude Haiku extraction call; voice notes are
transcribed via OpenAI Whisper first. The extractor returns a strict
JSON object describing the intent (transaction / query / correction /
onboarding / greeting) and any payload. The orchestrator then writes to
Postgres (Supabase) or queries it, formats a Roman-Urdu/Urdu/English
reply, and sends it back via the Cloud API. An APScheduler job runs at
21:00 local time to push a daily summary.

## Data flow

```
 WhatsApp
    │  inbound (text / voice)
    ▼
 ┌───────────────────────────┐
 │ POST /webhook/whatsapp    │  routers/webhook.py
 │  - verify X-Hub-Sig-256   │
 │  - dedupe by wa_message_id│
 │  - fetch media if voice   │
 └─────────────┬─────────────┘
               │ text or transcript
               ▼
 ┌───────────────────────────┐
 │ orchestrator.handle_msg   │  services/orchestrator.py
 │  - onboarding gate        │
 │  - 'undo' shortcut        │
 │  - LLM extract            │  services/llm.py
 │  - dispatch by intent     │
 └─────┬───────────┬─────────┘
       │           │
       │           ▼
       │   ┌───────────────┐
       │   │ replies.*()   │   services/replies.py
       │   │ (string tpl)  │
       │   └───────┬───────┘
       │           │
       ▼           ▼
 ┌───────────┐  ┌──────────────────────┐
 │ Postgres  │  │ POST Graph /messages │
 │ asyncpg   │  │ services/whatsapp.py │
 └───────────┘  └──────────────────────┘
```

## Layering

```
app/
├── main.py            # FastAPI app + lifespan (pool, scheduler)
├── config.py          # pydantic-settings
├── routers/
│   ├── webhook.py     # Meta WA webhook (GET verify + POST inbound)
│   └── ops.py         # /, /healthz, /admin/*
├── services/
│   ├── db.py          # asyncpg pool + all SQL
│   ├── contact_matching.py  # fuzzy name resolution (the hard bit)
│   ├── llm.py         # Claude Haiku primary, gpt-4o-mini fallback
│   ├── stt.py         # Whisper voice-note transcription
│   ├── whatsapp.py    # Cloud API: send_text, fetch_media, verify_signature
│   ├── replies.py     # Roman Urdu / Urdu / English message templates
│   ├── orchestrator.py# Business rules — the only place that coordinates the above
│   └── daily_summary.py
├── models/schemas.py  # Pydantic DTOs (Intent, TransactionType, ExtractionResult, ...)
├── prompts/extraction.py  # The Claude system prompt + few-shot examples
└── utils/
    ├── logging.py     # structlog (JSON in prod, pretty in dev)
    └── names.py       # Honorific-stripping + rapidfuzz best_match
```

**Rule:** `routers/` never touches the DB or external APIs directly.
They only call into `services/*` and return HTTP responses. `services/`
never know about HTTP. This keeps the webhook handler small and the
business logic testable.

## Key design choices

- **WhatsApp Cloud API (official), not unofficial wrappers.** Shopkeepers
  use this number for real business; a ban is catastrophic. Free for the
  first 1,000 conversations/month.
- **Claude Haiku 4.5 for extraction, gpt-4o-mini as fallback.** Haiku is
  cheap, fast, and strong on Urdu + Roman-Urdu code-mixing. The fallback
  path in `services/llm.py` only triggers if Anthropic throws.
- **OpenAI Whisper for STT.** Handles Urdu + code-mixing well at
  ~$0.006/min; WhatsApp voice notes are typically ~10–20s, so ~PKR 0.5
  each. Self-hosted Whisper is cheaper at scale but not needed for MVP.
- **Postgres via asyncpg (no ORM).** Queries are few and simple; SQL is
  easier to read than SQLAlchemy expressions here. We use a view
  (`v_contact_balances`) so balances are always derived, never stored —
  this prevents drift between the ledger and balance.
- **rapidfuzz for name matching, not embeddings.** Pakistani names +
  honorifics + spellings are a Levenshtein problem, not a semantic one.
  Embeddings would add cost and lag without helping.
- **Soft deletes via `is_deleted` flag.** When a shopkeeper undoes an
  entry, we keep the row so an auditor (or an upset user) can replay
  what happened. The `v_contact_balances` view filters deleted rows.
- **Idempotency by `wa_message_id`.** Meta retries webhooks; we check
  the `messages` table before reprocessing.
- **String templates for replies, not another LLM call.** Deterministic,
  faster, and free. Reply formatting is boring on purpose.

## What's intentionally NOT in the MVP

- Inventory tracking
- Invoices / receipts
- A web or mobile dashboard
- Multi-employee per shop
- Automated recurring billing
- Photo-of-receipt extraction

See `NEXT_STEPS.md` for the month-2 roadmap.

## Cost envelope (estimates, 100 active shops, ~10k messages/month)

| Item | Monthly |
|------|---------|
| Railway hosting | ~$5 |
| Supabase (free tier: 500MB) | $0 |
| Meta WhatsApp (under 1000 convos) | $0 |
| Whisper (~2,500 voice notes) | ~$15 |
| Claude Haiku (~100k messages) | ~$20 |
| **Total** | **~$40** |

Per-shop marginal cost at that volume is ~$0.40/month, against a Basic
plan of PKR 299 (~$1) — healthy gross margin.
