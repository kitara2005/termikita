"""Custom geometric renderer for Unicode block elements, box drawing, and shapes.

Instead of rendering these as font glyphs (which leave gaps between cells or
use wrong metrics from proportional fallback fonts), draws them as filled
rectangles, circles, and paths for pixel-perfect rendering.
This matches the approach used by kitty, Alacritty, and iTerm2.

Supported ranges:
- Block Elements: U+2580–U+259F (▀▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐░▒▓)
- Box Drawing: U+2500–U+257F (─│┌┐└┘├┤┬┴┼ etc.)
- Geometric Shapes: ● ○ ■ □ ◆ ◇ ▲ ▶ ▼ ◀ (common terminal UI symbols)
"""

from __future__ import annotations

from termikita.geometric_shape_renderer import GEOMETRIC_SHAPES, draw_geometric

# Block element character range
_BLOCK_START = 0x2580
_BLOCK_END = 0x259F

# Box drawing character range
_BOX_START = 0x2500
_BOX_END = 0x257F

# Line width for box drawing (in points)
_BOX_LINE_WIDTH = 1.0


def is_drawable_element(ch: str) -> bool:
    """Check if character should be drawn geometrically instead of as a glyph."""
    if not ch or len(ch) != 1:
        return False
    cp = ord(ch)
    return (
        (_BLOCK_START <= cp <= _BLOCK_END)
        or (_BOX_START <= cp <= _BOX_END)
        or cp in GEOMETRIC_SHAPES
    )


def draw_block_elements(
    cells: list,
    y: float,
    cell_w: float,
    cell_h: float,
    theme: dict,
    x_offset: float = 0.0,
) -> set[int]:
    """Draw block elements and box drawing chars as geometric shapes.

    Returns set of cell indices that were drawn (so CTLine pass can skip them).
    """
    try:
        from termikita.color_resolver import resolve_cell_colors
    except ImportError:
        return set()

    drawn: set[int] = set()

    for i, cell in enumerate(cells):
        ch = cell.char
        if not ch or len(ch) != 1:
            continue
        cp = ord(ch)

        if _BLOCK_START <= cp <= _BLOCK_END:
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            fg.set()
            x = x_offset + i * cell_w
            _draw_block(cp, x, y, cell_w, cell_h)
            drawn.add(i)

        elif _BOX_START <= cp <= _BOX_END:
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            fg.set()
            x = x_offset + i * cell_w
            _draw_box(cp, x, y, cell_w, cell_h)
            drawn.add(i)

        elif cp in GEOMETRIC_SHAPES:
            fg, _ = resolve_cell_colors(cell.fg, cell.bg, cell.reverse, theme)
            fg.set()
            x = x_offset + i * cell_w
            draw_geometric(cp, x, y, cell_w, cell_h)
            drawn.add(i)

    return drawn


def _draw_block(cp: int, x: float, y: float, w: float, h: float) -> None:
    """Draw a block element character as a filled rectangle."""
    import AppKit  # type: ignore[import]
    from AppKit import NSBezierPath  # type: ignore[import]

    if cp == 0x2588:  # █ FULL BLOCK
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, w, h))
    elif cp == 0x2580:  # ▀ UPPER HALF
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, w, h / 2))
    elif cp == 0x2584:  # ▄ LOWER HALF
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y + h / 2, w, h / 2))
    elif cp == 0x258C:  # ▌ LEFT HALF
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, w / 2, h))
    elif cp == 0x2590:  # ▐ RIGHT HALF
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x + w / 2, y, w / 2, h))
    # Lower 1/8 to 7/8 blocks (▁▂▃▄▅▆▇)
    elif 0x2581 <= cp <= 0x2587:
        frac = (cp - 0x2580) / 8.0
        bh = h * frac
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y + h - bh, w, bh))
    # Left 7/8 to 1/8 blocks (▉▊▋▌▍▎▏)
    elif 0x2589 <= cp <= 0x258F:
        frac = (0x2590 - cp) / 8.0
        bw = w * frac
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, bw, h))
    # Shade characters (░▒▓) — draw as semi-transparent fill
    elif cp == 0x2591:  # ░ LIGHT SHADE
        _draw_shade(x, y, w, h, 0.25)
    elif cp == 0x2592:  # ▒ MEDIUM SHADE
        _draw_shade(x, y, w, h, 0.50)
    elif cp == 0x2593:  # ▓ DARK SHADE
        _draw_shade(x, y, w, h, 0.75)
    # Quadrant block elements (▖▗▘▙▚▛▜▝▞▟)
    elif 0x2596 <= cp <= 0x259F:
        _draw_quadrant(cp, x, y, w, h)


def _draw_shade(x: float, y: float, w: float, h: float, alpha: float) -> None:
    """Draw a shade character as semi-transparent fill over cell."""
    import AppKit  # type: ignore[import]
    from AppKit import NSBezierPath, NSColor, NSGraphicsContext  # type: ignore[import]

    ctx = NSGraphicsContext.currentContext()
    if ctx is None:
        return
    # Apply alpha to current fill color for semi-transparent shade effect
    ctx.saveGraphicsState()
    NSColor.colorWithCalibratedWhite_alpha_(1.0, alpha).set()
    NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, w, h))
    ctx.restoreGraphicsState()


