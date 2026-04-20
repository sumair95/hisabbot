# Setup Guide

Goal: a working WhatsApp → AI → DB loop on your own phone within about
half a day of real effort, once accounts are created.

---

## 0. Prerequisites

- Python 3.11 or newer
- `git`
- A credit card or debit card for Meta / OpenAI / Anthropic billing
- A **new** SIM card for the WhatsApp Business number (do not use your
  personal WhatsApp number)

---

## 1. Create the cloud accounts

Do all of these before writing any code. Verification steps have
waiting times.

### 1a. Meta / WhatsApp Cloud API

1. Go to https://business.facebook.com and create a Meta Business
   account if you don't have one.
2. At https://developers.facebook.com → My Apps → Create App → type
   "Business" → app name "Kirana Bookkeeper" (or similar).
3. In the app, add the **WhatsApp** product.
4. A **test phone number** is provisioned automatically. It can send
   messages to up to 5 whitelisted testers. Use this for development.
5. From WhatsApp → API Setup, note down:
   - `Phone number ID` → `WHATSAPP_PHONE_NUMBER_ID`
   - `WhatsApp Business Account ID` → `WHATSAPP_BUSINESS_ACCOUNT_ID`
   - A **temporary access token** (valid 24h) → `WHATSAPP_ACCESS_TOKEN`
     (see step 1b to get a permanent one)
6. Under App Settings → Basic, copy **App Secret** →
   `WHATSAPP_APP_SECRET`.
7. To go live with a real number, start business verification now —
   it can take 1–2 weeks and is required before you can onboard real
   shopkeepers.

### 1b. Permanent access token (for production)

Generate a System User token so you don't have to rotate every 24h:
1. Meta Business Settings → Users → System Users → Add.
2. Give it Admin role, assign the WhatsApp app.
3. Click "Generate new token", select `whatsapp_business_messaging`
   and `whatsapp_business_management` scopes, set expiration to
   "Never".
4. Copy the token into `WHATSAPP_ACCESS_TOKEN`.

### 1c. Supabase

1. https://supabase.com → New project. Region: `ap-south-1` (Mumbai)
   for lowest latency from Pakistan.
2. Save the DB password.
3. Project Settings → Database → Connection string → **URI (Session
   mode, port 5432)**. Copy it into `SUPABASE_DB_URL`.
4. *Do not* use the pooler URL (port 6543) — asyncpg needs session
   mode.

### 1d. Anthropic

1. https://console.anthropic.com → sign up → add a payment method.
2. API Keys → Create Key. Copy to `ANTHROPIC_API_KEY`.

### 1e. OpenAI (for Whisper)

1. https://platform.openai.com → sign up → add a payment method.
2. Set a low monthly cap ($10) while developing.
3. Create an API key. Copy to `OPENAI_API_KEY`.

---

## 2. Clone and configure

```bash
git clone <your-repo-url> "AI Agent"
cd "AI Agent"

# Create virtualenv
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (cmd):
.\.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Fill in .env
cp .env.example .env    # Windows: copy .env.example .env
# Then edit .env with the values you gathered in step 1.
```

Minimum values you must set:
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (pick any random string)
- `SUPABASE_DB_URL`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

---

## 3. Apply the database schema

Option A — Supabase SQL Editor (easiest):
1. Open your Supabase project → SQL Editor → New query.
2. Paste the contents of `db/schema.sql` → Run.

Option B — psql:
```bash
psql "$SUPABASE_DB_URL" -f db/schema.sql
```

Verify:
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```
You should see `shopkeepers, contacts, transactions, messages, daily_summaries`.

---

## 4. Run the app locally

```bash
uvicorn app.main:app --reload --port 8000
```

Sanity checks:
```bash
curl http://localhost:8000/
curl http://localhost:8000/healthz
```
`healthz` will tell you exactly which env vars are still missing.

---

## 5. Expose your local server to the internet (for webhook testing)

Meta needs a public HTTPS URL to deliver webhooks to. Three options:

### Option A — ngrok (simplest for dev)
```bash
# download ngrok, then:
ngrok http 8000
```
Copy the https `https://xxxx.ngrok.app` URL.

