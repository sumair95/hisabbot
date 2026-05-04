"""
Per-shop vocabulary for Whisper prompt biasing.

Whisper accepts a `prompt` parameter (~224 token budget) that nudges
transcription toward the listed vocabulary. This is especially powerful
for proper nouns: customer names like "Akbar Trader" or product names
like "Lifebuoy" otherwise get transcribed phonetically and inconsistently
across calls. Feeding the shop's known vocabulary makes transcripts
stable, which in turn makes the LLM extractor and downstream contact
matcher much more accurate.

Built lazily per shopkeeper, cached in-process for 5 minutes.
Cache is invalidated on contact creation so new names appear in the
next transcription without waiting for the TTL.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from . import db
from ..utils.logging import get_logger

log = get_logger("vocabulary")

_CACHE: dict[str, tuple[str, datetime]] = {}
_TTL = timedelta(minutes=5)

# Whisper budget: ~224 tokens. Keep room for the static seed + structure.
_MAX_CONTACTS = 40
_MAX_PRODUCTS = 15

# Static seed: common Roman-Urdu / mixed bookkeeping vocabulary that
# Whisper sometimes mishears (e.g. "udhaar" → "uddhar"). Including it
# here stabilises these across all transcriptions.
_STATIC_SEED = (
    "Bookkeeping vocabulary: udhaar, hisaab, paisa, sale, cash, supplier, "
    "haan, nahi, theek, galat, bhai, sahib, apa, baji, sau, hazaar, lakh, "
    "rupay, dukaan, maal."
)


async def get_shop_vocabulary(sk_id: str) -> str:
    """Return a Whisper prompt string biasing transcription to this shop's vocabulary."""
    now = datetime.now(timezone.utc)
    cached = _CACHE.get(sk_id)
    if cached and (now - cached[1]) < _TTL:
        return cached[0]

    vocab = await _build(sk_id)
    _CACHE[sk_id] = (vocab, now)
    return vocab


def invalidate(sk_id: str) -> None:
    """Drop the cached vocabulary for one shop (call after contact/product changes)."""
    _CACHE.pop(sk_id, None)


def invalidate_all() -> None:
    """For tests / admin tooling."""
    _CACHE.clear()


async def _build(sk_id: str) -> str:
    contacts = await db.get_contacts(sk_id)
    products = await db.get_recent_product_names(sk_id, limit=_MAX_PRODUCTS)

    parts: list[str] = []

    if contacts:
        names = [c["name"] for c in contacts[:_MAX_CONTACTS] if c.get("name")]
        if names:
            parts.append("Customers and suppliers: " + ", ".join(names))

    if products:
        parts.append("Products: " + ", ".join(products))

    parts.append(_STATIC_SEED)

    vocab = " ".join(parts)
    log.info(
        "vocabulary.built",
        sk_id=sk_id,
        contacts=len(contacts),
        products=len(products),
        chars=len(vocab),
    )
    return vocab
