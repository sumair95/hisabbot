# Changelog

## [0.3.0] — 2026-05-04 — Per-shop Whisper vocabulary biasing (self-improving STT)

### Added
- `app/services/vocabulary.py` — builds a per-shopkeeper vocabulary
  string and feeds it to Whisper as the `prompt` parameter. Whisper
  uses this to bias transcription toward the shop's customers,
  suppliers, and products. Result: proper nouns transcribe stably
  ("Akbar Trader" stays "Akbar Trader" instead of becoming "Akbar
  Tarader" / "Akbar Trade-er" across calls).
- `db.get_recent_product_names(sk_id, limit)` — returns most-used
  product names from the `items` JSONB across past transactions.
- In-memory cache with 5-min TTL keyed by shopkeeper_id; ~7μs lookup
  on hit. Auto-invalidated on `create_contact()` so a brand-new
  customer name appears in the very next voice transcript.
- `stt.transcribe()` accepts an optional `prompt` parameter.

### Why
- Voice notes are the bot's main input channel for these shopkeepers,
  and Whisper's accuracy on Pakistani names was a noticeable weak
  spot. Whisper's `prompt` parameter is the right tool — it's free
  (no extra API calls), takes ~77 tokens for a shop with 40 customers
  + 15 products (well under the 224-token budget), and the bot
  literally improves itself as the shopkeeper logs more transactions.

### Self-improving loop
1. Shopkeeper sends voice → Whisper transcribes (with biased vocab)
2. LLM extracts a customer name → contact_matcher resolves or creates
3. New contact insert invalidates vocab cache
4. Next voice from this shop uses an updated vocabulary

---

## [0.2.4] — 2026-05-02 — Shop-rename via LLM intent (SETTINGS_CHANGE)

### Changed
- Replaced the keyword-matcher approach (0.2.2 / 0.2.3) with a proper
  LLM intent: `Intent.SETTINGS_CHANGE`. The extraction LLM now
  classifies "change shop name" phrasings directly and extracts the
  new name (if given) in a single pass.
- Added `ExtractedSettingsChange` schema with `setting_type` and
  `new_value` fields.
- Updated `app/prompts/extraction.py` with the new intent description,
  output schema, dedicated rules block, and four few-shot examples
  (19–22) covering single-message rename, two-step flag-only rename,
  Urdu script, and English variants.
- New orchestrator handler `_handle_settings_change` saves the shop
  name immediately when the LLM returned a non-null `new_value`,
  otherwise sets `onboarding_state="awaiting_shop_name"` so the next
  message is captured by the existing onboarding handler.
- Removed `_is_shop_rename_intent` and the keyword-based webhook
  branch — LLM is now the single source of truth.

### Why
- Voice notes go through Whisper with `language="ur"`, returning
  Urdu script. The keyword approach was missing common transcription
  variants ("شاپ کا نیم چینج کرو", filler words, mixed code) and
  also couldn't parse a name out of "shop ka naam X rakh do" in a
  single message. LLM handles both naturally.

---

## [0.2.3] — 2026-05-02 — Shop-rename: keyword-combination matcher

### Fixed
- Rename trigger from voice notes was missing because Whisper
  (`language="ur"`) returns Urdu script, and the original phrase
  list only contained two specific Urdu strings — most natural
  Urdu phrasings ("شاپ کا نام بدلو", "دکان کا نام غلط ہے") failed
  to match. The bot then fell through to the LLM, which asked its
  own clarification question, leading users to think the rename
  flow was broken.
- Replaced the fixed phrase list in `app/routers/webhook.py` with
  `_is_shop_rename_intent()` — keyword-combination matching. Needs
  a "shop" word (shop/dukaan/store/شاپ/دکان/اسٹور) AND a "change"
  word (change/rename/galat/wrong/tabdeel/بدل/غلط/...) AND, except
  for the explicit "rename" verb, a "name" word (name/naam/نام).
- Tested against 26 cases (Roman + Urdu-script transcripts +
  false-positive guards). "Ahmed Store" by itself does NOT trigger
  rename, so the second message correctly flows into the
  awaiting_shop_name handler.

---

## [0.2.2] — 2026-05-02 — Shop-name rename command

### Added
- New keyword command: shopkeepers can now rename their shop after
  onboarding by sending phrases like "change shop name",
  "shop ka naam change", "rename shop", "dukaan ka naam galat",
  "shop name wrong", "دکان کا نام تبدیل" etc.
- Bot replies asking for the new name; the next message is saved as
  the new `shop_name` (reuses the existing onboarding handler by
  flipping `onboarding_state` back to `awaiting_shop_name`).
- New reply template `replies.ask_new_shop_name()` in 3 languages.

### Why
- Tester onboarded with a wrong shop name had no way to fix it from
  WhatsApp — the LLM didn't know about settings changes and the bot
  fell through to the generic "log a transaction or ask sales" reply.

---

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
