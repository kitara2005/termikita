"""Low-level AppKit drawing helpers for terminal cell rendering.

These functions are called by TextRenderer.draw_line() and operate directly
on the current AppKit graphics context. Each helper handles one rendering pass:
  - draw_backgrounds  : Pass 1 — background fill rectangles (batched by color)
  - draw_glyphs       : Pass 2 — foreground text via CTLine runs
  - draw_decorations  : Pass 3 — underline / strikethrough via NSBezierPath

Performance: draw_glyphs groups consecutive same-style cells into runs and
renders each as a CTLine. Falls back to per-cell NSAttributedString if
CTLine rendering is disabled.
"""

from __future__ import annotations

import unicodedata

from termikita.buffer_manager import CellData
from termikita.color_resolver import resolve_cell_colors
from termikita.block_element_renderer import is_drawable_element, draw_block_elements

# Decoration line stroke width (points)
_DECO_WIDTH = 1.0

# Toggle: set False to revert to per-cell rendering for debugging
_USE_CTLINE_RENDERING = True

# Per-cell glyph cache (fallback): (char, bold, italic, fg, bg, reverse) -> NSAttributedString
_GLYPH_CACHE: dict[tuple, object] = {}
_GLYPH_CACHE_MAX = 4096
_GLYPH_CACHE_THEME_ID: int = 0


def _is_wide_char(ch: str) -> bool:
    """Check if character is double-width (CJK, emoji, fullwidth)."""
    if not ch or len(ch) != 1:
        return False
    return unicodedata.east_asian_width(ch) in ("W", "F")


def _is_pua_char(ch: str) -> bool:
    """Check if character is in Private Use Area (Powerline, Nerd Font icons).

    PUA chars need isolation in CTLine runs — if no Nerd Font installed,
    CoreText renders ?? at wrong width, breaking grid alignment for the run.
    """
    if not ch or len(ch) != 1:
        return False
    cp = ord(ch)
    # BMP PUA (U+E000-U+F8FF) covers Powerline, Nerd Font, devicons
    # Supplementary PUA-A/B (U+F0000-U+10FFFF) for extended icon sets
    return (0xE000 <= cp <= 0xF8FF) or (0xF0000 <= cp <= 0x10FFFF)


# Cache: PUA codepoint -> (resolved_char, fallback_font_or_None)
_PUA_RESOLVE_CACHE: dict[str, tuple[str, object]] = {}


def _resolve_pua_char(ch: str, primary_font: object) -> tuple[str, object]:
    """Find a font that can render PUA char, or substitute with space.

    Uses CTFontCreateForString to search all system fonts (not just cascade).
    Returns (char_to_render, font_to_use). If no font has the glyph,
    returns (" ", primary_font) to avoid ugly ?? replacement glyphs.
    """
    cached = _PUA_RESOLVE_CACHE.get(ch)
    if cached is not None:
        return cached

    try:
        from CoreText import CTFontCreateForString  # type: ignore[import]
        from CoreFoundation import CFRangeMake  # type: ignore[import]

        fallback = CTFontCreateForString(primary_font, ch, CFRangeMake(0, len(ch)))
        if fallback and fallback.fontName() != primary_font.fontName():
            # A different font can render this glyph
            result = (ch, fallback)
        else:
            # No font covers this PUA char — render space instead of ??
            result = (" ", primary_font)
    except Exception:
        result = (" ", primary_font)

    _PUA_RESOLVE_CACHE[ch] = result
    return result


def invalidate_glyph_cache() -> None:
    """Clear glyph cache (call on theme or font change)."""
    _GLYPH_CACHE.clear()
    _PUA_RESOLVE_CACHE.clear()


def draw_backgrounds(
    cells: list[CellData],
    y: float,
    cell_w: float,
    cell_h: float,
    theme: dict,
    x_offset: float = 0.0,
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
                    x_offset + run_start * cell_w, y,
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
    x_offset: float = 0.0,
    cell_h: float = 0.0,
) -> None:
    """Pass 2: draw block elements geometrically, then text glyphs via CTLine."""
    # Draw block/box chars as rectangles/lines (pixel-perfect, no AA gaps)
    drawn_indices = draw_block_elements(cells, y, cell_w, cell_h, theme, x_offset) if cell_h > 0 else set()
    if _USE_CTLINE_RENDERING and cell_h > 0:
        _draw_glyphs_ctline(cells, y, cell_w, cell_h, baseline, fonts, theme, x_offset, drawn_indices)
    else:
        _draw_glyphs_percell(cells, y, cell_w, baseline, fonts, theme, x_offset)


