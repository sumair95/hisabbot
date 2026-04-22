"""
Resolve a raw customer name from a shopkeeper's message into a contact.

Matching strategy:
  1. Normalise the name (strip honorifics, lowercase, digit spacing).
  2. Load the shopkeeper's contact list from a 60-second in-memory cache.
  3. Exact normalized match:
       - If confirmed within the last 10 minutes: return directly (session memory).
       - Otherwise: raise UnconfirmedContact so orchestrator can ask.
  4. Fuzzy match (adjusted WRatio with extra-token penalty):
       - 1 match  → raise UnconfirmedContact.
       - 2+ matches → raise AmbiguousContact.
  5. No match → create new contact, invalidate cache.
"""
from __future__ import annotations
import time
from typing import Any

from rapidfuzz import fuzz

from ..utils.logging import get_logger
from ..utils.names import normalize_name

log = get_logger("contact_matching")

FUZZY_THRESHOLD = 82

# ── Contact list cache (per shopkeeper, 60-second TTL) ────────────────────────
_contact_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 60

# ── Session confirmation memory (10-minute TTL) ───────────────────────────────
# Once a shopkeeper confirms "yes, this is Ali", skip re-asking for 10 minutes.
_confirmed: dict[str, float] = {}
_CONFIRM_TTL = 600


def _invalidate(shopkeeper_id: str) -> None:
    for k in [k for k in _contact_cache if k.startswith(shopkeeper_id)]:
        del _contact_cache[k]


async def _get_contacts(shopkeeper_id: str, contact_type: str, conn) -> list[dict]:
    key = f"{shopkeeper_id}:{contact_type}"
    now = time.monotonic()
    if key in _contact_cache and now - _contact_cache[key][0] < _CACHE_TTL:
        return _contact_cache[key][1]
    rows = await conn.fetch(
        "SELECT * FROM contacts WHERE shopkeeper_id = $1 AND type = $2",
        shopkeeper_id, contact_type,
    )
    data = [dict(r) for r in rows]
    _contact_cache[key] = (now, data)
    return data


def is_recently_confirmed(shopkeeper_id: str, contact_id: str) -> bool:
    return (time.monotonic() - _confirmed.get(f"{shopkeeper_id}:{contact_id}", 0)) < _CONFIRM_TTL


def mark_confirmed(shopkeeper_id: str, contact_id: str) -> None:
    _confirmed[f"{shopkeeper_id}:{contact_id}"] = time.monotonic()


# ── Scoring ───────────────────────────────────────────────────────────────────

def _adjusted_score(query_norm: str, candidate_norm: str) -> float:
    """WRatio with a penalty for extra tokens in the query not in the candidate.
    Prevents 'Ali Ahmed' from silently matching 'Ali'."""
    base = fuzz.WRatio(query_norm, candidate_norm)
    q_tokens = set(query_norm.split())
    c_tokens = set(candidate_norm.split())
    extra = q_tokens - c_tokens
    if extra and len(q_tokens) > len(c_tokens):
        base = max(0, base - len(extra) * 15)
    return base


# ── Exceptions ────────────────────────────────────────────────────────────────

class UnconfirmedContact(Exception):
    """One match found — ask shopkeeper: same person or new?"""
    def __init__(self, match: dict):
        self.match = match


class AmbiguousContact(Exception):
    """Multiple matches — ask shopkeeper to pick one."""
    def __init__(self, matches: list[dict]):
        self.matches = matches


# ── Main API ──────────────────────────────────────────────────────────────────

async def resolve_contact(
    shopkeeper_id: str,
    raw_name: str,
    contact_type: str = "customer",
) -> dict[str, Any]:
    """
    Find or create a contact. Raises UnconfirmedContact or AmbiguousContact
    when the orchestrator needs to ask the shopkeeper for clarification.
    """
    from . import db as dbs

    norm = normalize_name(raw_name)
    if not norm:
        raise ValueError("Cannot resolve empty contact name")

    async with dbs.conn() as c:
        contacts = await _get_contacts(shopkeeper_id, contact_type, c)

        # ── Exact normalized match ────────────────────────────────────────────
        exact = [ct for ct in contacts if ct["normalized_name"] == norm]
        if exact:
            if len(exact) == 1:
                ct = exact[0]
                if is_recently_confirmed(shopkeeper_id, str(ct["id"])):
                    return ct
                raise UnconfirmedContact(ct)
            raise AmbiguousContact(exact)

        # ── Fuzzy match ───────────────────────────────────────────────────────
        scored = sorted(
            [
                (score, ct) for ct in contacts
                if (score := _adjusted_score(norm, ct["normalized_name"])) >= FUZZY_THRESHOLD
            ],
            key=lambda x: x[0], reverse=True,
        )
        matches = [ct for _, ct in scored]
        if len(matches) == 1:
            raise UnconfirmedContact(matches[0])
        if len(matches) > 1:
            raise AmbiguousContact(matches)

        # ── No match — create new contact ─────────────────────────────────────
        row = await c.fetchrow(
            """
            INSERT INTO contacts (shopkeeper_id, name, normalized_name, type)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            shopkeeper_id, raw_name.strip(), norm, contact_type,
        )
        log.info("contact.created", name=raw_name, type=contact_type)
        _invalidate(shopkeeper_id)
        return dict(row)


async def find_contact_by_name(
    shopkeeper_id: str, raw_name: str, contact_type: str | None = None,
) -> dict[str, Any] | None:
    """Look up a contact by name without creating one (for balance queries)."""
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
        scored = sorted(
            [(fuzz.WRatio(norm, name), cid) for cid, name in candidates
             if fuzz.WRatio(norm, name) >= FUZZY_THRESHOLD],
            reverse=True,
        )
        if not scored:
            return None
        row = await c.fetchrow("SELECT * FROM contacts WHERE id = $1", scored[0][1])
    return dict(row) if row else None
