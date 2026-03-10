"""Low-level AppKit drawing helpers for terminal cell rendering.

These functions are called by TextRenderer.draw_line() and operate directly
on the current AppKit graphics context. Each helper handles one rendering pass:
  - draw_backgrounds  : Pass 1 — background fill rectangles (batched by color)
  - draw_glyphs       : Pass 2 — foreground text (batched NSMutableAttributedString)
  - draw_decorations  : Pass 3 — underline / strikethrough via NSBezierPath

Performance: draw_glyphs builds ONE attributed string per row with attribute
ranges, then issues a single drawAtPoint_ call. This reduces ObjC bridge
overhead from ~80 calls/row to ~10 calls/row.
"""

from __future__ import annotations

import unicodedata

from termikita.buffer_manager import CellData
from termikita.color_resolver import resolve_cell_colors

# Decoration line stroke width (points)
_DECO_WIDTH = 1.0


def _is_wide_char(ch: str) -> bool:
    """Check if character is double-width (CJK, emoji, fullwidth).

    Only checks single codepoints — matches pyte's per-cell buffer model.
    """
    if not ch or len(ch) != 1:
        return False
    return unicodedata.east_asian_width(ch) in ("W", "F")


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
    """Pass 2: draw row text as a single NSMutableAttributedString.

    Fast path: builds one attributed string for the row with attribute ranges,
    then draws with a single drawAtPoint_ call. Falls back to per-cell for
    rows containing wide chars (emoji/CJK) where font fallback may shift advances.
    """
    has_wide = any(_is_wide_char(c.char) for c in cells if c.char)
    if has_wide:
        _draw_glyphs_percell(cells, y, cell_w, baseline, fonts, theme)
    else:
        _draw_glyphs_batched(cells, y, cell_w, baseline, fonts, theme)


def _draw_glyphs_batched(
    cells: list[CellData], y: float, cell_w: float,
    baseline: float, fonts: dict, theme: dict,
) -> None:
    """Fast path: one NSMutableAttributedString per row, one draw call."""
    try:
        from AppKit import NSMutableAttributedString  # type: ignore[import]
        import AppKit  # type: ignore[import]
        from Foundation import NSMakeRange  # type: ignore[import]

        # Build row text (spaces for empty cells to maintain cell positioning)
        row_text = "".join(c.char if c.char else " " for c in cells)
        if not row_text.strip():
            return

        ns_str = AppKit.NSString.stringWithString_(row_text)
        attr_str = NSMutableAttributedString.alloc().initWithString_(ns_str)

        # Apply attributes in contiguous runs (same bold/italic/fg/bg/reverse)
        i, n = 0, len(cells)
        while i < n:
            cell = cells[i]
            key = (cell.bold, cell.italic, cell.fg, cell.bg, cell.reverse)
            # Find end of same-attribute run
            j = i + 1
            while j < n:
                c2 = cells[j]
                if (c2.bold, c2.italic, c2.fg, c2.bg, c2.reverse) != key:
                    break
                j += 1
            # Resolve color and font once per run
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            font = fonts.get((cell.bold, cell.italic)) or fonts.get((False, False))
            attrs: dict = {AppKit.NSForegroundColorAttributeName: fg}
            if font:
                attrs[AppKit.NSFontAttributeName] = font
            attr_str.setAttributes_range_(attrs, NSMakeRange(i, j - i))
            i = j

        # Single draw call for entire row
        attr_str.drawAtPoint_(AppKit.NSMakePoint(0, y + baseline))
    except Exception:
        pass


def _draw_glyphs_percell(
    cells: list[CellData], y: float, cell_w: float,
    baseline: float, fonts: dict, theme: dict,
) -> None:
    """Slow path: per-cell drawing for rows with wide chars (emoji/CJK)."""
    try:
        from AppKit import NSAttributedString  # type: ignore[import]
        import AppKit  # type: ignore[import]

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
            font = fonts.get((cell.bold, cell.italic)) or fonts.get((False, False))
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            attrs: dict = {AppKit.NSForegroundColorAttributeName: fg}
            if font:
                attrs[AppKit.NSFontAttributeName] = font
            ns_str = AppKit.NSString.stringWithString_(ch)
            attr_str = NSAttributedString.alloc().initWithString_attributes_(ns_str, attrs)
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
