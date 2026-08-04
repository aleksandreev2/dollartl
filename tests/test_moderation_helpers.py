import re

from dollartl.services.moderation import FALLBACK_RULES, normalize_for_matching


def test_normalization_handles_unicode_and_leetspeak() -> None:
    assert normalize_for_matching("  T3ST  ") == "test"


def test_fallback_patterns_match_obfuscated_prohibited_terms() -> None:
    pattern = next(pattern for code, _, pattern in FALLBACK_RULES if code == "nword")
    assert re.search(pattern, "n 1 g g 3 r", re.IGNORECASE)
