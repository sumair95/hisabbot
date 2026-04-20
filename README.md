# Kirana Bookkeeper — WhatsApp AI Bookkeeping Agent

A WhatsApp-based AI agent for Pakistani kirana (general) shops. Shopkeepers
send text or voice notes in Urdu, Roman Urdu, or English; the agent logs
transactions (sales, udhaar/credit, payments), answers queries about balances
and sales, and produces a daily summary.

## What's in this repo

```
ai-agent/
├── app/                    # FastAPI backend
│   ├── main.py             # App entry point & webhook
│   ├── config.py           # Settings via pydantic-settings
│   ├── routers/            # HTTP route handlers
│   ├── services/           # Integrations: WhatsApp, Whisper, LLM, DB
│   ├── models/             # Pydantic schemas (DTOs)
│   ├── prompts/            # LLM prompt templates
│   └── utils/              # Helpers (logging, name matching, etc.)
├── db/
│   └── schema.sql          # Supabase/Postgres schema
├── scripts/                # Utility scripts (local testing, cron, etc.)
├── tests/                  # pytest tests
├── docs/                   # Architecture, setup, API references
├── WORKLOG.md              # Running log of what's been done
├── NEXT_STEPS.md           # What you need to do next (manual steps)
├── ARCHITECTURE.md         # System design
├── .env.example            # Template for required env vars
├── requirements.txt        # Python dependencies
├── Dockerfile              # For Railway / Fly.io / any container host
└── railway.json            # Railway deployment config
```

## Quick start (local development)

```bash
# 1. Create a Python 3.11+ virtual env
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template and fill in your keys
cp .env.example .env
# Then edit .env with real values (see docs/SETUP.md)

# 4. Apply DB schema to your Supabase Postgres
# (either via the Supabase SQL editor, or using psql)
psql "$SUPABASE_DB_URL" -f db/schema.sql

# 5. Run the API locally
uvicorn app.main:app --reload --port 8000

# 6. Expose to WhatsApp via ngrok (for webhook testing)
ngrok http 8000
# Put the HTTPS URL into your Meta app's WhatsApp webhook config
```

See `docs/SETUP.md` for the full setup walkthrough, including Meta/WhatsApp
Business verification and Supabase project creation.

## Status

- MVP scaffold: ✅ complete
- WhatsApp webhook: ✅ implemented (needs your Meta credentials to go live)
- Voice transcription (Whisper): ✅ implemented
- Transaction extraction (Claude): ✅ implemented
- Queries & daily summary: ✅ implemented
- Corrections / undo: ✅ implemented
- Deployment-ready: ✅ Dockerfile + Railway config

See `WORKLOG.md` and `NEXT_STEPS.md` for the latest state.
