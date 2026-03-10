"""Low-level AppKit drawing helpers for terminal cell rendering.

These functions are called by TextRenderer.draw_line() and operate directly
on the current AppKit graphics context. Each helper handles one rendering pass:
  - draw_backgrounds  : Pass 1 — background fill rectangles (batched by color)
  - draw_glyphs       : Pass 2 — foreground text (cached per-cell positioning)
  - draw_decorations  : Pass 3 — underline / strikethrough via NSBezierPath

Performance: draw_glyphs caches NSAttributedString objects per unique
(char, bold, italic, fg, bg, reverse) combination. After the first frame,
zero allocations — only drawAtPoint_ calls at exact grid positions.
"""

from __future__ import annotations

import unicodedata

from termikita.buffer_manager import CellData
from termikita.color_resolver import resolve_cell_colors

# Decoration line stroke width (points)
_DECO_WIDTH = 1.0

# Glyph cache: (char, bold, italic, fg, bg, reverse) -> NSAttributedString
# Cleared on theme change. Max ~4096 entries (covers ASCII × styles × colors).
_GLYPH_CACHE: dict[tuple, object] = {}
_GLYPH_CACHE_MAX = 4096
_GLYPH_CACHE_THEME_ID: int = 0


def _is_wide_char(ch: str) -> bool:
    """Check if character is double-width (CJK, emoji, fullwidth).

    Only checks single codepoints — matches pyte's per-cell buffer model.
    """
    if not ch or len(ch) != 1:
        return False
    return unicodedata.east_asian_width(ch) in ("W", "F")


def invalidate_glyph_cache() -> None:
    """Clear glyph cache (call on theme or font change)."""
    _GLYPH_CACHE.clear()


def draw_backgrounds(
    cells: list[CellData],
    y: float,
    cell_w: float,
    cell_h: float,
    theme: dict,
) -> None:
    """Pass 1: fill background rectangles, batching adjacent same-color cells."""
    try:
        from AppKit import NSBezierPath  # type: ignore[import]
        import AppKit  # type: ignore[import]

        run_start = 0
        run_color = None

        def _flush(end: int) -> None:
            if run_color is not None:
                run_color.set()
                rect = AppKit.NSMakeRect(
                    run_start * cell_w, y,
                    (end - run_start) * cell_w, cell_h,
                )
                NSBezierPath.fillRect_(rect)

        for i, cell in enumerate(cells):
            _, bg = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            if run_color is None:
                run_color = bg
                run_start = i
            elif str(bg) != str(run_color):
                _flush(i)
                run_color = bg
                run_start = i
        _flush(len(cells))
    except Exception:
        pass


def draw_glyphs(
    cells: list[CellData],
    y: float,
    cell_w: float,
    baseline: float,
    fonts: dict[tuple[bool, bool], object],
    theme: dict,
) -> None:
    """Pass 2: draw text glyphs at exact grid positions with cached attr strings.

    Each unique (char, style, color) gets a cached NSAttributedString. After
    first frame, zero ObjC allocations — only drawAtPoint_ per visible cell.
    """
    global _GLYPH_CACHE_THEME_ID

    try:
        from AppKit import NSAttributedString  # type: ignore[import]
        import AppKit  # type: ignore[import]

        # Clear cache on theme change
        theme_id = id(theme)
        if theme_id != _GLYPH_CACHE_THEME_ID:
            _GLYPH_CACHE.clear()
            _GLYPH_CACHE_THEME_ID = theme_id

        skip_next = False
        for i, cell in enumerate(cells):
            if skip_next:
                skip_next = False
                continue
            ch = cell.char
            if not ch or ch == " ":
                continue
            if _is_wide_char(ch):
                skip_next = True

            # Cache lookup — avoids NSString/NSAttributedString allocation
            cache_key = (ch, cell.bold, cell.italic, cell.fg, cell.bg, cell.reverse)
            attr_str = _GLYPH_CACHE.get(cache_key)

            if attr_str is None:
                font = fonts.get((cell.bold, cell.italic)) or fonts.get((False, False))
                fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
                attrs: dict = {AppKit.NSForegroundColorAttributeName: fg}
                if font:
                    attrs[AppKit.NSFontAttributeName] = font
                ns_str = AppKit.NSString.stringWithString_(ch)
                attr_str = NSAttributedString.alloc().initWithString_attributes_(
                    ns_str, attrs
                )
                # Evict all if cache full (simple strategy, refills in 1 frame)
                if len(_GLYPH_CACHE) >= _GLYPH_CACHE_MAX:
                    _GLYPH_CACHE.clear()
                _GLYPH_CACHE[cache_key] = attr_str

            attr_str.drawAtPoint_(AppKit.NSMakePoint(i * cell_w, y + baseline))
    except Exception:
        pass


def draw_decorations(
    cells: list[CellData],
    y: float,
    cell_w: float,
    cell_h: float,
    baseline: float,
    theme: dict,
) -> None:
    """Pass 3: underline and strikethrough rendered as NSBezierPath strokes."""
    try:
        from AppKit import NSBezierPath  # type: ignore[import]
        import AppKit  # type: ignore[import]

        for i, cell in enumerate(cells):
            if not (cell.underline or cell.strikethrough):
                continue
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            fg.set()
            x = i * cell_w
            if cell.underline:
                ul_y = y + baseline - _DECO_WIDTH
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(_DECO_WIDTH)
                path.moveToPoint_(AppKit.NSMakePoint(x, ul_y))
                path.lineToPoint_(AppKit.NSMakePoint(x + cell_w, ul_y))
                path.stroke()
            if cell.strikethrough:
                st_y = y + baseline + (cell_h - baseline) * 0.35
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(_DECO_WIDTH)
                path.moveToPoint_(AppKit.NSMakePoint(x, st_y))
                path.lineToPoint_(AppKit.NSMakePoint(x + cell_w, st_y))
                path.stroke()
    except Exception:
        pass