def _draw_glyphs_ctline(
    cells: list[CellData],
    y: float,
    cell_w: float,
    cell_h: float,
    baseline: float,
    fonts: dict[tuple[bool, bool], object],
    theme: dict,
    x_offset: float,
    skip_indices: set[int] | None = None,
) -> None:
    """Draw text using CTLine per style-run for smooth anti-aliasing.

    Groups consecutive same-style cells into runs. Each run becomes one CTLine
    drawn via CTLineDraw. The flipped coordinate system is handled by
    translating to the row bottom and flipping y once per row.
    """
    try:
        from AppKit import NSAttributedString, NSGraphicsContext  # type: ignore[import]
        import AppKit  # type: ignore[import]
        from CoreText import CTLineCreateWithAttributedString, CTLineDraw  # type: ignore[import]
        import Quartz  # type: ignore[import]

        ctx = NSGraphicsContext.currentContext()
        if ctx is None:
            return
        cgctx = ctx.CGContext()

        # Flip coordinate system once for the entire row:
        # translate origin to bottom of cell row, then flip y
        Quartz.CGContextSaveGState(cgctx)
        Quartz.CGContextTranslateCTM(cgctx, 0, y + cell_h)
        Quartz.CGContextScaleCTM(cgctx, 1.0, -1.0)

        # Group cells into style runs, skipping block elements already drawn
        runs = _group_into_style_runs(cells, skip_indices)
        for start_col, end_col, style_key in runs:
            # Collect characters for this run
            chars = []
            col = start_col
            while col < end_col:
                ch = cells[col].char
                chars.append(ch if ch else " ")
                if _is_wide_char(ch):
                    col += 2  # skip shadow cell
                else:
                    col += 1
            run_text = "".join(chars)

            # Resolve font and color from style
            bold, italic, fg_key, bg_key, reverse = style_key
            font = fonts.get((bold, italic)) or fonts.get((False, False))
            fg, _ = resolve_cell_colors(fg_key, bg_key, reverse, theme)
            attrs: dict = {AppKit.NSForegroundColorAttributeName: fg}
            if font:
                attrs[AppKit.NSFontAttributeName] = font

            # Create CTLine and draw at grid position
            attr_str = NSAttributedString.alloc().initWithString_attributes_(
                run_text, attrs
            )
            ct_line = CTLineCreateWithAttributedString(attr_str)
            run_x = x_offset + start_col * cell_w
            # In the flipped context: y=0 is row bottom, baseline is up from bottom
            Quartz.CGContextSetTextPosition(cgctx, run_x, baseline)
            CTLineDraw(ct_line, cgctx)

        Quartz.CGContextRestoreGState(cgctx)
    except Exception:
        # Fallback to per-cell on any error
        _draw_glyphs_percell(cells, y, cell_w, baseline, fonts, theme, x_offset)


def _group_into_style_runs(
    cells: list[CellData],
    skip_indices: set[int] | None = None,
) -> list[tuple[int, int, tuple]]:
    """Group consecutive cells with same style into runs.

    Returns list of (start_col, end_col, style_key) tuples.
    Breaks runs at: style changes, empty/space cells, wide characters,
    and indices already drawn by block element renderer.
    """
    runs: list[tuple[int, int, tuple]] = []
    n = len(cells)
    i = 0

    while i < n:
        # Skip cells already drawn as block elements
        if skip_indices and i in skip_indices:
            i += 1
            continue
        cell = cells[i]
        ch = cell.char
        # Skip empty/space cells
        if not ch or ch == " ":
            i += 1
            continue

        style = (cell.bold, cell.italic, cell.fg, cell.bg, cell.reverse)

        # Wide chars: isolate into single-cell run
        if _is_wide_char(ch):
            runs.append((i, i + 1, style))
            i += 2  # skip shadow cell
            continue

        # Start a run of regular chars with same style
        run_start = i
        i += 1
        while i < n:
            if skip_indices and i in skip_indices:
                break
            nc = cells[i]
            nch = nc.char
            # Break on empty/space
            if not nch or nch == " ":
                break
            # Break on wide char
            if _is_wide_char(nch):
                break
            # Break on style change
            ns = (nc.bold, nc.italic, nc.fg, nc.bg, nc.reverse)
            if ns != style:
                break
            i += 1

        runs.append((run_start, i, style))

    return runs


