"""
WhatsApp Cloud API client.

Responsibilities:
- Send plain-text replies to a shopkeeper
- Fetch media (voice notes) given a Meta media id
- Verify the X-Hub-Signature-256 header on incoming webhooks
- (Later) send template messages for the 9pm daily summary

Reference: https://developers.facebook.com/docs/whatsapp/cloud-api
"""
from __future__ import annotations
import hmac
import hashlib
from typing import Any
import httpx

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("whatsapp")

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().whatsapp_access_token}",
        "Content-Type": "application/json",
    }


# ----- inbound signature verification ------------------------

def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """
    Verify X-Hub-Signature-256 header from Meta.
    Returns True if the app secret is not configured (dev mode) or signature matches.
    """
    settings = get_settings()
    if not settings.whatsapp_app_secret:
        # In dev you may not have set this; allow through but warn.
        log.warning("whatsapp.signature.skip (WHATSAPP_APP_SECRET not set)")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


# ----- outbound: send text -----------------------------------

async def send_text(to: str, body: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        log.warning("whatsapp.send.skipped", reason="not_configured", to=to)
        return {"skipped": True}

    url = f"{GRAPH_BASE}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        if r.status_code >= 400:
            log.error("whatsapp.send.error", status=r.status_code, body=r.text)
            r.raise_for_status()
        data = r.json()
        log.info("whatsapp.sent", to=to, id=data.get("messages", [{}])[0].get("id"))
        return data


# ----- outbound: template (for proactive daily summary) ------

async def send_template(
    to: str, template_name: str, lang: str = "en", components: list | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{GRAPH_BASE}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang},
            "components": components or [],
        },
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


# ----- inbound: fetch media (voice note bytes) ---------------

async def fetch_media(media_id: str) -> tuple[bytes, str]:
    """
    Two-step: GET media metadata to find the URL, then GET the URL
    (both with the access token). Returns (bytes, mime_type).
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_url = f"{GRAPH_BASE}/{media_id}"
        r = await client.get(meta_url, headers=_headers())
        r.raise_for_status()
        info = r.json()
        download_url = info["url"]
        mime_type = info.get("mime_type", "audio/ogg")

        r2 = await client.get(download_url, headers=_headers())
        r2.raise_for_status()
        return r2.content, mime_type
