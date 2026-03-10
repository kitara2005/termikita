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

# Font defaults
DEFAULT_FONT_FAMILY = "SF Mono"
DEFAULT_FONT_SIZE = 13.0

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

# PTY I/O constants
PTY_READ_CHUNK_SIZE = 4096   # bytes per os.read() call in the read thread
PTY_ENV_TERM = "xterm-256color"  # alias kept for explicit PTY usage
