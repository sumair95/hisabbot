"""
Resolve a raw customer name from a shopkeeper's message into an existing
contact (or create a new one). This is the highest-risk component of the
pipeline; we keep the logic in one place so it can be tested and iterated
without touching the rest of the app.

Strategy:
  1. Normalise the raw name (strip honorifics, lowercase, etc.).
  2. Look for an exact normalized match for this shopkeeper.
  3. Otherwise, fuzzy match against existing contacts (rapidfuzz WRatio).
  4. If no match >= threshold, create a new contact.
"""
from __future__ import annotations
from typing import Any

from ..utils.logging import get_logger
from ..utils.names import normalize_name, best_match

log = get_logger("contact_matching")

FUZZY_THRESHOLD = 85  # out of 100


async def resolve_contact(
    shopkeeper_id: str,
    raw_name: str,
    contact_type: str = "customer",
) -> dict[str, Any]:
    """Find or create a contact for this shopkeeper. Returns the DB row as dict."""
    from . import db as dbs  # avoid circular import at module load

    norm = normalize_name(raw_name)
    if not norm:
        raise ValueError("Cannot resolve empty contact name")

    async with dbs.conn() as c:
        # Exact normalized match
        row = await c.fetchrow(
            """
            SELECT * FROM contacts
             WHERE shopkeeper_id = $1 AND normalized_name = $2 AND type = $3
            """,
            shopkeeper_id, norm, contact_type,
        )
        if row:
            return dict(row)

        # Fuzzy match among this shop's contacts of same type
        rows = await c.fetch(
            "SELECT id, normalized_name FROM contacts WHERE shopkeeper_id = $1 AND type = $2",
            shopkeeper_id, contact_type,
        )
        candidates = [(str(r["id"]), r["normalized_name"]) for r in rows]
        match = best_match(norm, candidates, threshold=FUZZY_THRESHOLD)
        if match:
            cid, score = match
            log.info("contact.fuzzy_match", raw=raw_name, norm=norm, score=score)
            row = await c.fetchrow("SELECT * FROM contacts WHERE id = $1", cid)
            return dict(row)

        # Create new
        row = await c.fetchrow(
            """
            INSERT INTO contacts (shopkeeper_id, name, normalized_name, type)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            shopkeeper_id, raw_name.strip(), norm, contact_type,
        )
        log.info("contact.created", name=raw_name, type=contact_type)
        return dict(row)


async def find_contact_by_name(
    shopkeeper_id: str, raw_name: str, contact_type: str | None = None,
) -> dict[str, Any] | None:
    """Look up a contact by name without creating one (for queries)."""
    from . import db as dbs
    norm = normalize_name(raw_name)
    if not norm:
        return None

    async with dbs.conn() as c:
        if contact_type:
            rows = await c.fetch(
                "SELECT id, normalized_name FROM contacts WHERE shopkeeper_id = $1 AND type = $2",
                shopkeeper_id, contact_type,
            )
        else:
            rows = await c.fetch(
                "SELECT id, normalized_name FROM contacts WHERE shopkeeper_id = $1",
                shopkeeper_id,
            )
        candidates = [(str(r["id"]), r["normalized_name"]) for r in rows]
        match = best_match(norm, candidates, threshold=FUZZY_THRESHOLD)
        if not match:
            return None
        row = await c.fetchrow("SELECT * FROM contacts WHERE id = $1", match[0])
    return dict(row) if row else None