def _draw_quadrant(cp: int, x: float, y: float, w: float, h: float) -> None:
    """Draw quadrant block elements (U+2596–U+259F)."""
    import AppKit  # type: ignore[import]
    from AppKit import NSBezierPath  # type: ignore[import]

    hw, hh = w / 2, h / 2
    # Quadrant positions: TL, TR, BL, BR
    # Each codepoint encodes which quadrants are filled
    quads = {
        0x2596: (False, False, True, False),   # ▖ lower left
        0x2597: (False, False, False, True),   # ▗ lower right
        0x2598: (True, False, False, False),   # ▘ upper left
        0x2599: (True, False, True, True),     # ▙ upper left + lower
        0x259A: (True, False, False, True),    # ▚ upper left + lower right
        0x259B: (True, True, True, False),     # ▛ upper + lower left
        0x259C: (True, True, False, True),     # ▜ upper + lower right
        0x259D: (False, True, False, False),   # ▝ upper right
        0x259E: (False, True, True, False),    # ▞ upper right + lower left
        0x259F: (False, True, True, True),     # ▟ upper right + lower
    }
    tl, tr, bl, br = quads.get(cp, (False, False, False, False))
    if tl:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y, hw, hh))
    if tr:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x + hw, y, hw, hh))
    if bl:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, y + hh, hw, hh))
    if br:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x + hw, y + hh, hw, hh))


def _draw_box(cp: int, x: float, y: float, w: float, h: float) -> None:
    """Draw box drawing character as filled rectangles for pixel-perfect tiling.

    Uses filled rects instead of stroked paths — stroked lines leave sub-pixel
    gaps between adjacent cells. Filled rects tile seamlessly because each cell's
    rectangle spans its full width/height with no fractional edge issues.
    """
    import AppKit  # type: ignore[import]
    from AppKit import NSBezierPath, NSGraphicsContext  # type: ignore[import]
    from Quartz import CGContextSetShouldAntialias  # type: ignore[import]

    segments = _BOX_SEGMENTS.get(cp)
    if segments is None:
        return

    # Disable anti-aliasing for sharp box drawing lines
    ctx = NSGraphicsContext.currentContext()
    if ctx:
        cgctx = ctx.CGContext()
        CGContextSetShouldAntialias(cgctx, False)

    import math
    lw = _BOX_LINE_WIDTH
    # Center of cell, snapped to pixel grid
    cx = math.floor(x + w / 2)
    cy = math.floor(y + h / 2)

    right, left, down, up = segments

    # Horizontal segments: filled rect spanning full cell width at center y
    if right and left:
        # Full horizontal line — single rect spans entire cell width
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, cy, w, lw))
    elif right:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(cx, cy, x + w - cx, lw))
    elif left:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(x, cy, cx + lw - x, lw))

    # Vertical segments: filled rect spanning full cell height at center x
    if down and up:
        # Full vertical line — single rect spans entire cell height
        NSBezierPath.fillRect_(AppKit.NSMakeRect(cx, y, lw, h))
    elif down:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(cx, cy, lw, y + h - cy))
    elif up:
        NSBezierPath.fillRect_(AppKit.NSMakeRect(cx, y, lw, cy + lw - y))

    # Re-enable anti-aliasing for subsequent text rendering
    if ctx:
        CGContextSetShouldAntialias(cgctx, True)


