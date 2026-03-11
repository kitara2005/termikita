"""Terminal buffer manager with VT100 parsing via pyte.

Wraps pyte.Screen/Stream with:
- Scrollback ring buffer (collections.deque, maxlen=100_000)
- NFC normalization before parsing (Vietnamese text support)
- Dirty line tracking for efficient redraws
- OSC 8 hyperlink detection and per-cell storage
- DEC mode 2026 synchronized output suppression
"""

from __future__ import annotations

import codecs
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

# DECSCUSR — cursor shape: ESC [ Ps SP q
_DECSCUSR_RE = re.compile(r"\x1b\[([0-6]?) q")
_CURSOR_STYLE_MAP = {
    "": "block", "0": "block", "1": "block", "2": "block",
    "3": "underline", "4": "underline",
    "5": "beam", "6": "beam",
}
# DECTCEM — cursor show/hide: ESC [ ? 25 h / l
_DECTCEM_SHOW_RE = re.compile(r"\x1b\[\?25h")
_DECTCEM_HIDE_RE = re.compile(r"\x1b\[\?25l")


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
        self._cursor_style: str = "block"      # DECSCUSR cursor shape (default=block)
        self._cursor_hidden: bool = False      # Own DECTCEM tracking (don't rely on pyte)
        self._force_full_redraw: bool = True   # first frame needs full draw
        self._has_new_output: bool = False     # set True in feed(), cleared by renderer
        # Incremental UTF-8 decoder — buffers incomplete multi-byte sequences
        # across os.read() boundaries instead of replacing them with U+FFFD
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")("ignore")
        # Visible lines cache — avoids recreating 1920+ NamedTuples per frame
        self._visible_cache: list[list[CellData]] | None = None
        self._visible_cache_valid: bool = False

    # ------------------------------------------------------------------
    # Feed raw PTY bytes
    # ------------------------------------------------------------------
    def feed(self, data: bytes) -> None:
        """Decode → NFC-normalize → OSC 8/DEC 2026 pre-scan → pyte parse."""
        text = self._utf8_decoder.decode(data, False)
        text = normalize_text(text)  # NFC for Vietnamese diacritics

        # DEC 2026 synchronized output detection
        if _SYNC_BEGIN_RE.search(text):
            self._synchronized = True
        if _SYNC_END_RE.search(text):
            self._synchronized = False

        # DECTCEM cursor show/hide — track LAST occurrence to get final state.
        # When both show+hide appear in same chunk (e.g. Claude Code rendering),
        # the last one determines cursor state.
        show_matches = list(_DECTCEM_SHOW_RE.finditer(text))
        hide_matches = list(_DECTCEM_HIDE_RE.finditer(text))
        last_show = show_matches[-1].start() if show_matches else -1
        last_hide = hide_matches[-1].start() if hide_matches else -1
        if last_show > last_hide:
            self._cursor_hidden = False
        elif last_hide > last_show:
            self._cursor_hidden = True

        # DECSCUSR cursor shape (CSI Ps SP q) — use last match, implicitly shows cursor
        decscusr_matches = list(_DECSCUSR_RE.finditer(text))
        if decscusr_matches:
            m = decscusr_matches[-1]
            self._cursor_style = _CURSOR_STYLE_MAP.get(m.group(1), "block")
            self._cursor_hidden = False

        # OSC 8 hyperlink tracking
        self._osc8_current_url = _last_osc8_url(text, self._osc8_current_url)
        self._screen._osc8_current_url = self._osc8_current_url

        self._stream.feed(text)
        self._visible_cache_valid = False
        self._has_new_output = True

    # ------------------------------------------------------------------
    # Visible lines (live or scrollback + screen mix)
    # ------------------------------------------------------------------
    def get_visible_lines(self) -> list[list[CellData]]:
        """Return viewport lines for current scroll position (cached)."""
        if self._visible_cache_valid and self._visible_cache is not None:
            return self._visible_cache

        rows = self._screen.lines
        if self._scroll_offset == 0:
            # Reuse existing cache list structure if size matches — avoids
            # allocating a new list object every frame under streaming output.
            if self._visible_cache is not None and len(self._visible_cache) == rows:
                result = self._visible_cache
                for r in range(rows):
                    result[r] = self._screen.capture_line(r)
            else:
                result = [self._screen.capture_line(r) for r in range(rows)]
        else:
            sb = list(self._scrollback)          # oldest → newest
            sb_start = max(0, len(sb) - self._scroll_offset)
            window = sb[sb_start : sb_start + rows]
            if len(window) >= rows:
                result = window[:rows]
            else:
                # Pad with top screen lines if scrollback window shorter than viewport
                result = list(window)
                for r in range(rows - len(window)):
                    result.append(self._screen.capture_line(r))

        self._visible_cache = result
        self._visible_cache_valid = True
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
        return (c.y, c.x, not self._cursor_hidden)

    @property
    def cursor_style(self) -> str:
        """Current cursor shape: 'block', 'underline', or 'beam'."""
        return self._cursor_style

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------
    def get_dirty_rows(self) -> set[int] | None:
        """Dirty row indices, or None when full redraw needed (scroll/resize)."""
        if self._force_full_redraw:
            return None
        return set(self._screen.dirty)

    def get_dirty_lines(self) -> set[int]:
        return set(self._screen.dirty)

    def clear_dirty(self) -> None:
        self._screen.dirty.clear()
        self._force_full_redraw = False

    # ------------------------------------------------------------------
    # User scroll controls
    # ------------------------------------------------------------------
    def scroll_up(self, lines: int = 3) -> None:
        self._scroll_offset = min(self._scroll_offset + lines, len(self._scrollback))
        self._force_full_redraw = True
        self._visible_cache_valid = False

    def scroll_down(self, lines: int = 3) -> None:
        self._scroll_offset = max(0, self._scroll_offset - lines)
        self._force_full_redraw = True
        self._visible_cache_valid = False

    def scroll_to_bottom(self) -> None:
        self._scroll_offset = 0
        self._force_full_redraw = True
        self._visible_cache_valid = False

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------
    def resize(self, cols: int, rows: int) -> None:
        """Resize grid. No reflow in v1 — scroll_offset resets to bottom."""
        self._screen.resize(rows, cols)
        self._scroll_offset = 0
        self._force_full_redraw = True
        self._visible_cache_valid = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def has_new_output(self) -> bool:
        """True if PTY data arrived since last consume_new_output() call."""
        return self._has_new_output

    def consume_new_output(self) -> bool:
        """Read and clear has_new_output flag. Returns True if new data arrived."""
        had_output = self._has_new_output
        self._has_new_output = False
        return had_output

    @property
    def dirty(self) -> bool:
        return bool(self._screen.dirty) or self._force_full_redraw

    @property
    def is_at_bottom(self) -> bool:
        """True when viewport is at the latest output (not scrolled back)."""
        return self._scroll_offset == 0

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
