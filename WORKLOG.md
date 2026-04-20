# WORKLOG

Persistent record of work done on this project. Most recent first.
Read this when resuming in a new session to know exactly where you are.

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
