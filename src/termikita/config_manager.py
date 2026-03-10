"""User preferences persistence for Termikita.

Stores settings in ~/.config/termikita/config.json.
Falls back to DEFAULTS on missing keys or corrupt file.
"""

import json
from pathlib import Path
from typing import Any

from termikita.constants import CONFIG_DIR

# Default configuration values
DEFAULTS: dict[str, Any] = {
    "font_family": "SF Mono",
    "font_size": 13.0,
    "theme": "default-dark",
    "scrollback_lines": 100_000,
    "cursor_style": "block",       # "block" | "beam" | "underline"
    "cursor_blink": True,
    "line_height": 1.2,            # line height multiplier
    "window_width": 800,           # pixels
    "window_height": 500,          # pixels
    "shell": "",                   # empty = auto-detect from $SHELL
    "confirm_close": True,         # confirm before closing tab with running process
}


class ConfigManager:
    """Manages persistent user preferences backed by a JSON config file."""

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self._config_dir = config_dir
        self._config_path = config_dir / "config.json"
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load config from disk, merging over defaults. Silent on error."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    user_data = json.load(f)
                if isinstance(user_data, dict):
                    self._data.update(user_data)
            except (json.JSONDecodeError, OSError):
                pass  # Keep defaults on corrupt or unreadable file

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for key; falls back to default or DEFAULTS[key]."""
        if key in self._data:
            return self._data[key]
        if default is not None:
            return default
        return DEFAULTS.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set an in-memory config value. Call save() to persist."""
        self._data[key] = value

    def save(self) -> None:
        """Persist current config to disk."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(self._data, f, indent=2)

    def reload(self) -> None:
        """Reset to defaults then re-read config file from disk."""
        self._data = dict(DEFAULTS)
        self._load()

    def reset_defaults(self) -> None:
        """Overwrite config with factory defaults and save."""
        self._data = dict(DEFAULTS)
        self.save()

    # ------------------------------------------------------------------
    # Typed property accessors
    # ------------------------------------------------------------------

    @property
    def font_family(self) -> str:
        return str(self._data.get("font_family", DEFAULTS["font_family"]))

    @property
    def font_size(self) -> float:
        return float(self._data.get("font_size", DEFAULTS["font_size"]))

    @property
    def theme(self) -> str:
        return str(self._data.get("theme", DEFAULTS["theme"]))

    @property
    def scrollback_lines(self) -> int:
        return int(self._data.get("scrollback_lines", DEFAULTS["scrollback_lines"]))

    @property
    def cursor_style(self) -> str:
        return str(self._data.get("cursor_style", DEFAULTS["cursor_style"]))

    @property
    def cursor_blink(self) -> bool:
        return bool(self._data.get("cursor_blink", DEFAULTS["cursor_blink"]))

    @property
    def line_height(self) -> float:
        return float(self._data.get("line_height", DEFAULTS["line_height"]))

    @property
    def window_width(self) -> int:
        return int(self._data.get("window_width", DEFAULTS["window_width"]))

    @property
    def window_height(self) -> int:
        return int(self._data.get("window_height", DEFAULTS["window_height"]))

    @property
    def shell(self) -> str:
        return str(self._data.get("shell", DEFAULTS["shell"]))

    @property
    def confirm_close(self) -> bool:
        return bool(self._data.get("confirm_close", DEFAULTS["confirm_close"]))
