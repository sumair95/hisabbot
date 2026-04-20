"""
LLM extraction service.
Primary: Anthropic Claude Haiku. Fallback: OpenAI gpt-4o-mini.
Returns a validated ExtractionResult object.
"""
from __future__ import annotations
import json
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from ..config import get_settings
from ..models.schemas import ExtractionResult, Intent
from ..prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_EXAMPLES, VOICE_TRANSCRIPT_HINT
from ..utils.logging import get_logger

log = get_logger("llm")

_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


def _anthropic_client() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _anthropic


def _openai_client() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _openai


def _build_user_prompt(text: str, is_voice: bool) -> str:
    parts = [EXTRACTION_EXAMPLES, ""]
    if is_voice:
        parts.append(f"Note: {VOICE_TRANSCRIPT_HINT}")
        parts.append("")
    parts.append(f'User: "{text}"')
    return "\n".join(parts)


async def _extract_anthropic(text: str, is_voice: bool) -> dict[str, Any]:
    settings = get_settings()
    client = _anthropic_client()
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=800,
        temperature=0.0,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(text, is_voice)}],
    )
    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    return _parse_json_lenient(raw)


async def _extract_openai(text: str, is_voice: bool) -> dict[str, Any]:
    settings = get_settings()
    client = _openai_client()
    resp = await client.chat.completions.create(
        model=settings.fallback_openai_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text, is_voice)},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    return _parse_json_lenient(raw)


def _parse_json_lenient(s: str) -> dict[str, Any]:
    """LLMs sometimes add ```json fences or stray prose; strip and parse."""
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # drop optional leading 'json'
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    # Find the first { and last } and parse that
    first = s.find("{")
    last = s.rfind("}")
    if first == -1 or last == -1:
        raise ValueError(f"LLM returned non-JSON: {s[:200]}")
    return json.loads(s[first : last + 1])


async def extract(text: str, is_voice: bool = False) -> ExtractionResult:
    """Main entry point. Tries Anthropic, falls back to OpenAI."""
    settings = get_settings()
    errors: list[str] = []

    if settings.anthropic_api_key:
        try:
            data = await _extract_anthropic(text, is_voice)
            return ExtractionResult.model_validate(data)
        except Exception as e:  # noqa: BLE001
            errors.append(f"anthropic: {e}")
            log.warning("llm.anthropic.failed", error=str(e))

    if settings.openai_api_key:
        try:
            data = await _extract_openai(text, is_voice)
            return ExtractionResult.model_validate(data)
        except Exception as e:  # noqa: BLE001
            errors.append(f"openai: {e}")
            log.warning("llm.openai.failed", error=str(e))

    # Both failed or unconfigured — degrade gracefully
    log.error("llm.all_failed", errors=errors)
    return ExtractionResult(
        intent=Intent.GREETING_OR_OTHER,
        needs_clarification=True,
        clarification_question=(
            "Abhi system mein koi dikkat hai, kuch der baad dobara try karein."
        ),
    )
