"""
WhatsApp Cloud API webhook.

GET  /webhook/whatsapp  — Meta's verification challenge during setup
POST /webhook/whatsapp  — inbound messages (and status callbacks, which we ignore)
"""
from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from ..config import get_settings
from ..services import db, orchestrator, stt, whatsapp
from ..utils.logging import get_logger

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

    # Run the orchestrator
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

    # Send reply
    try:
        await whatsapp.send_text(phone_number, reply_text)
        await db.log_message(
            shopkeeper_id=sk_id,
            direction="outbound",
            kind="text",
            wa_message_id=None,
            content=reply_text,
        )
    except Exception as e:  # noqa: BLE001
        log.error("webhook.reply_failed", error=str(e))
