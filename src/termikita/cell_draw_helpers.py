"""Low-level AppKit drawing helpers for terminal cell rendering.

These functions are called by TextRenderer.draw_line() and operate directly
on the current AppKit graphics context. Each helper handles one rendering pass:
  - _draw_backgrounds : Pass 1 — background fill rectangles (batched by color)
  - _draw_glyphs      : Pass 2 — foreground text via NSAttributedString
  - _draw_decorations : Pass 3 — underline / strikethrough via NSBezierPath
"""

from __future__ import annotations

from termikita.buffer_manager import CellData
from termikita.color_resolver import resolve_cell_colors

# Decoration line stroke width (points)
_DECO_WIDTH = 1.0


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
    """Pass 2: draw text glyphs using NSAttributedString.drawAtPoint_."""
    try:
        from AppKit import NSAttributedString  # type: ignore[import]
        import AppKit  # type: ignore[import]

        for i, cell in enumerate(cells):
            ch = cell.char
            if not ch or ch == " ":
                continue
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
                # Strikethrough sits at ~35% above the baseline in the ascender zone
                st_y = y + baseline + (cell_h - baseline) * 0.35
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(_DECO_WIDTH)
                path.moveToPoint_(AppKit.NSMakePoint(x, st_y))
                path.lineToPoint_(AppKit.NSMakePoint(x + cell_w, st_y))
                path.stroke()
    except Exception:
        pass
