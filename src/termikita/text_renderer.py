"""CoreText-based text rendering engine for Termikita.

Delegates drawing passes to cell_draw_helpers, glyph caching to GlyphAtlas,
and color resolution to color_resolver. The caller's NSView owns the context.
"""

from __future__ import annotations

from termikita.buffer_manager import CellData
from termikita.cell_draw_helpers import draw_backgrounds, draw_decorations, draw_glyphs
from termikita.color_resolver import resolve_color
from termikita.constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
from termikita.glyph_atlas import GlyphAtlas

# Line-height multiplier applied to ceiled font metrics.
# 1.0 matches Terminal.app (tight lines, block art connects perfectly).
# Values >1.0 add inter-line spacing but break block character art (█▄▀).
_LINE_HEIGHT_MULT = 1.0
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
        # Individual font metrics for coordinate calculations
        self.ascender: float = 12.0
        self.descender: float = 3.0
        self.leading: float = 0.0
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

            # Add system font cascade for missing glyph fallback
            font      = _add_font_cascade(font)
            bold      = _add_font_cascade(bold)
            italic    = _add_font_cascade(italic)
            bold_italic = _add_font_cascade(bold_italic)

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
        x_offset: float = 0.0,
    ) -> None:
        """Render one row of terminal cells at vertical offset *y*."""
        if not cells:
            return
        draw_backgrounds(cells, y, self.cell_width, self.cell_height, theme_colors, x_offset)
        draw_glyphs(cells, y, self.cell_width, self.baseline_offset, self._fonts, theme_colors, x_offset, cell_h=self.cell_height)
        draw_decorations(cells, y, self.cell_width, self.cell_height, self.baseline_offset, theme_colors, x_offset)

    def draw_cursor(
        self,
        context: object,
        row: int,
        col: int,
        style: str,
        color: object,
        x_offset: float = 0.0,
        y_offset: float = 0.0,
    ) -> None:
        """Draw terminal cursor at grid position (row, col)."""
        try:
            import AppKit  # type: ignore[import]
            from AppKit import NSBezierPath  # type: ignore[import]

            x     = x_offset + col * self.cell_width
            row_y = y_offset + row * self.cell_height
            color.set()

            if style == "beam":
                NSBezierPath.fillRect_(AppKit.NSMakeRect(x, row_y, _BEAM_WIDTH, self.cell_height))
            elif style == "underline":
                # Underline at bottom of cell (isFlipped: y increases downward)
                NSBezierPath.fillRect_(AppKit.NSMakeRect(
                    x, row_y + self.cell_height - _DECO_WIDTH * 2, self.cell_width, _DECO_WIDTH * 2
                ))
            else:
                # Block cursor — semi-transparent so text beneath is visible
                from AppKit import NSColor  # type: ignore[import]
                NSColor.colorWithSRGBRed_green_blue_alpha_(
                    color.redComponent(), color.greenComponent(),
                    color.blueComponent(), 0.7
                ).setFill()
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
        x_offset: float = 0.0,
        y_offset: float = 0.0,
    ) -> None:
        """Render IME composing text with background fill and underline at cursor."""
        if not text:
            return
        try:
            import AppKit  # type: ignore[import]
            from AppKit import (  # type: ignore[import]
                NSAttributedString,
                NSBezierPath,
                NSUnderlineStyleAttributeName,
            )

            from termikita.unicode_utils import normalize_text, string_display_width

            # NFC-normalize marked text — IME may send decomposed Vietnamese
            text = normalize_text(text)
            text_width = string_display_width(text)

            x    = x_offset + cursor_col * self.cell_width
            pt_y = y_offset + cursor_row * self.cell_height

            # Fill background behind marked text so it's readable over terminal content
            bg = resolve_color("default", is_fg=False, theme=theme_colors)
            bg.set()
            NSBezierPath.fillRect_(AppKit.NSMakeRect(
                x, pt_y, text_width * self.cell_width, self.cell_height
            ))

            fg   = resolve_color("default", is_fg=True, theme=theme_colors)
            font = self._fonts.get((False, False))
            attrs: dict = {
                AppKit.NSForegroundColorAttributeName: fg,
                NSUnderlineStyleAttributeName: 1,
            }
            if font:
                attrs[AppKit.NSFontAttributeName] = font
            ns_str   = AppKit.NSString.stringWithString_(text)
            attr_str = NSAttributedString.alloc().initWithString_attributes_(ns_str, attrs)
            attr_str.drawAtPoint_(AppKit.NSMakePoint(x, pt_y))
        except Exception:
            pass

    def _calculate_metrics(self) -> None:
        """Derive cell_width, cell_height, baseline_offset from primary font.

        Uses ceiled font metrics (matching Terminal.app behavior) so block
        characters (█▄▀) tile seamlessly without sub-pixel gaps.
        """
        font = self.primary_font
        if font is None:
            return
        try:
            import math
            glyph_id = font.glyphWithName_("M")
            self.cell_width = (
                font.advancementForGlyph_(glyph_id).width
                if glyph_id
                else font.maximumAdvancement().width
            )
            # Ceil individual metrics like NSLayoutManager does for line height
            self.ascender = math.ceil(font.ascender())
            self.descender = math.ceil(abs(font.descender()))
            self.leading = math.ceil(font.leading())
            self.cell_height = (self.ascender + self.descender + self.leading) * _LINE_HEIGHT_MULT
            # baseline_offset = descender: distance from cell BOTTOM to baseline
            # Used by CTLine path (locally-flipped context where y=0 is cell bottom)
            self.baseline_offset = self.descender
        except Exception:
            pass  # retain previous safe defaults


