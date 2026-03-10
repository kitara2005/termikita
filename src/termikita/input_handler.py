"""Key event to terminal byte sequence translation for Termikita.

Maps NSEvent key codes and modifier combinations to the escape sequences
expected by terminal applications (VT100/xterm standard).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Special key code → terminal escape sequence map
# ---------------------------------------------------------------------------

KEY_MAP: dict[int, bytes] = {
    0x7E: b"\x1b[A",    # Up arrow
    0x7D: b"\x1b[B",    # Down arrow
    0x7C: b"\x1b[C",    # Right arrow
    0x7B: b"\x1b[D",    # Left arrow
    0x7A: b"\x1bOP",    # F1
    0x78: b"\x1bOQ",    # F2
    0x63: b"\x1bOR",    # F3
    0x76: b"\x1bOS",    # F4
    0x60: b"\x1b[15~",  # F5
    0x61: b"\x1b[17~",  # F6
    0x62: b"\x1b[18~",  # F7
    0x64: b"\x1b[19~",  # F8
    0x65: b"\x1b[20~",  # F9
    0x6D: b"\x1b[21~",  # F10
    0x67: b"\x1b[23~",  # F11
    0x6F: b"\x1b[24~",  # F12
    0x73: b"\x1b[H",    # Home
    0x77: b"\x1b[F",    # End
    0x74: b"\x1b[5~",   # Page Up
    0x79: b"\x1b[6~",   # Page Down
    0x75: b"\x1b[3~",   # Delete (forward delete)
    0x33: b"\x7f",      # Backspace (DEL)
    0x24: b"\r",        # Return (carriage return)
    0x30: b"\t",        # Tab
    0x35: b"\x1b",      # Escape
}


def translate_key_event(event: object) -> bytes | None:
    """Convert an NSEvent to a terminal byte sequence.

    Handles Ctrl+letter control characters, special keys from KEY_MAP,
    and regular printable characters encoded as UTF-8.

    Args:
        event: An NSEvent object from AppKit.

    Returns:
        Bytes to send to the PTY, or None if the event is unhandled.
    """
    try:
        from AppKit import NSEventModifierFlagControl  # type: ignore[import]
    except ImportError:
        # Not running under AppKit — unit test fallback
        NSEventModifierFlagControl = 1 << 18

    keycode = event.keyCode()
    modifiers = event.modifierFlags()
    chars = event.characters()

    # Ctrl+letter: map to control character 0x01-0x1A
    if modifiers & NSEventModifierFlagControl and chars and len(chars) == 1:
        ch = chars[0].lower()
        if "a" <= ch <= "z":
            return bytes([ord(ch) - ord("a") + 1])

    # Special key from map
    if keycode in KEY_MAP:
        return KEY_MAP[keycode]

    # Regular printable characters → UTF-8
    if chars:
        try:
            return chars.encode("utf-8")
        except (UnicodeEncodeError, AttributeError):
            return None

    return None
