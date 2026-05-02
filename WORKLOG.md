# WORKLOG

Persistent record of work done on this project. Most recent first.
Read this when resuming in a new session to know exactly where you are.

---

## 2026-05-02 — Shop-name rename command

**Goal:** let shopkeepers fix the shop name after onboarding without
needing DB access.

**Bug reported by user:**
A new tester onboarded with a wrong shop name. When they tried to
correct it ("change shop name"), the bot didn't understand and fell
through to the generic "log a transaction" reply, because the LLM
extractor has no settings/admin intent.

**Done:**
- `app/routers/webhook.py` — new `_SHOP_RENAME_PHRASES` set covering
  English, Roman-Urdu, and Urdu-script triggers. Handler placed after
  voice/lang toggles and before the LLM call.
- When matched, sets `onboarding_state="awaiting_shop_name"` and
  asks for the new name. The next message is consumed by the
  existing onboarding handler in `orchestrator.py` (which already
  saves shop_name and sets state back to `done`).
- `app/services/replies.py` — new `ask_new_shop_name()` template in
  Urdu, Roman-Urdu, and English.
- Smoke-tested 13 phrase-matching cases — all pass. Generic strings
  like "shop name" or "ahmed ko 500 udhaar" do NOT match.

**Decisions:**
- Reused the onboarding flow rather than building a separate
  `bot_state="renaming"`. Simpler, fewer states, same UX.
- Phrase-list matching, not LLM intent. Latency stays low and the
  trigger is deterministic.

**NOT done:**
- Single-message rename ("change shop name to Ahmed Store") not
  supported — always two-step. Easy follow-up if shopkeepers ask.

---

## 2026-05-01 — Daily summary bottom line fixed

**Goal:** stop the daily summary from netting borrower repayments and
supplier payments into the headline number.

**Bug reported by user:**
The 10pm summary's "Net today" line was computing
`cash_sales + payments_received - payments_made`. So if a customer paid
back PKR 1,800 of an old debt and the shop paid PKR 5,000 to a
supplier, those moved the headline number — confusing for shopkeepers
who just want to know "how much did I sell today".

**Done:**
- `app/services/replies.py:format_daily_summary` — replaced `net`
  with `total_sales = cash_sales + credit_sales`. Borrower receipts
  and supplier payments still display as their own lines but no
  longer affect the total.
- Label: "Net today" / "Net aaj" / "خالص آج" → "Total sales" /
  "Kul Sales" / "کل فروخت".
- `tests/test_replies.py` — assertion updated from `9,300` to
  `15,700` (the new total = 12500 cash + 3200 credit).
- Manually exercised both Roman-Urdu and English variants — output
  verified clean.
- `CHANGELOG.md` bumped to 0.2.1.

**Decision (assumed, flagged to user):**
- "Sum of sales done" interpreted as cash_sales + credit_sales (both
  count as sales; credit is just unpaid). If user wanted cash-only,
  the line is one edit away.

**NOT done:**
- Not pushed to GitHub yet — user typically pushes manually. Local
  changes only.
- Railway redeploy needed for shopkeepers to see the new format
  tonight at 10pm PKT.

---

## 2026-04-30 — STT migrated from OpenAI Whisper to Groq

**Goal:** swap the speech-to-text provider to cut cost and latency.

**Done:**
- `app/services/stt.py` rewritten to use Groq's OpenAI-compatible
  audio endpoint with `whisper-large-v3`. Same `transcribe()`
  signature → no caller changes.
- `app/config.py` — added `groq_api_key`, `groq_whisper_model`,
  `groq_base_url`; runtime check now requires `GROQ_API_KEY` (was
  `OPENAI_API_KEY`).
- `.env` and `.env.example` updated. `OPENAI_API_KEY` retained for
  the extraction fallback (`gpt-4o-mini`); only the Whisper path moved.
- `CHANGELOG.md` bumped to `0.2.0`.

**NOT done this session (pending you):**
- Create Groq account at console.groq.com and paste key into
  `.env` → `GROQ_API_KEY=...`.
- Add `GROQ_API_KEY` to Railway Variables tab and redeploy.
- Smoke test: send a Roman-Urdu voice note via WhatsApp, watch
  Railway logs for `stt.ok provider=groq`.

