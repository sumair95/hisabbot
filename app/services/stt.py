"""
Speech-to-text via Groq (whisper-large-v3).

Groq exposes an OpenAI-compatible audio endpoint, so we reuse the OpenAI
SDK with a different base_url. WhatsApp voice notes arrive as OGG/Opus;
they are pre-cleaned by app/services/audio_preprocess.py and reach this
module as 16kHz mono WAV.

`transcribe()` returns a TranscriptionResult — both the text and the
per-call confidence metrics (avg_logprob, no_speech_prob,
compression_ratio). Use `is_low_confidence(result)` to decide whether to
trust the transcript or ask the shopkeeper to re-record.
"""
from __future__ import annotations
import io
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("stt")

_client: AsyncOpenAI | None = None


# Confidence thresholds. These are conservative defaults derived from
# OpenAI's reference Whisper code:
#   * avg_logprob < -1.0 indicates very poor token probability;
#     -0.7 catches most garbled / wrong-language hallucinations
#   * no_speech_prob > 0.6 indicates the model itself thinks this is silence
#   * compression_ratio > 2.4 indicates repeated/looping output
LOW_LOGPROB_THRESHOLD = -0.7
HIGH_NO_SPEECH_THRESHOLD = 0.6
HIGH_COMPRESSION_THRESHOLD = 2.4


@dataclass
class TranscriptionResult:
    text: str
    duration_sec: float | None
    avg_logprob: float | None
    no_speech_prob: float | None
    compression_ratio: float | None
    language: str | None


def _groq() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
    return _client


async def transcribe(
    audio_bytes: bytes,
    filename: str = "voice.wav",
    prompt: str = "",
) -> TranscriptionResult:
    """
    Transcribe audio bytes via Groq's whisper-large-v3 with verbose_json.
    Urdu is hinted as the primary language; the model still handles
    code-mixed Urdu / English / Roman-Urdu speech well.

    `prompt` is the per-shop vocabulary biasing string (~224 tokens).
    See app/services/vocabulary.py.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    client = _groq()
    buf = io.BytesIO(audio_bytes)
    buf.name = filename

    try:
        resp: Any = await client.audio.transcriptions.create(
            model=settings.groq_whisper_model,
            file=buf,
            language="ur",
            response_format="verbose_json",
            temperature=0.0,
            prompt=prompt,
        )
    except Exception as e:  # noqa: BLE001
        log.error("stt.failed", error=str(e), provider="groq")
        raise

    text = (getattr(resp, "text", None) or "").strip()
    duration = _coerce_float(getattr(resp, "duration", None))
    language = getattr(resp, "language", None)

    avg_logprob, no_speech_prob, compression_ratio = _segment_metrics(
        getattr(resp, "segments", None) or []
    )

    log.info(
        "stt.ok",
        chars=len(text),
        provider="groq",
        model=settings.groq_whisper_model,
        prompt_chars=len(prompt),
        duration_sec=duration,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
    )

    return TranscriptionResult(
        text=text,
        duration_sec=duration,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
        language=language,
    )


def is_low_confidence(r: TranscriptionResult) -> bool:
    """
    Return True if any of the verbose_json metrics indicate Whisper isn't
    confident in this transcript. Used by the webhook to ask the shopkeeper
    to re-record instead of feeding garbage to the LLM extractor.

    Note: empty text is also treated as low-confidence (the model returned
    nothing usable).
    """
    if not r.text:
        return True
    if r.no_speech_prob is not None and r.no_speech_prob > HIGH_NO_SPEECH_THRESHOLD:
        return True
    if r.avg_logprob is not None and r.avg_logprob < LOW_LOGPROB_THRESHOLD:
        return True
    if r.compression_ratio is not None and r.compression_ratio > HIGH_COMPRESSION_THRESHOLD:
        return True
    return False


# -------------------- helpers --------------------

def _segment_metrics(
    segments: list,
) -> tuple[float | None, float | None, float | None]:
    """
    Aggregate per-segment confidence metrics into a single number each.

    avg_logprob:        duration-weighted mean across segments
    no_speech_prob:     worst (max) value across segments — single bad
                        segment is enough to be suspicious
    compression_ratio:  worst (max) value — repeated / looping output is
                        usually concentrated in one segment
    """
    if not segments:
        return None, None, None

    total_dur = 0.0
    weighted_logprob = 0.0
    max_no_speech: float | None = None
    max_compression: float | None = None

    for seg in segments:
        # Segments may be Pydantic objects or plain dicts depending on SDK
        s = seg if isinstance(seg, dict) else seg.__dict__

        start = _coerce_float(s.get("start"))
        end = _coerce_float(s.get("end"))
        dur = max((end or 0.0) - (start or 0.0), 0.0)

        lp = _coerce_float(s.get("avg_logprob"))
        nsp = _coerce_float(s.get("no_speech_prob"))
        cr = _coerce_float(s.get("compression_ratio"))

        if lp is not None and dur > 0:
            weighted_logprob += lp * dur
            total_dur += dur

        if nsp is not None:
            max_no_speech = nsp if max_no_speech is None else max(max_no_speech, nsp)
        if cr is not None:
            max_compression = cr if max_compression is None else max(max_compression, cr)

    avg_logprob = weighted_logprob / total_dur if total_dur > 0 else None
    return avg_logprob, max_no_speech, max_compression


def _coerce_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
