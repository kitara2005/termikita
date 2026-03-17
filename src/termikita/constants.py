"""App-wide constants for Termikita terminal emulator."""

import sys
from pathlib import Path

# Application identity
APP_NAME = "Termikita"
APP_BUNDLE_ID = "com.termikita.app"

# Default terminal dimensions
DEFAULT_COLS = 80
DEFAULT_ROWS = 24

# Scrollback buffer size (lines)
DEFAULT_SCROLLBACK = 100_000

# Font defaults — SF Mono is Apple's system monospace, optimized for Retina
DEFAULT_FONT_FAMILY = "SF Mono"
DEFAULT_FONT_SIZE = 13.0

# Terminal padding (points) — breathing room between text and view edges
TERMINAL_PADDING_X = 12.0
TERMINAL_PADDING_Y = 8.0

# User config directory (~/.config/termikita/)
CONFIG_DIR = Path.home() / ".config" / "termikita"

# Themes directory — resolves correctly both in dev and inside .app bundle
def _get_themes_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Running as .app bundle: executable is MacOS/Termikita, Resources is one level up
        return Path(sys.executable).parent.parent / "Resources" / "themes"
    return Path(__file__).parent.parent.parent / "themes"

THEMES_DIR = _get_themes_dir()

# Terminal environment variables advertised to child processes
DEFAULT_TERM = "xterm-256color"
DEFAULT_COLORTERM = "truecolor"  # Required for 24-bit color (Claude Code CLI, etc.)

# Font smoothing — reads macOS AppleFontSmoothing preference
# 0 = thin strokes (no smoothing), 1-3 = smoothing intensity, None = system default (on)
def get_font_smoothing_enabled() -> bool:
    """Read AppleFontSmoothing from user defaults. 0 = thin strokes, else = normal."""
    try:
        from Foundation import NSUserDefaults  # type: ignore[import]
        defaults = NSUserDefaults.standardUserDefaults()
        if defaults.objectForKey_("AppleFontSmoothing") is None:
            return True  # system default = smoothing on
        return defaults.integerForKey_("AppleFontSmoothing") != 0
    except Exception:
        return True


# Tab bar height (points) — shared by main_window.py and tab_controller.py
TAB_BAR_HEIGHT: float = 28.0

# Fallback theme colors — used when no JSON theme is loaded
DEFAULT_THEME: dict = {
    "foreground": (204, 204, 204),
    "background": (30, 30, 30),
    "cursor": (255, 255, 255),
    "selection": (68, 68, 68),
    "ansi": [
        (0, 0, 0),       (204, 0, 0),     (0, 204, 0),     (204, 204, 0),
        (0, 0, 204),     (204, 0, 204),   (0, 204, 204),   (204, 204, 204),
        (128, 128, 128), (255, 0, 0),     (0, 255, 0),     (255, 255, 0),
        (0, 0, 255),     (255, 0, 255),   (0, 255, 255),   (255, 255, 255),
    ],
}

# PTY I/O constants
PTY_READ_CHUNK_SIZE = 65536  # bytes per os.read() call in the read thread
PTY_ENV_TERM = "xterm-256color"  # alias kept for explicit PTY usage
