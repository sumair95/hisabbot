# NEXT_STEPS

Action items. Grouped by who needs to do them.

---

## A. Things YOU must do (require credentials / approvals / Windows access)

### A1. Extract the project to `C:\Users\admin\AI Agent`
You'll receive a zip (`kirana-bookkeeper.zip`). Extract its contents
(not the zip-named folder — the contents) into
`C:\Users\admin\AI Agent\`. The structure should be:
```
C:\Users\admin\AI Agent\
├── app\
├── db\
├── docs\
├── tests\
├── README.md
├── requirements.txt
├── .env.example
├── Dockerfile
└── ...
```

### A2. Create the cloud accounts (see `docs/SETUP.md` for details)
- [ ] Meta Business + WhatsApp Cloud API app (start business
      verification immediately — 1–2 week wait)
- [ ] Supabase project in `ap-south-1` (Mumbai)
- [ ] Anthropic console + API key
- [ ] OpenAI console + API key (for Whisper)

### A3. Configure `.env`
```
copy .env.example .env
notepad .env
```
Fill in everything. Run `curl http://localhost:8000/healthz` after
starting the server — it will list any missing values.

### A4. Apply the DB schema
Easiest: paste `db/schema.sql` into Supabase SQL Editor → Run.

### A5. Create the GitHub repo and push
From `C:\Users\admin\AI Agent` in PowerShell or Git Bash:
```bash
git init
git add .
git commit -m "Initial commit: Kirana Bookkeeper MVP"
git branch -M main

# Then on GitHub, create a new empty repo (no README, no gitignore)
# and copy its URL. Then:
git remote add origin https://github.com/<you>/kirana-bookkeeper.git
git push -u origin main
```

### A6. Deploy to Railway
```bash
# one-time
railway login
railway init
# then
railway up
```
Add all `.env` variables in Railway's Variables tab. Generate a public
domain. Put that domain in Meta's webhook config.

### A7. Register the Meta webhook
Meta app → WhatsApp → Configuration → Webhook → Edit:
- URL: `https://<railway-domain>/webhook/whatsapp`
- Verify token: whatever you set for `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
- Subscribe to: **messages**

### A8. Submit the `daily_summary` template for approval
Meta Business → WhatsApp Manager → Message Templates. Template body
provided in `docs/SETUP.md` §8.

### A9. Onboard your first 3 shopkeepers in person
Seriously — do not remote-onboard. Sit with them, watch what they try
to say. Iterate on the prompt based on the first 100 real messages.

---

## B. Things I could not do (physical/environmental limits)

- **Write to `C:\Users\admin\AI Agent`**: I'm in a Linux sandbox, not
  on your Windows box. Delivered as a zip you extract.
- **Push to GitHub**: I have no GitHub credentials and should never
  hold them. Local git init done — you run `git remote add` + `push`.
- **Call real APIs with your keys**: I can't contact Meta / Supabase /
  OpenAI / Anthropic from this sandbox. The integration code is
  written and tested in isolation (21/21 unit tests pass). The first
  real-traffic test happens on your machine.

---

## C. Small improvements to make in the first week of real traffic

These are known rough edges you'll want to polish once you see real
messages:

- [ ] **Rate limit per shopkeeper** — cap at ~200 voice notes/day. Use
      a simple Postgres count query in `webhook._process_one_message`,
      reject with a polite message above cap.
- [ ] **Switch daily summary to template send** once Meta approves your
      `daily_summary` template. See `docs/WHATSAPP_SETUP.md`.
- [ ] **Two-contact disambiguation** — when there are multiple matches
      above the fuzzy threshold, reply with `Aapke 2 Ahmed hain: Ahmed
      Khan (1200 udhaar), Ahmed bhai (300 udhaar). Kaun sa?` and hold
      the transaction in a `pending_transactions` table for 2 minutes.
      Not in MVP because it adds real complexity; add once you see it
      happen twice.
- [ ] **Confirmation for medium-confidence extractions** — when the
      LLM returns `confidence < 0.75`, reply `Maine likha: ... sahi
      hai? (haan/nahi)` instead of silently logging. Pipe off the
      confidence value from the extraction JSON.
- [ ] **Weekly & monthly summaries** on demand.
- [ ] **Customer reminders** — "Ahmed bhai, aap par PKR 1,200 udhaar
      hai" sent from the shop's number with shopkeeper's approval.
      This is the single highest-value follow-on feature.

---

## D. Things NOT to build in month 1

(Repeating from the plan because the temptation is real.)

- Inventory management
- Invoices / receipts
- Web or mobile dashboard
- Photo-of-receipt extraction
- Multi-employee per shop
- Automated recurring billing integration (use manual EasyPaisa/JazzCash
  for the first 30 days)

Each is a multi-week rabbit hole that doesn't move the wedge.

---

## E. When you come back to this repo

1. Read `WORKLOG.md` — most recent entry first.
2. Read this file.
3. Run `pytest` to make sure nothing drifted.
4. Look at `docs/ARCHITECTURE.md` if you're making a structural change.