def _draw_glyphs_percell(
    cells: list[CellData],
    y: float,
    cell_w: float,
    baseline: float,
    fonts: dict[tuple[bool, bool], object],
    theme: dict,
    x_offset: float,
) -> None:
    """Fallback: draw text per-cell with cached NSAttributedString objects.

    In flipped view (isFlipped=YES), drawAtPoint_ uses the point as the
    text layout origin (top-left). We offset by leading so text fills the
    cell correctly: ascender at top, descender at bottom.
    """
    global _GLYPH_CACHE_THEME_ID

    try:
        from AppKit import NSAttributedString  # type: ignore[import]
        import AppKit  # type: ignore[import]

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

            cache_key = (ch, cell.bold, cell.italic, cell.fg, cell.bg, cell.reverse)
            attr_str = _GLYPH_CACHE.get(cache_key)

            if attr_str is None:
                font = fonts.get((cell.bold, cell.italic)) or fonts.get((False, False))
                fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
                attrs: dict = {AppKit.NSForegroundColorAttributeName: fg}
                if font:
                    attrs[AppKit.NSFontAttributeName] = font
                attr_str = NSAttributedString.alloc().initWithString_attributes_(
                    ch, attrs
                )
                if len(_GLYPH_CACHE) >= _GLYPH_CACHE_MAX:
                    _GLYPH_CACHE.clear()
                _GLYPH_CACHE[cache_key] = attr_str

            # In flipped view, drawAtPoint_ y = top of text layout area.
            # Use y (cell top) so ascender starts at cell top, matching CTLine path.
            attr_str.drawAtPoint_(
                AppKit.NSMakePoint(x_offset + i * cell_w, y)
            )
    except Exception:
        pass


def draw_decorations(
    cells: list[CellData],
    y: float,
    cell_w: float,
    cell_h: float,
    baseline: float,
    theme: dict,
    x_offset: float = 0.0,
) -> None:
    """Pass 3: underline and strikethrough in flipped view coordinates.

    In flipped view (y=0 top): baseline_offset = descender (from cell bottom).
    Baseline screen position = y + cell_h - baseline (from cell top).
    Underline: just below baseline. Strikethrough: ~mid-height of x-height.
    """
    try:
        from AppKit import NSBezierPath  # type: ignore[import]
        import AppKit  # type: ignore[import]

        # baseline_offset = descender (distance from cell bottom to baseline)
        # In flipped coords: baseline_y = y + (cell_h - baseline)
        baseline_y = y + cell_h - baseline

        for i, cell in enumerate(cells):
            if not (cell.underline or cell.strikethrough):
                continue
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            fg.set()
            x = x_offset + i * cell_w
            if cell.underline:
                # Underline just below baseline (1pt below in flipped = +1)
                ul_y = baseline_y + _DECO_WIDTH
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(_DECO_WIDTH)
                path.moveToPoint_(AppKit.NSMakePoint(x, ul_y))
                path.lineToPoint_(AppKit.NSMakePoint(x + cell_w, ul_y))
                path.stroke()
            if cell.strikethrough:
                # Strikethrough at approximately x-height center
                # x-height is roughly 55% of ascender, from baseline upward (= -y in flipped)
                ascender = cell_h - baseline  # ascender + leading
                st_y = y + ascender * 0.55
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(_DECO_WIDTH)
                path.moveToPoint_(AppKit.NSMakePoint(x, st_y))
                path.lineToPoint_(AppKit.NSMakePoint(x + cell_w, st_y))
                path.stroke()
    except Exception:
        pass
