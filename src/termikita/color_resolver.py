"""Color resolution for the terminal renderer.

Converts the heterogeneous color values stored in CellData (strings, ints,
tuples) to NSColor objects, applying theme defaults and reverse-video logic.
"""

from __future__ import annotations

from termikita.color_utils import ansi_256_to_rgb, rgb_to_nscolor

# Mapping from ANSI color name -> palette index (0-15)
ANSI_NAMES: dict[str, int] = {
    "black": 0,       "red": 1,         "green": 2,       "yellow": 3,
    "blue": 4,        "magenta": 5,     "cyan": 6,        "white": 7,
    "brightblack": 8, "brightred": 9,   "brightgreen": 10, "brightyellow": 11,
    "brightblue": 12, "brightmagenta": 13, "brightcyan": 14, "brightwhite": 15,
}


def resolve_color(
    color: str | int | tuple[int, int, int] | None,
    is_fg: bool,
    theme: dict,
) -> object:
    """Convert a CellData color value to an NSColor.

    Args:
        color:   Raw color from CellData.fg or CellData.bg.
                 May be "default", an ANSI name string, an int (256-color index),
                 or an (r, g, b) tuple.
        is_fg:   True when resolving foreground color (affects "default" lookup).
        theme:   Theme dict with keys "foreground", "background", "ansi" (list of
                 16 rgb tuples), "cursor", "selection".

    Returns:
        NSColor object ready for use in AppKit drawing calls.
    """
    rgb = _to_rgb(color, is_fg, theme)
    return rgb_to_nscolor(*rgb)


def resolve_cell_colors(
    fg_raw: str | int | tuple,
    bg_raw: str | int | tuple,
    reverse: bool,
    theme: dict,
) -> tuple[object, object]:
    """Return (fg_nscolor, bg_nscolor) with reverse-video applied.

    Args:
        fg_raw:  Raw foreground value from CellData.
        bg_raw:  Raw background value from CellData.
        reverse: CellData.reverse flag — swaps fg and bg when True.
        theme:   Theme color dict.

    Returns:
        (fg_NSColor, bg_NSColor) pair.
    """
    # Resolve colors FIRST, then swap for reverse video.
    # Swapping raw "default"/"default" strings before resolving has no effect
    # because resolve_color("default", is_fg=True) always returns theme foreground.
    # By resolving first, reverse video correctly shows fg-as-bg and bg-as-fg.
    fg_color = resolve_color(fg_raw, is_fg=True, theme=theme)
    bg_color = resolve_color(bg_raw, is_fg=False, theme=theme)
    if reverse:
        return bg_color, fg_color
    return fg_color, bg_color


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_rgb(
    color: str | int | tuple[int, int, int] | None,
    is_fg: bool,
    theme: dict,
) -> tuple[int, int, int]:
    """Convert any color representation to an (r, g, b) tuple."""
    # Direct RGB tuple — pass through unchanged
    if isinstance(color, tuple):
        return color  # type: ignore[return-value]

    # Integer: 256-color palette index
    if isinstance(color, int):
        return ansi_256_to_rgb(color)

    # String cases
    if not color or color == "default":
        key = "foreground" if is_fg else "background"
        return theme.get(key, (255, 255, 255) if is_fg else (0, 0, 0))

    # Named ANSI color ("red", "brightblue", etc.)
    lower = color.lower()
    if lower in ANSI_NAMES:
        idx = ANSI_NAMES[lower]
        ansi_palette: list[tuple[int, int, int]] = theme.get("ansi", [])
        if idx < len(ansi_palette):
            return ansi_palette[idx]
        return ansi_256_to_rgb(idx)

    # 24-bit "R;G;B" format from pyte (SGR 38;2;R;G;B / SGR 48;2;R;G;B)
    if ";" in color:
        try:
            parts = color.split(";")
            if len(parts) == 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass

    # Numeric string from pyte 256-color (SGR 38;5;N) — some pyte versions
    # store the index as a string instead of an integer
    if color.isdigit():
        return ansi_256_to_rgb(int(color))

    # Hex string fallback ("#RRGGBB" or "RRGGBB")
    if color.startswith("#") or (len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color)):
        try:
            from termikita.color_utils import hex_to_rgb
            return hex_to_rgb(color)
        except Exception:
            pass

    # Unknown — fall back to theme default
    key = "foreground" if is_fg else "background"
    return theme.get(key, (255, 255, 255) if is_fg else (0, 0, 0))