**Decisions:**
- Kept `OPENAI_API_KEY` because `app/services/llm.py` still calls
  `gpt-4o-mini` when Anthropic extraction fails. Don't remove it.
- Stayed on the OpenAI Python SDK (just changed `base_url`) instead
  of adding a `groq` SDK dependency — fewer moving parts.

---

## 2026-04-21 — Session with Claude Code

- PHASE 2 complete: code pushed to GitHub at https://github.com/sumair95/hisabbot (branch: main). Pending: cloud accounts (Supabase, Anthropic, OpenAI, Meta, Railway).
- Supabase project created (region: Singapore). SUPABASE_DB_URL written to .env. Schema not yet applied.
- Anthropic API key created and written to .env (ANTHROPIC_API_KEY).
- OpenAI API key created and written to .env (OPENAI_API_KEY).
- Meta/WhatsApp credentials written to .env: WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_BUSINESS_ACCOUNT_ID, WHATSAPP_ACCESS_TOKEN, WHATSAPP_APP_SECRET, WHATSAPP_WEBHOOK_VERIFY_TOKEN=hisabbot-webhook-2026.
- Railway deployed successfully. App live at https://hisabbot-production-aa5a.up.railway.app — healthz returns ok:true, missing_config:[].
- Supabase schema applied. WhatsApp webhook registered. End-to-end test passed.
- Smart name matching: always ask confirmation on match (exact or fuzzy), 10-min session memory skips re-asking, digit normalisation (Ali1=Ali 1), 60-sec contact list cache, extra-token penalty prevents Ali Ahmed matching Ali silently.: bot asks "Kaun sa? 1. Ahmed Khan 2. Ahmed Bhai" when multiple contacts match. Stores pending_tx + bot_state in DB.
- Daily summary moved to 10 PM PKT (DAILY_SUMMARY_HOUR=22).
- DB migration applied: bot_state and pending_tx columns added to shopkeepers table.

---

## 2026-04-20 — Session 2 (continuation)

**Goal:** finish the MVP scaffold started in session 1 and verify it runs.

**Done:**
- `app/services/stt.py` — Whisper wrapper (OGG direct, language hint `ur`, `response_format="text"`).
- `app/services/whatsapp.py` — Cloud API client: `send_text`, `send_template`, `fetch_media` (2-step), `verify_signature` (HMAC SHA-256).
- `app/services/replies.py` — Roman-Urdu / Urdu / English reply templates for every confirmation, query response, daily summary, onboarding, undo, error.
- `app/services/orchestrator.py` — ties LLM → DB → replies. Handles onboarding gate, `undo` keyword shortcut, transaction dispatch with auto contact resolution, query dispatch with date ranges.
- `app/services/daily_summary.py` — `build_daily_summary_text` (reused by on-demand query) + `run_daily_summary_for_all` batch. Logs warning when send fails (likely 24h-window / template issue).
- `app/routers/webhook.py` — GET verify (echoes `hub.challenge`), POST handler with signature verification, dedup on `wa_message_id`, voice-note pathway.
- `app/routers/ops.py` — `/`, `/healthz` (lists missing env vars), `/admin/run-daily-summary`, `/admin/shop/{phone}/summary`. Admin endpoints gated by `X-Admin-Token` header (reusing `WHATSAPP_WEBHOOK_VERIFY_TOKEN`).
- `app/main.py` — FastAPI entrypoint, lifespan opens asyncpg pool + (in prod only) starts APScheduler cron for daily summary at `DAILY_SUMMARY_HOUR`.
- `Dockerfile` + `railway.json` — deployable container.
- `tests/test_names.py` — 8 tests for honorific stripping and fuzzy match.
- `tests/test_replies.py` — 8 tests for formatted reply strings.
- `tests/test_api.py` — 5 tests for FastAPI endpoints via TestClient.
- `pytest.ini`.
- Docs: `docs/ARCHITECTURE.md`, `docs/SETUP.md`, `docs/WHATSAPP_SETUP.md`, `docs/DATABASE.md`.
- Fixed a bug where `app/utils/logging.py` imported `.config` instead of `..config`.