### Option B — Cloudflare Tunnel
Free, more stable URLs than ngrok.

### Option C — Deploy to Railway right away
See step 7.

---

## 6. Register the webhook with Meta

1. Meta app → WhatsApp → Configuration → Webhook → Edit.
2. Callback URL: `https://<your-public-url>/webhook/whatsapp`
3. Verify token: the same random string you put in
   `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
4. Click Verify and Save — Meta will GET your `/webhook/whatsapp` and
   expect the challenge echoed back. If it fails, your `.env` value and
   Meta's value don't match.
5. Subscribe the webhook to: **messages**.

Send a message from your personal WhatsApp (which you added as a test
recipient in step 1a) to the test number. Watch your uvicorn logs —
you should see `webhook.sent` and your phone should receive a reply.

---

## 7. Deploy to Railway (production-ish)

```bash
# install railway cli: https://docs.railway.app/guides/cli
railway login
railway init    # inside the repo
railway up      # builds via the Dockerfile
```

Then in the Railway dashboard:
1. Add all `.env` variables under the Variables tab.
2. Generate a domain (Settings → Networking → Generate Domain).
3. Update Meta's webhook URL to point to the new domain.
4. Set `APP_ENV=production` and the APScheduler daily job will
   auto-start at 21:00 Asia/Karachi.

---

## 8. Daily summary template (for proactive 9 PM send)

If a shopkeeper hasn't messaged in the last 24h, the 9 PM summary as a
plain text message will be rejected by Meta. You need a pre-approved
template.

1. Meta Business → WhatsApp Manager → Message Templates → Create.
2. Name: `daily_summary`. Category: UTILITY. Language: English (or Urdu
   if you want — English is faster to approve).
3. Body (with variables):
   ```
   🧾 Daily Summary for {{1}}

   Cash sales: PKR {{2}}
   Credit sales: PKR {{3}}
   Payments received: PKR {{4}}
   Paid to suppliers: PKR {{5}}

   Net today: PKR {{6}}

   Reply for full details.
   ```
4. Submit — approval usually takes a few hours to a day.
5. Once approved, upgrade `services/daily_summary.py` to use
   `whatsapp.send_template(...)` with the approved template name,
   falling back to `send_text` when the 24h window is still open.

(For the MVP, plain text works fine if shopkeepers message during the
day, which active shops do.)

---

## 9. Admin testing shortcuts

Once deployed with `X-Admin-Token` set (we re-use
`WHATSAPP_WEBHOOK_VERIFY_TOKEN` for this):

```bash
# Force the daily summary batch
curl -X POST https://your-domain/admin/run-daily-summary \
     -H "X-Admin-Token: $WHATSAPP_WEBHOOK_VERIFY_TOKEN"

# Get a specific shop's summary
curl "https://your-domain/admin/shop/+923001234567/summary" \
     -H "X-Admin-Token: $WHATSAPP_WEBHOOK_VERIFY_TOKEN"
```

---

## 10. Common problems

| Symptom | Likely cause |
|---|---|
| Webhook verification fails | Verify token mismatch between `.env` and Meta dashboard |
| `401 bad signature` in logs | `WHATSAPP_APP_SECRET` wrong; or Meta is testing with a payload you modified |
| `asyncpg.exceptions.InvalidCatalogNameError` | Wrong DB URL; check you used the Session-mode connection string, not pooler |
| Whisper returns nonsense | Voice note is too short (<1s) or silent — usually a fat-finger from the shopkeeper, just ask them to re-record |
| Replies not arriving | Check Meta app → WhatsApp → Configuration → webhook is still "Active" (Meta disables it after repeated 5xx responses) |
| `healthz` lists `SUPABASE_DB_URL` as missing but you set it | You left the placeholder `YOUR-PROJECT` in the string |
