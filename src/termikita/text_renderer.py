"""CoreText-based text rendering engine for Termikita.

Delegates drawing passes to cell_draw_helpers, glyph caching to GlyphAtlas,
and color resolution to color_resolver. The caller's NSView owns the context.
"""

from __future__ import annotations

from termikita.constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
from termikita.glyph_atlas import GlyphAtlas
from termikita.color_resolver import resolve_color
from termikita.buffer_manager import CellData
from termikita.cell_draw_helpers import draw_backgrounds, draw_glyphs, draw_decorations

# Line-height multiplier applied to raw ascender+descender+leading
_LINE_HEIGHT_MULT = 1.2
# Cursor beam width in points
_BEAM_WIDTH = 2.0
# Decoration / cursor underline stroke width in points
_DECO_WIDTH = 1.0


class TextRenderer:
    """CoreText/AppKit text renderer for terminal cell grids."""

    def __init__(self) -> None:
        self.primary_font: object = None
        self.bold_font: object = None
        self.italic_font: object = None
        self.bold_italic_font: object = None
        self.cell_width: float = 8.0
        self.cell_height: float = 16.0
        self.baseline_offset: float = 3.0
        self._atlas = GlyphAtlas()
        # (bold, italic) -> NSFont; rebuilt by set_font()
        self._fonts: dict[tuple[bool, bool], object] = {}
        self.set_font(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)

    def set_font(self, family: str, size: float) -> None:
        """Load primary font and derive bold/italic variants; rebuild atlas."""
        try:
            from AppKit import NSFont, NSFontManager  # type: ignore[import]

            font = NSFont.fontWithName_size_(family, size)
            if font is None:
                font = NSFont.monospacedSystemFontOfSize_weight_(size, 0.0)

            fm = NSFontManager.sharedFontManager()
            bold      = _safe_convert(fm, font, 0x2) or font   # NSBoldFontMask
            italic    = _safe_convert(fm, font, 0x1) or font   # NSItalicFontMask
            bold_italic = _safe_convert(fm, bold, 0x1) or bold

            self.primary_font    = font
            self.bold_font       = bold
            self.italic_font     = italic
            self.bold_italic_font = bold_italic

        except Exception:
            self.primary_font = self.bold_font = self.italic_font = self.bold_italic_font = None

        self._fonts = {
            (False, False): self.primary_font,
            (True,  False): self.bold_font,
            (False, True):  self.italic_font,
            (True,  True):  self.bold_italic_font,
        }
        self._calculate_metrics()
        self._atlas.clear()
        self._atlas.warm(self._fonts, self.cell_width)

    def get_cell_dimensions(self) -> tuple[float, float]:
        """Return (cell_width, cell_height) in points."""
        return (self.cell_width, self.cell_height)

    def invalidate_cache(self) -> None:
        """Clear glyph atlas (call after theme or DPI change)."""
        self._atlas.clear()

    def measure_char(self, char: str) -> float:
        """Advance width for *char* using primary font metrics."""
        advance, _ = self._atlas.lookup(char, False, False, self._fonts, self.cell_width)
        return advance

    def draw_line(
        self,
        context: object,
        y: float,
        cells: list[CellData],
        theme_colors: dict,
    ) -> None:
        """Render one row of terminal cells at vertical offset *y*."""
        if not cells:
            return
        draw_backgrounds(cells, y, self.cell_width, self.cell_height, theme_colors)
        draw_glyphs(cells, y, self.cell_width, self.baseline_offset, self._fonts, theme_colors)
        draw_decorations(cells, y, self.cell_width, self.cell_height, self.baseline_offset, theme_colors)

    def draw_cursor(
        self,
        context: object,
        row: int,
        col: int,
        style: str,
        color: object,
    ) -> None:
        """Draw terminal cursor at grid position (row, col).

        style: "block" | "beam" | "underline"
        color: NSColor resolved by caller from theme["cursor"]
        """
        try:
            from AppKit import NSBezierPath  # type: ignore[import]
            import AppKit  # type: ignore[import]

            x     = col * self.cell_width
            row_y = row * self.cell_height
            color.set()

            if style == "beam":
                NSBezierPath.fillRect_(AppKit.NSMakeRect(x, row_y, _BEAM_WIDTH, self.cell_height))
            elif style == "underline":
                NSBezierPath.fillRect_(AppKit.NSMakeRect(x, row_y, self.cell_width, _DECO_WIDTH))
            else:  # block (default)
                NSBezierPath.fillRect_(AppKit.NSMakeRect(x, row_y, self.cell_width, self.cell_height))
        except Exception:
            pass

    def draw_marked_text(
        self,
        context: object,
        text: str,
        cursor_col: int,
        cursor_row: int,
        theme_colors: dict,
    ) -> None:
        """Render IME composing text with underline highlight at cursor position."""
        if not text:
            return
        try:
            from AppKit import NSAttributedString, NSUnderlineStyleAttributeName  # type: ignore[import]
            import AppKit  # type: ignore[import]

            x    = cursor_col * self.cell_width
            pt_y = cursor_row * self.cell_height + self.baseline_offset
            fg   = resolve_color("default", is_fg=True, theme=theme_colors)
            font = self._fonts.get((False, False))
            attrs: dict = {AppKit.NSForegroundColorAttributeName: fg, NSUnderlineStyleAttributeName: 1}
            if font:
                attrs[AppKit.NSFontAttributeName] = font
            ns_str   = AppKit.NSString.stringWithString_(text)
            attr_str = NSAttributedString.alloc().initWithString_attributes_(ns_str, attrs)
            attr_str.drawAtPoint_(AppKit.NSMakePoint(x, pt_y))
        except Exception:
            pass

    def _calculate_metrics(self) -> None:
        """Derive cell_width, cell_height, baseline_offset from primary font."""
        font = self.primary_font
        if font is None:
            return
        try:
            glyph_id = font.glyphWithName_("M")
            self.cell_width = (
                font.advancementForGlyph_(glyph_id).width
                if glyph_id
                else font.maximumAdvancement().width
            )
            raw_height      = font.ascender() + abs(font.descender()) + font.leading()
            self.cell_height    = raw_height * _LINE_HEIGHT_MULT
            self.baseline_offset = abs(font.descender())
        except Exception:
            pass  # retain previous safe defaults


def _safe_convert(fm: object, font: object, trait_mask: int) -> object | None:
    """Apply trait via NSFontManager; return None on failure."""
    try:
        return fm.convertFont_toHaveTrait_(font, trait_mask)  # type: ignore[attr-defined]
    except Exception:
        return None