# Box drawing segment lookup: (right, left, down, up)
# True = draw line from center to that edge
_BOX_SEGMENTS: dict[int, tuple[bool, bool, bool, bool]] = {
    0x2500: (True, True, False, False),    # ─ horizontal
    0x2501: (True, True, False, False),    # ━ heavy horizontal
    0x2502: (False, False, True, True),    # │ vertical
    0x2503: (False, False, True, True),    # ┃ heavy vertical
    0x250C: (True, False, True, False),    # ┌ down-right
    0x250D: (True, False, True, False),    # ┍
    0x250E: (True, False, True, False),    # ┎
    0x250F: (True, False, True, False),    # ┏
    0x2510: (False, True, True, False),    # ┐ down-left
    0x2511: (False, True, True, False),    # ┑
    0x2512: (False, True, True, False),    # ┒
    0x2513: (False, True, True, False),    # ┓
    0x2514: (True, False, False, True),    # └ up-right
    0x2515: (True, False, False, True),    # ┕
    0x2516: (True, False, False, True),    # ┖
    0x2517: (True, False, False, True),    # ┗
    0x2518: (False, True, False, True),    # ┘ up-left
    0x2519: (False, True, False, True),    # ┙
    0x251A: (False, True, False, True),    # ┚
    0x251B: (False, True, False, True),    # ┛
    0x251C: (True, False, True, True),     # ├ vertical-right
    0x251D: (True, False, True, True),     # ┝
    0x251E: (True, False, True, True),     # ┞
    0x251F: (True, False, True, True),     # ┟
    0x2520: (True, False, True, True),     # ┠
    0x2521: (True, False, True, True),     # ┡
    0x2522: (True, False, True, True),     # ┢
    0x2523: (True, False, True, True),     # ┣
    0x2524: (False, True, True, True),     # ┤ vertical-left
    0x2525: (False, True, True, True),     # ┥
    0x2526: (False, True, True, True),     # ┦
    0x2527: (False, True, True, True),     # ┧
    0x2528: (False, True, True, True),     # ┨
    0x2529: (False, True, True, True),     # ┩
    0x252A: (False, True, True, True),     # ┪
    0x252B: (False, True, True, True),     # ┫
    0x252C: (True, True, True, False),     # ┬ horizontal-down
    0x252D: (True, True, True, False),     # ┭
    0x252E: (True, True, True, False),     # ┮
    0x252F: (True, True, True, False),     # ┯
    0x2530: (True, True, True, False),     # ┰
    0x2531: (True, True, True, False),     # ┱
    0x2532: (True, True, True, False),     # ┲
    0x2533: (True, True, True, False),     # ┳
    0x2534: (True, True, False, True),     # ┴ horizontal-up
    0x2535: (True, True, False, True),     # ┵
    0x2536: (True, True, False, True),     # ┶
    0x2537: (True, True, False, True),     # ┷
    0x2538: (True, True, False, True),     # ┸
    0x2539: (True, True, False, True),     # ┹
    0x253A: (True, True, False, True),     # ┺
    0x253B: (True, True, False, True),     # ┻
    0x253C: (True, True, True, True),      # ┼ cross
    0x253D: (True, True, True, True),      # ┽
    0x253E: (True, True, True, True),      # ┾
    0x253F: (True, True, True, True),      # ┿
    0x2540: (True, True, True, True),      # ╀
    0x2541: (True, True, True, True),      # ╁
    0x2542: (True, True, True, True),      # ╂
    0x2543: (True, True, True, True),      # ╃
    0x2544: (True, True, True, True),      # ╄
    0x2545: (True, True, True, True),      # ╅
    0x2546: (True, True, True, True),      # ╆
    0x2547: (True, True, True, True),      # ╇
    0x2548: (True, True, True, True),      # ╈
    0x2549: (True, True, True, True),      # ╉
    0x254A: (True, True, True, True),      # ╊
    0x254B: (True, True, True, True),      # ╋
    # Dashed lines (treat as solid segments)
    0x254C: (True, True, False, False),    # ╌
    0x254D: (True, True, False, False),    # ╍
    0x254E: (False, False, True, True),    # ╎
    0x254F: (False, False, True, True),    # ╏
    # Double lines (draw as single for now)
    0x2550: (True, True, False, False),    # ═
    0x2551: (False, False, True, True),    # ║
    0x2552: (True, False, True, False),    # ╒
    0x2553: (True, False, True, False),    # ╓
    0x2554: (True, False, True, False),    # ╔
    0x2555: (False, True, True, False),    # ╕
    0x2556: (False, True, True, False),    # ╖
    0x2557: (False, True, True, False),    # ╗
    0x2558: (True, False, False, True),    # ╘
    0x2559: (True, False, False, True),    # ╙
    0x255A: (True, False, False, True),    # ╚
    0x255B: (False, True, False, True),    # ╛
    0x255C: (False, True, False, True),    # ╜
    0x255D: (False, True, False, True),    # ╝
    0x255E: (True, False, True, True),     # ╞
    0x255F: (True, False, True, True),     # ╟
    0x2560: (True, False, True, True),     # ╠
    0x2561: (False, True, True, True),     # ╡
    0x2562: (False, True, True, True),     # ╢
    0x2563: (False, True, True, True),     # ╣
    0x2564: (True, True, True, False),     # ╤
    0x2565: (True, True, True, False),     # ╥
    0x2566: (True, True, True, False),     # ╦
    0x2567: (True, True, False, True),     # ╧
    0x2568: (True, True, False, True),     # ╨
    0x2569: (True, True, False, True),     # ╩
    0x256A: (True, True, True, True),      # ╪
    0x256B: (True, True, True, True),      # ╫
    0x256C: (True, True, True, True),      # ╬
    # Rounded corners
    0x256D: (True, False, True, False),    # ╭
    0x256E: (False, True, True, False),    # ╮
    0x256F: (False, True, False, True),    # ╯
    0x2570: (True, False, False, True),    # ╰
    # Diagonal lines (skip for now)
    # Light/heavy arcs
    0x2574: (False, True, False, False),   # ╴ light left
    0x2575: (False, False, False, True),   # ╵ light up
    0x2576: (True, False, False, False),   # ╶ light right
    0x2577: (False, False, True, False),   # ╷ light down
    0x2578: (False, True, False, False),   # ╸ heavy left
    0x2579: (False, False, False, True),   # ╹ heavy up
    0x257A: (True, False, False, False),   # ╺ heavy right
    0x257B: (False, False, True, False),   # ╻ heavy down
}
