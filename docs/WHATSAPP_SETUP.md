# WhatsApp Cloud API — Notes & Gotchas

Things that bite everyone the first time they integrate with the
Cloud API, collected here so you don't have to learn them the hard way.

## The 24-hour rule

You can only send free-form messages within 24 hours of the user's
last message to you. Outside that window, you must use a pre-approved
**Message Template**.

Implications for this project:
- Replies to user-initiated conversation: always fine.
- The 9 PM daily summary cron: fine if the shopkeeper messaged earlier
  today. If not, you need `template daily_summary`.

## Conversation pricing

Meta charges per "conversation" (a 24-hour window per user), not per
message. Categories matter:

| Category | Price (Pakistan, approx) | When it triggers |
|---|---|---|
| Service | Free | User-initiated messages (most of yours) |
| Utility | ~$0.004 | Templates like daily summary |
| Marketing | ~$0.02 | Promotional templates (you don't need these) |

First 1,000 service conversations/month are free. For MVP volumes you
will be well within the free tier.

## Phone number tiers

Starts at **Tier 1** — can message 1,000 unique users per 24h. Tier
goes up automatically as quality stays high. For 20–50 shopkeepers
you'll never notice this.

## What you lose if you use unofficial libraries

- `whatsapp-web.js` / `Baileys`: work by driving WhatsApp Web. They get
  banned eventually, and the ban hits the user's phone number itself —
  the shopkeeper loses their business number.
- You cannot use templates or scheduled messages reliably.
- No business verification badge.

Just use the Cloud API. It's free at this scale and stable.

## Dealing with voice notes

WhatsApp sends voice notes as two fields:
```json
"type": "audio",
"audio": { "id": "MEDIA_ID", "mime_type": "audio/ogg; codecs=opus", ... }
```

To get bytes:
1. `GET https://graph.facebook.com/v21.0/{MEDIA_ID}` with Bearer token →
   returns `{url, mime_type, ...}`.
2. `GET {url}` with Bearer token → returns the raw OGG bytes.

Whisper accepts OGG directly, no conversion needed. (We pass
`filename="voice.ogg"` because the SDK uses the file extension to
guess format.)

## Message templates

Templates are text with `{{1}}, {{2}}, ...` placeholders, approved by
Meta. Approval is usually < 1 day for utility templates.

When editing `services/daily_summary.py` to use a template:

```python
await whatsapp.send_template(
    to=phone,
    template_name="daily_summary",
    lang="en",
    components=[{
        "type": "body",
        "parameters": [
            {"type": "text", "text": shop_name},
            {"type": "text", "text": f"{cash:,.0f}"},
            {"type": "text", "text": f"{credit:,.0f}"},
            {"type": "text", "text": f"{pr:,.0f}"},
            {"type": "text", "text": f"{pm:,.0f}"},
            {"type": "text", "text": f"{net:,.0f}"},
        ]
    }],
)
```

## Webhook retries

Meta retries a webhook if you return non-2xx. We always return
`{"ok": true}` even on internal errors so Meta doesn't pound us.
Logs surface the errors instead.

## Testing checklist

- [ ] GET /webhook/whatsapp echoes the challenge when verify token
  matches
- [ ] POST with a plain-text message reaches `_process_one_message`
- [ ] Duplicate POST with same `wa_message_id` is a no-op
- [ ] Voice message triggers Whisper
- [ ] Out-of-window send returns the Meta error we've logged a warning
  for (rather than crashing)
