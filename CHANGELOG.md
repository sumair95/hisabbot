# Changelog

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
