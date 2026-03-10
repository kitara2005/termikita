"""Color conversion utilities for terminal colors."""


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' or 'RRGGBB' to (r, g, b) tuple."""
    hex_str = hex_str.lstrip("#")
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def rgb_to_nscolor(r: int, g: int, b: int):
    """Convert RGB (0-255) to NSColor (macOS AppKit color object)."""
    from AppKit import NSColor  # type: ignore[import]

    return NSColor.colorWithSRGBRed_green_blue_alpha_(
        r / 255.0, g / 255.0, b / 255.0, 1.0
    )


def ansi_256_to_rgb(index: int) -> tuple[int, int, int]:
    """Convert ANSI 256-color index to RGB tuple.

    The 256-color palette is split into three regions:
      - 0-15:   Standard 16 colors (terminal-defined)
      - 16-231: 6x6x6 color cube
      - 232-255: 24-step grayscale ramp
    """
    if index < 16:
        # Standard 16 ANSI colors — widely-used default values
        basic_colors = [
            (0, 0, 0),       (205, 0, 0),     (0, 205, 0),     (205, 205, 0),
            (0, 0, 238),     (205, 0, 205),   (0, 205, 205),   (229, 229, 229),
            (127, 127, 127), (255, 0, 0),     (0, 255, 0),     (255, 255, 0),
            (92, 92, 255),   (255, 0, 255),   (0, 255, 255),   (255, 255, 255),
        ]
        return basic_colors[index]

    if index < 232:
        # 6x6x6 color cube: indices 16-231
        index -= 16
        r = (index // 36) * 51
        g = ((index % 36) // 6) * 51
        b = (index % 6) * 51
        return (r, g, b)

    # 24-step grayscale ramp: indices 232-255
    shade = 8 + (index - 232) * 10
    return (shade, shade, shade)
