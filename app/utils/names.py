"""
Utilities for normalising customer/supplier names before fuzzy matching.

Pakistani/Urdu context: names come with honorifics (bhai, sahib, sahab, apa,
baji, uncle, aunty, mian, chacha, mamu), varied spellings (Ahmed/Ahmad), and
case/whitespace noise. We strip all of this to a canonical form so that
"Ahmed bhai" and "ahmad" both normalise to "ahmed".
"""
from __future__ import annotations
import re
from rapidfuzz import fuzz, process


# Honorifics and polite suffixes commonly appended to names.
_HONORIFICS = {
    "bhai", "bhaiya", "bhaijaan", "bhaisaab",
    "sahib", "sahab", "saheb",
    "apa", "api", "apee", "apaa",
    "baji", "bajee",
    "uncle", "aunty", "auntie",
    "mian", "miyan", "miaan",
    "chacha", "chachu", "chachaji",
    "mamu", "mamoo", "mama",
    "khala", "khalu",
    "nana", "nani",
    "dada", "dadi",
    "ji", "jee",
    "sir", "madam", "maam", "mam",
    "haji", "hajji",
    "mr", "mrs", "ms",
}

# Simple Urdu→Roman fallbacks for a few very common names. This is a stopgap
# so that 'احمد' and 'Ahmed' can be matched; the LLM already gives us Roman
# form most of the time so this table stays small on purpose.
_URDU_ROMAN_HINTS = {
    "احمد": "ahmed",
    "علی": "ali",
    "محمد": "muhammad",
    "حسن": "hassan",
    "حسین": "hussain",
    "بلال": "bilal",
    "سائرہ": "saira",
    "فاطمہ": "fatima",
    "عائشہ": "aisha",
}


def normalize_name(raw: str | None) -> str:
    """Return a canonical lowercase key for name matching."""
    if not raw:
        return ""
    s = raw.strip().lower()

    # Replace any urdu-script whole word we know about
    for ur, ro in _URDU_ROMAN_HINTS.items():
        s = s.replace(ur, ro)

    # Strip punctuation/special chars, collapse whitespace
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()

    # Remove honorific tokens
    tokens = [t for t in s.split(" ") if t and t not in _HONORIFICS]
    return " ".join(tokens)


def best_match(
    query_norm: str,
    candidates: list[tuple[str, str]],   # [(id, normalized_name), ...]
    threshold: int = 85,
) -> tuple[str, int] | None:
    """
    Find the best fuzzy match above `threshold` (0-100).
    Returns (id, score) or None.
    """
    if not query_norm or not candidates:
        return None
    # process.extractOne works on (choice, key) — we give it the normalized names
    lookup = {cid: nname for cid, nname in candidates}
    result = process.extractOne(
        query_norm,
        lookup,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
    )
    if result is None:
        return None
    # result = (matched_value, score, key)
    _, score, cid = result
    return cid, int(score)
