# MVP Feature Matrix

Status of every requirement from the original spec.

| Requirement | Status | Where |
|---|---|---|
| Accept text from shopkeeper | ✅ | `routers/webhook.py` — `msg_type == "text"` |
| Accept voice notes from shopkeeper | ✅ | `routers/webhook.py` — `msg_type in ("audio","voice")` + `services/stt.py` |
| Understand Urdu | ✅ | prompt + Whisper `language="ur"` |
| Understand Roman Urdu | ✅ | prompt examples in `prompts/extraction.py` |
| Understand English | ✅ | prompt + reply templates support English |
| Extract customer name | ✅ | `ExtractedTransaction.customer_name` |
| Extract transaction type | ✅ | `TransactionType` enum |
| Extract amount | ✅ | `ExtractedTransaction.amount` |
| Extract date/time | ⚠️ | We use `occurred_at = NOW()`; explicit dates in text are not yet parsed (rare need for MVP) |
| Store in DB with clear schema | ✅ | `db/schema.sql`, documented in `docs/DATABASE.md` |
| Query: "aaj ki total sales" | ✅ | `QueryType.DAILY_SALES` → `replies.reply_daily_sales` |
| Query: "kaun kaun udhaar par hai" | ✅ | `QueryType.WHO_OWES_ME` → `replies.reply_who_owes_me` |
| Query: "kis se lene hain / kis ko dene hain" | ✅ | `WHO_OWES_ME` + `WHO_I_OWE` |
| Generate daily summary message | ✅ | `services/daily_summary.build_daily_summary_text` |
| Store daily summary in DB | ✅ | `daily_summaries` table, upsert on `(shopkeeper_id, summary_date)` |
| Cost-effective | ✅ | ~$40/month for 100 shops. See `docs/ARCHITECTURE.md` §cost |
| Robust & simple for low-tech users | ✅ | WhatsApp-only, voice-first, 3-step onboarding, tiered confirmation |
| Quickly sellable MVP | ✅ | All the above in 1 month; see 30-day plan in original strategy doc |
| Error handling | ✅ | `orchestrator` returns friendly errors; webhook always returns 200 to Meta |
| Corrections / undo | ✅ | `undo` keyword + `CORRECTION` intent from LLM → `soft_delete_last_transaction` |
| Confirmations | ✅ | Every transaction reply ends with "Ghalat hai? 'undo' likhein." |
| Idempotency | ✅ | `was_wa_message_processed` keyed on `wa_message_id` |
| Audit trail | ✅ | `messages` table logs every inbound + outbound with full extraction JSON |
| Signature verification | ✅ | HMAC-SHA-256 on `X-Hub-Signature-256` |
| Daily summary cron | ✅ | APScheduler at 21:00 local time (prod only) |
| Deployable | ✅ | `Dockerfile` + `railway.json` |
| Tests | ✅ | 21 passing (`pytest tests/`) |
| Architecture docs | ✅ | `docs/ARCHITECTURE.md` |
| Setup docs | ✅ | `docs/SETUP.md`, `docs/WHATSAPP_SETUP.md`, `docs/DATABASE.md` |
| Persistent worklog | ✅ | `WORKLOG.md` |
| Next-steps doc | ✅ | `NEXT_STEPS.md` |

## Minor things not wired up

- Explicit dates in messages ("kal Ahmed ko 500 diye") — the LLM
  returns the intent correctly, but we always stamp `occurred_at = NOW()`.
  Easy fix later: add `occurred_at` to `ExtractedTransaction` and parse
  it in the orchestrator.
- Rate limiting per shopkeeper — simple Postgres count query, listed
  in `NEXT_STEPS.md` §C.
- Template-based daily summary send — requires Meta approval, listed
  in `NEXT_STEPS.md` §A8 and code stub in `services/whatsapp.py:send_template`.
- `image` message type is politely declined.
- Disambiguation between multiple close name matches (two "Ahmed"s) —
  currently we pick the highest-scoring match above threshold; will
  add interactive disambiguation in week 2 of real traffic.
