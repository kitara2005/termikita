"""Terminal buffer manager with VT100 parsing via pyte.

Wraps pyte.Screen/Stream with:
- Scrollback ring buffer (collections.deque, maxlen=100_000)
- NFC normalization before parsing (Vietnamese text support)
- Dirty line tracking for efficient redraws
- OSC 8 hyperlink detection and per-cell storage
- DEC mode 2026 synchronized output suppression
"""

from __future__ import annotations

import collections
import re
from typing import NamedTuple

import pyte
from pyte.screens import Margins as _Margins

from termikita.constants import DEFAULT_SCROLLBACK
from termikita.unicode_utils import normalize_text

# OSC 8 hyperlink sequences  ESC ] 8 ; params ; uri BEL
_OSC8_OPEN_RE = re.compile(r"\x1b]8;[^;]*;([^\x07\x1b]*)\x07")
_OSC8_CLOSE_RE = re.compile(r"\x1b]8;;\x07")

# DEC mode 2026 synchronized output  ESC [ ? 2026 h / l
_SYNC_BEGIN_RE = re.compile(r"\x1b\[\?2026h")
_SYNC_END_RE = re.compile(r"\x1b\[\?2026l")


class CellData(NamedTuple):
    """Immutable per-cell data for the renderer layer (Phase 04+)."""

    char: str = " "
    fg: str = "default"
    bg: str = "default"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strikethrough: bool = False
    hyperlink: str | None = None  # OSC 8 URI; None = no hyperlink


def _pyte_char_to_cell(ch: object, hyperlink: str | None) -> CellData:
    """Convert a pyte Char to CellData. Returns empty CellData when ch is None."""
    if ch is None:
        return CellData(hyperlink=hyperlink)
    return CellData(
        char=ch.data,  # type: ignore[attr-defined]
        fg=ch.fg,  # type: ignore[attr-defined]
        bg=ch.bg,  # type: ignore[attr-defined]
        bold=ch.bold,  # type: ignore[attr-defined]
        italic=ch.italics,  # type: ignore[attr-defined]
        underline=ch.underscore,  # type: ignore[attr-defined]
        reverse=ch.reverse,  # type: ignore[attr-defined]
        strikethrough=ch.strikethrough,  # type: ignore[attr-defined]
        hyperlink=hyperlink,
    )


class TermikitaScreen(pyte.Screen):
    """pyte.Screen extended with scrollback capture.

    Overrides index() so that every line scrolled off the visible top is
    appended to the shared scrollback deque before pyte discards it.
    """

    def __init__(self, columns: int, lines: int) -> None:
        super().__init__(columns, lines)
        # Both fields injected / updated by BufferManager
        self._scrollback: collections.deque = collections.deque()
        self._osc8_current_url: str | None = None

    def index(self) -> None:  # type: ignore[override]
        """Capture departing top line into scrollback, then scroll."""
        top, _ = self.margins or _Margins(0, self.lines - 1)
        if top == 0:
            self._scrollback.append(self.capture_line(0))
        super().index()

    def capture_line(self, row: int) -> list[CellData]:
        """Convert a pyte buffer row to list[CellData] (one entry per column)."""
        row_data = self.buffer[row]
        url = self._osc8_current_url
        return [_pyte_char_to_cell(row_data.get(col), url) for col in range(self.columns)]


