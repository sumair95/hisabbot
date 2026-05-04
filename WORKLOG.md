# WORKLOG

Persistent record of work done on this project. Most recent first.
Read this when resuming in a new session to know exactly where you are.

---

## 2026-05-04 — Self-improving STT via Whisper vocabulary biasing

**Goal:** make the bot transcribe more accurately as each shopkeeper
logs more transactions. User wanted "the bot to improve over time".

**Strategy chosen:**
Whisper's `prompt` parameter accepts ~224 tokens of vocabulary that
biases transcription. Feed the shopkeeper's known customer/supplier
names + recent product names + a static seed of common Roman-Urdu
bookkeeping vocabulary. Whisper then produces stable, consistent
transcripts for proper nouns it would otherwise misspell.

This is a true compounding loop:
- More transactions → richer vocabulary → better transcription →
  better extraction → fewer corrections → smoother experience.

**Done:**
- New `app/services/vocabulary.py`:
  - `get_shop_vocabulary(sk_id)` builds the prompt string
  - 5-min in-memory TTL cache (~7μs hit time)
  - `invalidate(sk_id)` for explicit drop
  - Caps: 40 contacts + 15 products + static seed (~77 tokens)
- New `db.get_recent_product_names(sk_id, limit=15)` — pulls
  most-frequent product names from `items` JSONB.
- `stt.transcribe()` accepts optional `prompt` parameter, passed to
  Whisper API. Logs `prompt_chars` so usage is observable.
- `webhook.py` voice path: fetches vocabulary right before STT,
  passes to `transcribe()`. Cached so cost is negligible.
- `db.create_contact()` invalidates the vocab cache so brand-new
  customer names show up in the very next voice without waiting for
  the 5-min TTL.

**Tested locally:**
- Vocabulary builder produces ~309-char (~77-token) string with
  realistic shop data — within Whisper's 224-token budget with
  plenty of headroom.
- Cache hit ~7μs — essentially free on subsequent calls.
- All file syntax validated.

**Future improvements (not done — flagged in NEXT_STEPS):**
- Dynamic LLM few-shot: track last 5 successful (message, extraction)
  pairs per shop and inject as additional examples in the LLM prompt.
  Adapts the LLM to each shopkeeper's phrasing style.
- Correction tracking: when the user does fix_customer, log
  (heard_name, correct_name) and use as an explicit pronunciation
  alias dictionary. Would also feed into the Whisper prompt.
- Per-shop confidence calibration: track when low-confidence
  extractions get confirmed vs cancelled, adjust the threshold per
  shop.

**Decisions:**
- Whisper biasing first because it's the highest-leverage and
  simplest intervention — one parameter, immediate effect.
- In-memory cache (not Redis) because Railway runs a single instance
  for now. Will need to revisit if scaled out.

---

## 2026-05-02 — Shop-rename moved to LLM intent (final)

**Goal:** make the shop rename actually work, after two failed
keyword-matcher iterations.

**User report:**
After 0.2.3 ("dukaan k naam change karke ... rakh do" voice flow),
still didn't work. User wanted both two-step (ask, then provide
name) AND single-message ("change shop name to X") flows.

**Root cause (real one this time):**
Keyword matching was the wrong tool. Whisper voice transcripts
include arbitrary filler words, code-mixed Urdu/Roman, English
words written in Urdu script ("نیم", "چینج"), etc. Trying to keep
a keyword list complete is whack-a-mole. The LLM extractor sees
every message anyway — it's the natural place to classify intent
and extract the new name from natural phrasing.

**Done:**
- `app/models/schemas.py` — added `Intent.SETTINGS_CHANGE` and
  `ExtractedSettingsChange` (`setting_type`, `new_value`).
- `app/prompts/extraction.py` — added intent description, output
  schema field, dedicated rules block (filler-word stripping
  guidance, false-positive guard against contact-name corrections),
  and four few-shot examples (19–22) covering Roman/Urdu/English
  and single/two-step variants.
- `app/services/orchestrator.py` — new `_handle_settings_change`
  handler. Single-message → save immediately + send onboarding_done
  reply. Flag-only → set state to `awaiting_shop_name` and ask via
  `replies.ask_new_shop_name` (existing onboarding handler picks up
  the next message).
- `app/routers/webhook.py` — deleted `_is_shop_rename_intent` and
  the keyword branch. LLM is single source of truth now.
- Schema parsing verified locally for SETTINGS_CHANGE outputs in
  Roman, Urdu script, and the existing TRANSACTION case (no
  regression).

**Decisions:**
- LLM handles natural phrasings — no need to enumerate variants.
- Filler-word stripping ("rakh do", "kar do", "to") delegated to
  the LLM via prompt instructions, not done in Python.
- Dropped keyword fallback. Keeps logic in one place; LLM failures
  already return generic_error which is the same UX as a missed
  keyword anyway.

**NOT done:**
- Other settings (language, voice toggle) still use keyword commands
  in webhook.py. They work fine; not worth migrating.
- LLM may occasionally extract the wrong name (e.g. if user says
  "shop ka naam Ali ka tha woh galat hai"). If this becomes a
  pattern, add more confidence-gated examples.

---

## 2026-05-02 — Shop-rename keyword matcher (voice-transcript fix)

**Goal:** make the shop-rename trigger from earlier today actually fire
on voice notes.

**Bug reported by user (same day as feature shipped):**
User sent a voice "shop ka naam galat" — bot asked for the new name,
which looked correct. They sent the new name as a second voice — bot
replied "Aap koi transaction record karna chahty hain?" (LLM clarification).

Root cause: STT runs Whisper with `language="ur"`, so all voice gets
transcribed to **Urdu script**. The fixed phrase list from 0.2.2 only
had two specific Urdu strings ("دکان کا نام تبدیل", "دکان کا نام غلط")
and missed common variants like "شاپ کا نام بدلو", "دکان کا نام غلط ہے",
"شاپ کا نام تبدیل کرو". So the rename trigger never fired on voice; the
LLM was the one asking for the new name. The second voice (the actual
new name) also went to the LLM since DB state was still `done`.

**Done:**
- Replaced `_SHOP_RENAME_PHRASES` set with
  `_is_shop_rename_intent(text)` — keyword-combination matcher.
  Match requires: shop-word ∈ {shop, dukaan, dukan, store, شاپ, دکان,
  اسٹور} + change-word ∈ {change, rename, galat, wrong, tabdeel, بدل,
  غلط, …} + name-word ∈ {name, naam, نام}. The "rename" verb covers
  English short-form on its own.
- Tested 26 transcripts (Roman + Urdu-script + false-positive guards).
  Critical: bare "Ahmed Store" (the user's reply with the new name)
  does NOT match — so the second message correctly flows into the
  `awaiting_shop_name` handler in orchestrator.
- CHANGELOG bumped to 0.2.3.

**Decision:**
- Stayed with deterministic keyword matching rather than adding a
  settings-intent to the LLM. Keeps latency / cost low and the
  trigger is debuggable without LLM logs.

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
