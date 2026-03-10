"""Theme management for Termikita terminal emulator.

Loads JSON theme files from the themes/ directory, resolves hex colors to
RGB tuples, and provides theme switching. The resolved color dict format
matches what color_resolver.py expects.
"""

from __future__ import annotations

import json
from pathlib import Path

from termikita.color_utils import hex_to_rgb
from termikita.constants import THEMES_DIR

# ---------------------------------------------------------------------------
# Default ANSI palette used as fallback when theme has no/partial ansi list
# ---------------------------------------------------------------------------
_DEFAULT_ANSI_HEX = [
    "#000000", "#cc0000", "#00cc00", "#cccc00",
    "#0000cc", "#cc00cc", "#00cccc", "#cccccc",
    "#808080", "#ff0000", "#00ff00", "#ffff00",
    "#0000ff", "#ff00ff", "#00ffff", "#ffffff",
]


def _fallback_theme() -> dict:
    """Return a minimal dark theme as fallback when no themes are loaded."""
    return {
        "foreground": hex_to_rgb("#cccccc"),
        "background": hex_to_rgb("#1e1e1e"),
        "cursor":     hex_to_rgb("#ffffff"),
        "selection":  hex_to_rgb("#444444"),
        "ansi":       [hex_to_rgb(c) for c in _DEFAULT_ANSI_HEX],
    }


class ThemeManager:
    """Load, resolve, and switch terminal color themes.

    Theme JSON files live in the themes/ directory at project root.
    Each file is keyed by its stem (filename without .json).

    Resolved color dicts use (r, g, b) tuples compatible with color_resolver.
    """

    def __init__(self, themes_dir: Path = THEMES_DIR) -> None:
        self._themes_dir = themes_dir
        self._themes: dict[str, dict] = {}          # stem -> raw JSON data
        self._active_theme_name: str = "default-dark"
        self._active_colors: dict = {}

        self.load_themes()

        if self._active_theme_name in self._themes:
            self._active_colors = self._resolve(self._themes[self._active_theme_name])
        else:
            self._active_colors = _fallback_theme()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_themes(self) -> None:
        """Scan themes directory and load all .json theme files."""
        if not self._themes_dir.exists():
            return

        for path in sorted(self._themes_dir.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                # Use file stem as key for predictable lookups
                self._themes[path.stem] = data
            except (json.JSONDecodeError, OSError, KeyError):
                continue

    def get_theme_names(self) -> list[str]:
        """Return sorted list of available theme keys (file stems)."""
        return sorted(self._themes.keys())

    def get_active_theme(self) -> dict:
        """Return resolved color dict for the currently active theme."""
        return self._active_colors

    def set_theme(self, name: str) -> dict:
        """Switch to theme by key (file stem). Returns resolved colors.

        If name is unknown, returns current active colors unchanged.
        """
        if name not in self._themes:
            return self._active_colors
        self._active_theme_name = name
        self._active_colors = self._resolve(self._themes[name])
        return self._active_colors

    def get_theme_colors(self, name: str) -> dict:
        """Return resolved colors for a specific theme without switching.

        Falls back to active theme colors if name is unknown.
        """
        if name not in self._themes:
            return self._active_colors
        return self._resolve(self._themes[name])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, theme_data: dict) -> dict:
        """Convert hex colors in theme JSON to (r, g, b) tuple format.

        Expected theme_data structure::

            {
                "name": "...",
                "colors": {
                    "foreground": "#rrggbb",
                    "background": "#rrggbb",
                    "cursor":     "#rrggbb",
                    "selection":  "#rrggbb",
                    "ansi":       ["#rrggbb", ...] (16 entries)
                }
            }
        """
        colors = theme_data.get("colors", {})

        raw_ansi = colors.get("ansi", _DEFAULT_ANSI_HEX)
        # Guard: ensure exactly 16 entries
        if len(raw_ansi) < 16:
            raw_ansi = raw_ansi + _DEFAULT_ANSI_HEX[len(raw_ansi):]

        return {
            "foreground": hex_to_rgb(colors.get("foreground", "#cccccc")),
            "background": hex_to_rgb(colors.get("background", "#1e1e1e")),
            "cursor":     hex_to_rgb(colors.get("cursor",     "#ffffff")),
            "selection":  hex_to_rgb(colors.get("selection",  "#444444")),
            "ansi":       [hex_to_rgb(c) for c in raw_ansi[:16]],
        }
