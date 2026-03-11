"""Glyph atlas cache: maps (char, bold, italic) -> (advance_width, font_ref).

Uses an OrderedDict as a bounded LRU cache (max 8192 entries).
Pre-populates printable ASCII on font init for all 4 style combinations.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # NSFont type hint only needed at runtime via try/except

# LRU capacity — large enough for Unicode coverage, small enough to stay fast
_ATLAS_MAX = 8192

# Printable ASCII range pre-warmed on every font change
_ASCII_START = 0x20  # space
_ASCII_END = 0x7E    # tilde


class GlyphAtlas:
    """LRU cache from (char, bold, italic) to (advance_width, font_ref).

    advance_width is in points (float).
    font_ref is the NSFont that can actually render the glyph (may be a
    fallback font for non-ASCII characters).
    """

    def __init__(self) -> None:
        # OrderedDict gives O(1) move-to-end for LRU semantics
        self._cache: OrderedDict[tuple[str, bool, bool], tuple[float, object]] = OrderedDict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def warm(self, fonts: dict[tuple[bool, bool], object], default_advance: float) -> None:
        """Pre-populate printable ASCII for all 4 style combos.

        Args:
            fonts: mapping (bold, italic) -> NSFont
            default_advance: cell_width used when glyph advance unavailable
        """
        self._cache.clear()
        for bold in (False, True):
            for italic in (False, True):
                font = fonts.get((bold, italic))
                if font is None:
                    continue
                for code in range(_ASCII_START, _ASCII_END + 1):
                    ch = chr(code)
                    advance = _measure_advance(font, ch, default_advance)
                    self._put((ch, bold, italic), (advance, font))

    def lookup(
        self,
        char: str,
        bold: bool,
        italic: bool,
        fonts: dict[tuple[bool, bool], object],
        default_advance: float,
    ) -> tuple[float, object]:
        """Return (advance_width, font_ref) for char, computing and caching if needed.

        For non-ASCII characters, uses CoreText font fallback to find a font
        that can actually render the glyph (prevents "??" for missing glyphs).
        """
        key = (char, bold, italic)
        entry = self._cache.get(key)
        if entry is not None:
            # Move to end = most recently used
            self._cache.move_to_end(key)
            return entry

        font = fonts.get((bold, italic)) or fonts.get((False, False))
        # For non-ASCII, find a font that can render this character
        if font and char and ord(char) > 0x7E:
            font = _find_fallback_font(font, char)
        advance = _measure_advance(font, char, default_advance)
        value = (advance, font)
        self._put(key, value)
        return value

    def clear(self) -> None:
        """Discard all cached entries (call on font change)."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _put(self, key: tuple[str, bool, bool], value: tuple[float, object]) -> None:
        """Insert entry, evicting LRU entry when at capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= _ATLAS_MAX:
                # popitem(last=False) removes the oldest (LRU) entry
                self._cache.popitem(last=False)
            self._cache[key] = value


# ---------------------------------------------------------------------------
# Module-level helper (keeps GlyphAtlas class lean)
# ---------------------------------------------------------------------------

def _find_fallback_font(primary_font: object, char: str) -> object:
    """Use CoreText to find a font that can render *char*.

    CTFontCreateForString checks the primary font's cascade list and
    system fonts, returning a font that has the glyph. Returns primary
    if it already covers the character.
    """
    try:
        from CoreText import CTFontCreateForString  # type: ignore[import]
        from CoreFoundation import CFRangeMake  # type: ignore[import]

        # Use UTF-16 length: supplementary plane chars (emoji, ext-PUA) need 2 units
        utf16_len = 2 if ord(char) > 0xFFFF else 1
        result = CTFontCreateForString(primary_font, char, CFRangeMake(0, utf16_len))
        return result if result else primary_font
    except Exception:
        return primary_font


def _measure_advance(font: object, char: str, fallback: float) -> float:
    """Return advance width for *char* in *font*, or *fallback* on failure."""
    try:
        from AppKit import NSString  # type: ignore[import]
        import CoreText  # type: ignore[import]

        # Build a minimal attributed string and measure via CoreText
        cf_str = NSString.stringWithString_(char)
        attrs = {CoreText.kCTFontAttributeName: font}
        attr_str = CoreText.CFAttributedStringCreate(None, cf_str, attrs)
        line = CoreText.CTLineCreateWithAttributedString(attr_str)
        width = CoreText.CTLineGetTypographicBounds(line, None, None, None)
        return float(width) if width > 0 else fallback
    except Exception:
        return fallback