class BufferManager:
    """Manages terminal buffer: VT100 parsing, scrollback, dirty tracking.

    Usage::

        bm = BufferManager(cols=80, rows=24)
        bm.feed(pty_bytes)
        lines = bm.get_visible_lines()
    """

    def __init__(self, cols: int, rows: int, scrollback_max: int = DEFAULT_SCROLLBACK) -> None:
        self._screen = TermikitaScreen(cols, rows)
        self._stream = pyte.Stream(self._screen)

        # Ring buffer — auto-drops oldest when full, zero GC cost
        self._scrollback: collections.deque[list[CellData]] = collections.deque(
            maxlen=scrollback_max
        )
        self._screen._scrollback = self._scrollback  # shared reference

        self._scroll_offset: int = 0
        self._synchronized: bool = False       # DEC 2026 batch mode
        self._osc8_current_url: str | None = None

    # ------------------------------------------------------------------
    # Feed raw PTY bytes
    # ------------------------------------------------------------------
    def feed(self, data: bytes) -> None:
        """Decode → NFC-normalize → OSC 8/DEC 2026 pre-scan → pyte parse."""
        text = data.decode("utf-8", errors="replace")
        text = normalize_text(text)  # NFC for Vietnamese diacritics

        # DEC 2026 synchronized output detection
        if _SYNC_BEGIN_RE.search(text):
            self._synchronized = True
        if _SYNC_END_RE.search(text):
            self._synchronized = False

        # OSC 8 hyperlink tracking
        self._osc8_current_url = _last_osc8_url(text, self._osc8_current_url)
        self._screen._osc8_current_url = self._osc8_current_url

        self._stream.feed(text)

    # ------------------------------------------------------------------
    # Visible lines (live or scrollback + screen mix)
    # ------------------------------------------------------------------
    def get_visible_lines(self) -> list[list[CellData]]:
        """Return viewport lines for current scroll position."""
        rows = self._screen.lines
        if self._scroll_offset == 0:
            return [self._screen.capture_line(r) for r in range(rows)]

        sb = list(self._scrollback)          # oldest → newest
        sb_start = max(0, len(sb) - self._scroll_offset)
        window = sb[sb_start : sb_start + rows]
        if len(window) >= rows:
            return window[:rows]
        # Pad with top screen lines if scrollback window shorter than viewport
        result = list(window)
        for r in range(rows - len(window)):
            result.append(self._screen.capture_line(r))
        return result

    # ------------------------------------------------------------------
    # Cell / line / cursor access
    # ------------------------------------------------------------------
    def get_cell(self, row: int, col: int) -> CellData:
        """CellData at screen (row, col)."""
        return _pyte_char_to_cell(self._screen.buffer[row].get(col), self._osc8_current_url)

    def get_line(self, row: int) -> list[CellData]:
        """All cells in screen row."""
        return self._screen.capture_line(row)

    def get_scrollback_line(self, index: int) -> list[CellData]:
        """Scrollback line by index; 0 = most recent. Returns [] if out of range."""
        sb = self._scrollback
        if not sb or index >= len(sb):
            return []
        return list(sb)[len(sb) - 1 - index]

    def get_cursor(self) -> tuple[int, int, bool]:
        """(row, col, visible) for the terminal cursor."""
        c = self._screen.cursor
        return (c.y, c.x, not getattr(c, "hidden", False))

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------
    def get_dirty_lines(self) -> set[int]:
        return set(self._screen.dirty)

    def clear_dirty(self) -> None:
        self._screen.dirty.clear()

    # ------------------------------------------------------------------
    # User scroll controls
    # ------------------------------------------------------------------
    def scroll_up(self, lines: int = 3) -> None:
        self._scroll_offset = min(self._scroll_offset + lines, len(self._scrollback))

    def scroll_down(self, lines: int = 3) -> None:
        self._scroll_offset = max(0, self._scroll_offset - lines)

    def scroll_to_bottom(self) -> None:
        self._scroll_offset = 0

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------
    def resize(self, cols: int, rows: int) -> None:
        """Resize grid. No reflow in v1 — scroll_offset resets to bottom."""
        self._screen.resize(rows, cols)
        self._scroll_offset = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def dirty(self) -> bool:
        return bool(self._screen.dirty)

    @property
    def synchronized(self) -> bool:
        """True while DEC 2026 synchronized output is active (suppress redraws)."""
        return self._synchronized

    @property
    def cursor(self) -> tuple[int, int]:
        """(x, y) cursor position for the drawing layer."""
        return (self._screen.cursor.x, self._screen.cursor.y)

    @property
    def title(self) -> str:
        return self._screen.title or "Termikita"

    @property
    def scrollback_length(self) -> int:
        return len(self._scrollback)


# ---------------------------------------------------------------------------
# Module-level helper (keeps BufferManager under 200 lines)
# ---------------------------------------------------------------------------
def _last_osc8_url(text: str, current: str | None) -> str | None:
    """Return the OSC 8 URL active at the end of `text`, or `current` if none found."""
    events: list[tuple[int, str | None]] = [
        (m.start(), m.group(1) or None) for m in _OSC8_OPEN_RE.finditer(text)
    ]
    events += [(m.start(), None) for m in _OSC8_CLOSE_RE.finditer(text)]
    if not events:
        return current
    events.sort(key=lambda e: e[0])
    return events[-1][1]
