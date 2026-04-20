"""Tests for the honorific-stripping name normaliser."""
from app.utils.names import normalize_name, best_match


def test_normalize_basic():
    assert normalize_name("Ahmed") == "ahmed"
    assert normalize_name("  AHMED  ") == "ahmed"


def test_normalize_strips_honorifics():
    assert normalize_name("Ahmed bhai") == "ahmed"
    assert normalize_name("ahmed sahib") == "ahmed"
    assert normalize_name("Bilal Uncle") == "bilal"
    assert normalize_name("Saira apa") == "saira"
    assert normalize_name("Fatima baji") == "fatima"
    assert normalize_name("Mian Ali") == "ali"


def test_normalize_compound_names():
    assert normalize_name("Ahmed Khan") == "ahmed khan"
    assert normalize_name("Mr. Ahmed Khan") == "ahmed khan"
    assert normalize_name("Ahmed Khan bhai") == "ahmed khan"


def test_normalize_urdu_script_hint():
    # Falls back to our tiny transliteration table
    assert normalize_name("احمد") == "ahmed"


def test_normalize_empty():
    assert normalize_name("") == ""
    assert normalize_name(None) == ""
    assert normalize_name("   ") == ""


def test_best_match_finds_close():
    candidates = [("c1", "ahmed khan"), ("c2", "bilal"), ("c3", "saira")]
    match = best_match("ahmad khan", candidates, threshold=85)
    assert match is not None
    cid, score = match
    assert cid == "c1"
    assert score >= 85


def test_best_match_rejects_far():
    candidates = [("c1", "ahmed"), ("c2", "bilal")]
    assert best_match("farhan", candidates, threshold=85) is None


def test_best_match_empty():
    assert best_match("", [("c1", "ahmed")]) is None
    assert best_match("ahmed", []) is None
