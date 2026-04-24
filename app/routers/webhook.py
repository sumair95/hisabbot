"""
WhatsApp Cloud API webhook.

GET  /webhook/whatsapp  — Meta's verification challenge during setup
POST /webhook/whatsapp  — inbound messages (and status callbacks, which we ignore)
"""
from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from ..config import get_settings
from ..services import db, orchestrator, replies, stt, tts, whatsapp
from ..utils.logging import get_logger

_VOICE_ON_TOKENS  = {"voice on", "voice reply on", "audio on", "awaz on", "audio reply on"}
_VOICE_OFF_TOKENS = {"voice off", "voice reply off", "audio off", "awaz off", "voice band", "audio reply off"}

router = APIRouter(prefix="/webhook", tags=["webhook"])
log = get_logger("webhook")


@router.get("/whatsapp", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
):
    """Meta calls this once when you save the webhook URL in the dashboard."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_webhook_verify_token:
        log.info("webhook.verified")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    log.warning("webhook.verify_failed", mode=hub_mode)
    raise HTTPException(status_code=403, detail="verification failed")


@router.post("/whatsapp")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    raw = await request.body()
    if not whatsapp.verify_signature(raw, x_hub_signature_256):
        log.warning("webhook.bad_signature")
        raise HTTPException(status_code=401, detail="bad signature")

    payload = await request.json()

    # WhatsApp payload shape:
    # {entry:[{changes:[{value:{messages:[...], contacts:[...], metadata:{...}}}]}]}
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                # Ignore status callbacks (sent/delivered/read)
                if "messages" not in value:
                    continue
                for msg in value["messages"]:
                    await _process_one_message(msg, value)
    except Exception as e:  # noqa: BLE001
        log.exception("webhook.handler_error", error=str(e))
        # Still return 200 so Meta doesn't hammer us with retries.
    return JSONResponse(content={"ok": True})


async def _process_one_message(msg: dict, value: dict) -> None:
    """Handle a single inbound message from the webhook payload."""
    wa_id = msg.get("id")
    from_ = msg.get("from")  # E.164 without '+'
    if not from_:
        return
    phone_number = "+" + from_ if not from_.startswith("+") else from_

    # Idempotency: Meta may retry.
    if wa_id and await db.was_wa_message_processed(wa_id):
        log.info("webhook.duplicate", wa_id=wa_id)
        return

    shopkeeper = await db.get_or_create_shopkeeper(phone_number)
    sk_id = str(shopkeeper["id"])

    msg_type = msg.get("type")
    text_content: str | None = None
    transcript: str | None = None
    kind = "text"
    media_url = None

    if msg_type == "text":
        text_content = (msg.get("text") or {}).get("body", "").strip()

    elif msg_type in ("audio", "voice"):
        kind = "voice"
        media = msg.get(msg_type) or {}
        media_id = media.get("id")
        if not media_id:
            return
        try:
            audio_bytes, mime = await whatsapp.fetch_media(media_id)
            ext = "ogg" if "ogg" in mime else "mp3"
            transcript = await stt.transcribe(audio_bytes, filename=f"voice.{ext}")
            text_content = transcript
        except Exception as e:  # noqa: BLE001
            log.error("webhook.voice_failed", error=str(e))
            await whatsapp.send_text(
                phone_number,
                "Voice note samajh nahi aayi. Dobara bhejein ya text likh dein.",
            )
            await db.log_message(
                shopkeeper_id=sk_id, wa_message_id=wa_id,
                direction="inbound", kind="voice",
                content=None, transcript=None, intent="ERROR",
            )
            return

    elif msg_type == "image":
        # MVP: politely decline
        await whatsapp.send_text(
            phone_number,
            "Abhi image support nahi hai — text ya voice note bhejein.",
        )
        await db.log_message(
            shopkeeper_id=sk_id, wa_message_id=wa_id,
            direction="inbound", kind="image",
        )
        return

    else:
        log.info("webhook.unsupported_type", type=msg_type)
        return

    if not text_content:
        return

    lang = shopkeeper.get("language_pref") or "roman_urdu"

    # ---- Voice reply toggle (handled before LLM to save cost) ----
    normalized = text_content.strip().lower()
    if normalized in _VOICE_ON_TOKENS:
        await db.update_shopkeeper(sk_id, voice_reply=True)
        shopkeeper = await db.get_or_create_shopkeeper(phone_number)
        reply_text = replies.voice_reply_enabled(lang)
        await _send_reply(phone_number, reply_text, kind="text", sk_id=sk_id, wa_id=wa_id,
                          text_content=text_content, transcript=transcript,
                          extraction_json=None, txn_id=None, use_voice=False)
        return
    if normalized in _VOICE_OFF_TOKENS:
        await db.update_shopkeeper(sk_id, voice_reply=False)
        shopkeeper = await db.get_or_create_shopkeeper(phone_number)
        reply_text = replies.voice_reply_disabled(lang)
        await _send_reply(phone_number, reply_text, kind="text", sk_id=sk_id, wa_id=wa_id,
                          text_content=text_content, transcript=transcript,
                          extraction_json=None, txn_id=None, use_voice=False)
        return

    # ---- Run the orchestrator ----
    reply_text, extraction_json, txn_id = await orchestrator.handle_message(
        shopkeeper,
        text_content,
        source=("voice" if kind == "voice" else "text"),
        transcript=transcript,
        raw_message=text_content,
    )

    # Log inbound
    await db.log_message(
        shopkeeper_id=sk_id,
        wa_message_id=wa_id,
        direction="inbound",
        kind=kind,
        content=text_content,
        media_url=media_url,
        transcript=transcript,
        intent=(extraction_json or {}).get("intent"),
        extraction_json=extraction_json,
        transaction_id=txn_id,
    )

    use_voice = bool(shopkeeper.get("voice_reply")) and kind == "voice"

    # Append voice tip when they send a voice note but voice reply is still off
    if kind == "voice" and not use_voice:
        reply_text = reply_text + "\n\n" + replies.voice_note_tip(lang)

    await _send_reply(phone_number, reply_text, kind=kind, sk_id=sk_id, wa_id=None,
                      text_content=None, transcript=None,
                      extraction_json=extraction_json, txn_id=txn_id,
                      use_voice=use_voice)


async def _send_reply(
    phone_number: str,
    reply_text: str,
    *,
    kind: str,
    sk_id: str,
    wa_id: str | None,
    text_content: str | None,
    transcript: str | None,
    extraction_json: dict | None,
    txn_id: str | None,
    use_voice: bool,
) -> None:
    """Send a reply — audio if use_voice is True, otherwise text.
    Falls back to text if TTS or media upload fails.
    """
    sent_kind = "text"
    if use_voice:
        try:
            audio_bytes = await tts.synthesize(reply_text)
            media_id = await whatsapp.upload_media(audio_bytes)
            await whatsapp.send_audio(phone_number, media_id)
            sent_kind = "voice"
            log.info("webhook.voice_reply_sent", to=phone_number)
        except Exception as e:  # noqa: BLE001
            log.error("webhook.voice_reply_failed", error=str(e))
            # Fall back to text
            try:
                await whatsapp.send_text(phone_number, reply_text)
            except Exception as e2:  # noqa: BLE001
                log.error("webhook.reply_failed", error=str(e2))
                return
    else:
        try:
            await whatsapp.send_text(phone_number, reply_text)
        except Exception as e:  # noqa: BLE001
            log.error("webhook.reply_failed", error=str(e))
            return

    await db.log_message(
        shopkeeper_id=sk_id,
        direction="outbound",
        kind=sent_kind,
        wa_message_id=None,
        content=reply_text,
    )
