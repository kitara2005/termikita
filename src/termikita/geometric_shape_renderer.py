"""Geometric shape renderer for common Unicode symbols used in terminal UIs.

Monospace fonts often lack geometric shape glyphs (●, ■, ◆, etc.), causing
CoreText cascade to silently use Apple Symbols (proportional font) which
renders shapes smaller than the monospace cell grid. Drawing them
geometrically ensures consistent sizing matching Terminal.app behavior.

This matches the approach used by kitty and Alacritty for geometric shapes.

Supported characters:
  ● ○ ■ □ ◆ ◇ ▲ ▶ ▼ ◀
"""

from __future__ import annotations

# Codepoints drawn geometrically instead of via font glyphs
GEOMETRIC_SHAPES: set[int] = {
    0x25A0,  # ■ BLACK SQUARE
    0x25A1,  # □ WHITE SQUARE
    0x25B2,  # ▲ BLACK UP-POINTING TRIANGLE
    0x25B6,  # ▶ BLACK RIGHT-POINTING TRIANGLE
    0x25BC,  # ▼ BLACK DOWN-POINTING TRIANGLE
    0x25C0,  # ◀ BLACK LEFT-POINTING TRIANGLE
    0x25C6,  # ◆ BLACK DIAMOND
    0x25C7,  # ◇ WHITE DIAMOND
    0x25CB,  # ○ WHITE CIRCLE
    0x25CF,  # ● BLACK CIRCLE
}


def draw_geometric(cp: int, x: float, y: float, w: float, h: float) -> None:
    """Draw geometric shape as NSBezierPath centered in cell.

    Circles use 60% cell size (smaller, less prominent during spinner updates).
    Other shapes use 80% cell size for visual balance with Terminal.app.
    """
    import AppKit  # type: ignore[import]
    from AppKit import NSBezierPath  # type: ignore[import]

    # 10% padding on each side for visual balance (80% fill)
    pad_x = w * 0.1
    pad_y = h * 0.1
    sx = x + pad_x
    sy = y + pad_y
    sw = w - 2 * pad_x
    sh = h - 2 * pad_y
    cx = x + w / 2
    cy = y + h / 2

    if cp == 0x25CF:  # ● BLACK CIRCLE — 60% cell for subtle spinner/status
        cpad_x = w * 0.2
        cpad_y = h * 0.2
        path = NSBezierPath.bezierPathWithOvalInRect_(
            AppKit.NSMakeRect(x + cpad_x, y + cpad_y, w - 2 * cpad_x, h - 2 * cpad_y)
        )
        path.fill()

    elif cp == 0x25CB:  # ○ WHITE CIRCLE — 60% cell for subtle spinner/status
        cpad_x = w * 0.2
        cpad_y = h * 0.2
        path = NSBezierPath.bezierPathWithOvalInRect_(
            AppKit.NSMakeRect(x + cpad_x, y + cpad_y, w - 2 * cpad_x, h - 2 * cpad_y)
        )
        path.setLineWidth_(1.0)
        path.stroke()

    elif cp == 0x25A0:  # ■ BLACK SQUARE
        NSBezierPath.fillRect_(AppKit.NSMakeRect(sx, sy, sw, sh))

    elif cp == 0x25A1:  # □ WHITE SQUARE
        NSBezierPath.strokeRect_(AppKit.NSMakeRect(sx, sy, sw, sh))

    elif cp == 0x25C6:  # ◆ BLACK DIAMOND
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(cx, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, cy))
        path.lineToPoint_(AppKit.NSMakePoint(cx, sy + sh))
        path.lineToPoint_(AppKit.NSMakePoint(sx, cy))
        path.closePath()
        path.fill()

    elif cp == 0x25C7:  # ◇ WHITE DIAMOND
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(cx, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, cy))
        path.lineToPoint_(AppKit.NSMakePoint(cx, sy + sh))
        path.lineToPoint_(AppKit.NSMakePoint(sx, cy))
        path.closePath()
        path.setLineWidth_(1.0)
        path.stroke()

    elif cp == 0x25B2:  # ▲ BLACK UP-POINTING TRIANGLE
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(cx, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, sy + sh))
        path.lineToPoint_(AppKit.NSMakePoint(sx, sy + sh))
        path.closePath()
        path.fill()

    elif cp == 0x25BC:  # ▼ BLACK DOWN-POINTING TRIANGLE
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(sx, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, sy))
        path.lineToPoint_(AppKit.NSMakePoint(cx, sy + sh))
        path.closePath()
        path.fill()

    elif cp == 0x25B6:  # ▶ BLACK RIGHT-POINTING TRIANGLE
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(sx, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, cy))
        path.lineToPoint_(AppKit.NSMakePoint(sx, sy + sh))
        path.closePath()
        path.fill()

    elif cp == 0x25C0:  # ◀ BLACK LEFT-POINTING TRIANGLE
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(AppKit.NSMakePoint(sx + sw, sy))
        path.lineToPoint_(AppKit.NSMakePoint(sx + sw, sy + sh))
        path.lineToPoint_(AppKit.NSMakePoint(sx, cy))
        path.closePath()
        path.fill()
