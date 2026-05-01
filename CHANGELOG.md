# Changelog

## [0.2.1] — 2026-05-01 — Daily summary: total = sales only

### Fixed
- `app/services/replies.py:format_daily_summary` — bottom line was
  netting borrower repayments in and supplier payments out
  (`net = cash_sales + payments_received - payments_made`). This
  conflated cash flow with sales revenue.
- New formula: `total_sales = cash_sales + credit_sales`. Borrower
  repayments and supplier payments still appear as their own
  informational lines but are no longer rolled into the bottom line.
- Label changed: "Net today" / "Net aaj" / "خالص آج" →
  "Total sales" / "Kul Sales" / "کل فروخت".
- `tests/test_replies.py` updated to assert `15,700` (not `9,300`).

### Why
- Shopkeepers want to know "how much did I sell today" — that's a
  revenue question. Mixing in old-debt collections inflated the
  number; mixing in supplier payments deflated it. Both belong on
  the report, but not in the bottom line.

---

## [0.2.0] — 2026-04-30 — STT swap: OpenAI Whisper → Groq whisper-large-v3

### Changed
- `app/services/stt.py` — now calls Groq's OpenAI-compatible audio
  endpoint (`https://api.groq.com/openai/v1`) using `whisper-large-v3`.
  Same function signature; orchestrator + webhook unchanged.
- `app/config.py` — added `groq_api_key`, `groq_whisper_model`,
  `groq_base_url`. `assert_ready_for_runtime()` now requires
  `GROQ_API_KEY` instead of `OPENAI_API_KEY` for voice notes.
- `OPENAI_API_KEY` retained — still used by extraction fallback
  (`fallback_openai_model=gpt-4o-mini`) in `app/services/llm.py`.

### Why
- ~3× cheaper per minute (~$0.00185 vs $0.006).
- Faster inference (Groq LPU: 1–2s vs 5–10s for a 30s clip).
- whisper-large-v3 has stronger Urdu accuracy than whisper-1.

### Action required
- Add `GROQ_API_KEY` to Railway env vars and redeploy. Without it,
  `/healthz` will list it as missing and voice notes will fail.

---

## [0.1.0] — 2026-04-20 — Initial MVP scaffold

### Added
- FastAPI backend with WhatsApp Cloud API webhook (`/webhook/whatsapp`)
- Postgres schema (Supabase) with shopkeepers / contacts / transactions
  / messages / daily_summaries, plus `v_contact_balances` view
- Voice-note transcription via OpenAI Whisper (Urdu language hint)
- LLM extraction via Anthropic Claude Haiku, fallback to OpenAI gpt-4o-mini
- Roman-Urdu / Urdu / English reply templates
- Honorific-stripping name normaliser + rapidfuzz fuzzy matching
- Onboarding flow (welcome → shop name → ready)
- `undo` keyword + `CORRECTION` intent with soft-delete
- Daily summary generator with APScheduler cron at 21:00 local time
- HMAC-SHA-256 webhook signature verification
- Idempotent webhook processing via `wa_message_id`
- Admin endpoints gated by `X-Admin-Token`
- Dockerfile + railway.json for deployment
- 21 unit + API tests (all passing)
- Docs: architecture, setup, WhatsApp setup, database, MVP features
- Dev scripts: extraction tester, webhook simulator

### Known limitations (tracked in NEXT_STEPS.md)
- Explicit dates in messages ("kal") not parsed; always uses `now()`
- No rate limiting yet
- Daily summary uses plain text (needs Meta template approval for
  users outside 24h window)
- Two-contact disambiguation picks highest fuzzy score; interactive
  prompt not yet implemented