def _add_font_cascade(font: object) -> object:
    """Add system font cascade list so CoreText can find missing glyphs.

    Without this, characters not in the primary font render as '??'.
    The cascade list tells CoreText to try these fonts in order.
    Includes Nerd Font fallbacks for Powerline/devicon glyphs (PUA U+E000-U+F8FF).
    """
    try:
        from CoreText import (  # type: ignore[import]
            CTFontCreateCopyWithAttributes,
            CTFontDescriptorCreateWithNameAndSize,
            kCTFontCascadeListAttribute,
        )
        # Detect installed Nerd Fonts for Powerline/icon glyph coverage
        nerd_descriptors = _find_nerd_font_descriptors()
        cascade = [
            *nerd_descriptors,
            # Symbols, geometric shapes, arrows, dingbats
            CTFontDescriptorCreateWithNameAndSize("Apple Symbols", 0),
            # Emoji support
            CTFontDescriptorCreateWithNameAndSize("Apple Color Emoji", 0),
            # Monospace fallbacks (box drawing, powerline, etc.)
            CTFontDescriptorCreateWithNameAndSize("Menlo", 0),
            CTFontDescriptorCreateWithNameAndSize("Monaco", 0),
            # Broad Unicode coverage (diamonds ◆, bullets ●, arrows ▶)
            CTFontDescriptorCreateWithNameAndSize("Lucida Grande", 0),
            CTFontDescriptorCreateWithNameAndSize("Helvetica Neue", 0),
            # System UI font — widest coverage on macOS
            CTFontDescriptorCreateWithNameAndSize(".AppleSystemUIFont", 0),
        ]
        from CoreText import CTFontDescriptorCreateCopyWithAttributes  # type: ignore[import]
        desc = font.fontDescriptor()
        new_desc = CTFontDescriptorCreateCopyWithAttributes(
            desc, {kCTFontCascadeListAttribute: cascade}
        )
        return CTFontCreateCopyWithAttributes(font, font.pointSize(), None, new_desc)
    except Exception:
        return font


def _find_nerd_font_descriptors() -> list:
    """Detect installed Nerd Fonts and return CTFontDescriptors for cascade.

    Checks for Symbols Nerd Font (icons-only) first, then common full Nerd Fonts.
    Only returns descriptors for fonts actually available on the system.
    """
    try:
        from AppKit import NSFontManager  # type: ignore[import]
        from CoreText import CTFontDescriptorCreateWithNameAndSize  # type: ignore[import]

        fm = NSFontManager.sharedFontManager()
        available = set(fm.availableFontFamilies())
        # Ordered by preference: symbols-only first, then popular full Nerd Fonts
        candidates = [
            "Symbols Nerd Font Mono",
            "Symbols Nerd Font",
            "MesloLGS Nerd Font Mono",
            "MesloLGS NF",
            "Hack Nerd Font Mono",
            "Hack Nerd Font",
            "JetBrainsMono Nerd Font Mono",
            "JetBrainsMono Nerd Font",
            "FiraCode Nerd Font Mono",
            "FiraCode Nerd Font",
        ]
        descriptors = []
        for name in candidates:
            if name in available:
                descriptors.append(CTFontDescriptorCreateWithNameAndSize(name, 0))
                break  # one Nerd Font is enough for PUA coverage
        return descriptors
    except Exception:
        return []


def _safe_convert(fm: object, font: object, trait_mask: int) -> object | None:
    """Apply trait via NSFontManager; return None on failure."""
    try:
        return fm.convertFont_toHaveTrait_(font, trait_mask)  # type: ignore[attr-defined]
    except Exception:
        return None
