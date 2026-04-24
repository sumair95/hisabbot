"""
Text-to-speech using OpenAI TTS API.
Returns MP3 bytes ready to upload to WhatsApp.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("tts")

_TTS_MODEL = "tts-1"
_TTS_VOICE = "nova"


async def synthesize(text: str) -> bytes:
    """Convert text to MP3 bytes. Raises on API error."""
    client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    response = await client.audio.speech.create(
        model=_TTS_MODEL,
        voice=_TTS_VOICE,
        input=text[:4096],
        response_format="mp3",
    )
    audio = b""
    async for chunk in response.iter_bytes(chunk_size=4096):
        audio += chunk
    log.info("tts.synthesized", chars=len(text), bytes=len(audio))
    return audio