**Verified locally:**
- `pytest -v` → 21/21 passing.
- `python -c "from app.main import app"` → imports cleanly.
- Routes registered: `/`, `/healthz`, `/admin/*`, `/webhook/whatsapp` (GET+POST), plus FastAPI's default `/docs`, `/redoc`, `/openapi.json`.

**Decisions made this session:**
- Reused the webhook verify token as the admin token (one less secret; it's already secret and not user-facing).
- Daily summary saves to DB even when send fails — shopkeeper gets it next time they open the chat.
- Scheduler only starts in production to avoid surprise sends during dev reloads.
- Voice notes that Whisper chokes on → we reply politely asking them to text, and still log the inbound attempt (so we can analyse failures later).
- Image messages → polite decline for MVP.
- Return 200 from the webhook even on internal errors so Meta doesn't retry-storm us; real errors surface through logs.

**NOT done this session (carried to NEXT_STEPS):**
- Can't push to GitHub from this sandbox — repo is init'd locally; you push.
- Can't write directly to `C:\Users\admin\AI Agent` from a Linux sandbox — delivered as a zip.
- Real Meta / Supabase / Anthropic / OpenAI credentials need to come from you.

---

## 2026-04-20 — Session 1

**Goal:** scaffold project structure, config, DB schema, and the hardest utility (fuzzy name matching).

**Done:**
- Project layout under `ai-agent/` with `app/{routers,services,models,utils,prompts}`, `db/`, `docs/`, `scripts/`, `tests/`.
- `README.md` — project overview, folder map, quick-start.
- `requirements.txt` — pinned versions.
- `.env.example` — every required var documented.
- `.gitignore` — covers `.env`, Python cruft, IDE files, caches.
- `db/schema.sql` — `shopkeepers`, `contacts`, `transactions`, `messages`, `daily_summaries`, `v_contact_balances` view, `pg_trgm` and `pgcrypto` extensions, soft-delete via `is_deleted`, `updated_at` trigger, idempotent.
- `app/config.py` — pydantic-settings; `assert_ready_for_runtime()` returns list of missing critical env vars.
- `app/utils/logging.py` — structlog (JSON in prod, pretty in dev).
- `app/utils/names.py` — honorific-stripping normalizer (bhai/sahib/apa/uncle/mian/chacha/ji/etc.) + rapidfuzz WRatio matching at 85/100 threshold + tiny Urdu→Roman fallback table.
- `app/models/schemas.py` — Pydantic DTOs: `Intent`, `TransactionType`, `QueryType`, `ItemLine`, `ExtractedTransaction`, `ExtractedQuery`, `ExtractionResult`, plus DB-facing models.
- `app/prompts/extraction.py` — Claude system prompt with strict JSON schema + 8 Urdu/Roman-Urdu/English few-shot examples + voice-transcript hint.
- `app/services/db.py` — asyncpg pool; shopkeeper ops, contact ops, transaction insert / soft-delete-last, message log with idempotency check, daily aggregates in shop's timezone, daily-summary upsert.
- `app/services/contact_matching.py` — exact → fuzzy → create pipeline for name resolution.
- `app/services/llm.py` — Claude Haiku primary, gpt-4o-mini fallback, lenient JSON extraction to handle stray ``` fences.

---

## Key decisions (standing)

- **WhatsApp Cloud API (official)** — never unofficial libraries. See `docs/WHATSAPP_SETUP.md`.
- **No ORM** — asyncpg + raw SQL. Queries are few; SQL reads better.
- **Balances derived, never stored** — `v_contact_balances` view is the source of truth.
- **Soft-delete, not hard-delete** — audit trail matters when a shopkeeper says "yeh ghalat hai".
- **Claude Haiku for extraction, gpt-4o-mini fallback** — best Urdu/Roman-Urdu handling at the cheap tier.
- **rapidfuzz over embeddings for name matching** — this is a spelling problem, not a semantic one.
- **Templates for 9 PM summary (post-MVP)** — plain text for now; works for shops that message during the day.
- **One orchestrator** — all the business rules live in `services/orchestrator.py`. Routers don't call LLM/DB directly.

## Cost posture

At 100 shops + ~10k msgs/month: ~$40/month infra. Per-shop marginal
~$0.40. Plan: PKR 299/month basic (~$1).
