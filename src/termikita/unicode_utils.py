"""Unicode utilities for Vietnamese text and wide character handling."""

import unicodedata


def normalize_text(text: str) -> str:
    """Normalize text to NFC form for consistent Vietnamese rendering.

    Vietnamese diacritics can be encoded as precomposed (NFC) or decomposed (NFD).
    NFC ensures combining marks are merged with base characters before rendering.
    """
    return unicodedata.normalize("NFC", text)


def char_display_width(char: str) -> int:
    """Return display width of a single character.

    Returns:
        0 for combining/non-spacing marks (Vietnamese diacritics, etc.)
        1 for normal-width characters
        2 for wide/fullwidth characters (CJK, emoji, etc.)
    """
    category = unicodedata.category(char)
    # Combining marks: Mn=non-spacing, Me=enclosing, Mc=spacing combining
    if category in ("Mn", "Me", "Mc"):
        return 0
    east_asian = unicodedata.east_asian_width(char)
    if east_asian in ("W", "F"):  # Wide or Fullwidth
        return 2
    return 1


def string_display_width(text: str) -> int:
    """Return total display width of a string (sum of per-character widths)."""
    return sum(char_display_width(c) for c in text)
