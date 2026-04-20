"""
Speech-to-text via OpenAI Whisper.
WhatsApp voice notes are OGG/Opus. Whisper accepts OGG directly so no
conversion needed.
"""
from __future__ import annotations
import io
from openai import AsyncOpenAI

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("stt")

_client: AsyncOpenAI | None = None


def _openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Transcribe audio bytes to text. We hint Urdu as the primary language,
    but Whisper handles code-mixed Urdu/English/Roman-Urdu speech reasonably
    well when language='ur' is set.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = _openai()
    # The OpenAI SDK expects a file-like with a name attribute.
    buf = io.BytesIO(audio_bytes)
    buf.name = filename

    try:
        resp = await client.audio.transcriptions.create(
            model=settings.openai_whisper_model,
            file=buf,
            language="ur",           # primary: Urdu. Whisper still handles mixed speech.
            response_format="text",
            temperature=0.0,
        )
        # response_format='text' returns a plain string in the SDK
        text = resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
        text = (text or "").strip()
        log.info("stt.ok", chars=len(text))
        return text
    except Exception as e:  # noqa: BLE001
        log.error("stt.failed", error=str(e))
        raise
