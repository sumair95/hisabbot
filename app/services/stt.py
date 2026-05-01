"""
Speech-to-text via Groq (whisper-large-v3).
Groq exposes an OpenAI-compatible audio endpoint, so we reuse the OpenAI
SDK with a different base_url. WhatsApp voice notes are OGG/Opus and
whisper-large-v3 accepts them directly.
"""
from __future__ import annotations
import io
from openai import AsyncOpenAI

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("stt")

_client: AsyncOpenAI | None = None


def _groq() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
    return _client


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Transcribe audio bytes to text via Groq's whisper-large-v3.
    Urdu is hinted as the primary language; the model still handles
    code-mixed Urdu/English/Roman-Urdu speech well.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    client = _groq()
    buf = io.BytesIO(audio_bytes)
    buf.name = filename

    try:
        resp = await client.audio.transcriptions.create(
            model=settings.groq_whisper_model,
            file=buf,
            language="ur",
            response_format="text",
            temperature=0.0,
        )
        text = resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
        text = (text or "").strip()
        log.info("stt.ok", chars=len(text), provider="groq", model=settings.groq_whisper_model)
        return text
    except Exception as e:  # noqa: BLE001
        log.error("stt.failed", error=str(e), provider="groq")
        raise
