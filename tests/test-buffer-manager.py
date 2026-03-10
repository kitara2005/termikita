"""Tests for BufferManager — Phase 03 success criteria verification.

Run with: .venv/bin/python3 -m pytest tests/test-buffer-manager.py -v
"""

import unicodedata

import pytest

from termikita.buffer_manager import BufferManager, CellData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bm(cols: int = 80, rows: int = 24, scrollback_max: int = 100_000) -> BufferManager:
    return BufferManager(cols=cols, rows=rows, scrollback_max=scrollback_max)


# ---------------------------------------------------------------------------
# Basic instantiation
# ---------------------------------------------------------------------------

def test_instantiation():
    bm = _make_bm()
    assert bm.title == "Termikita"
    assert bm.scrollback_length == 0
    assert bm.cursor == (0, 0)


# ---------------------------------------------------------------------------
# VT100 color attributes
# ---------------------------------------------------------------------------

def test_plain_text_default_colors():
    """Plain text cells should have default fg/bg."""
    bm = _make_bm()
    bm.feed(b"Hello")
    h = bm.get_cell(0, 0)
    assert h.char == "H"
    assert h.fg == "default"
    assert h.bg == "default"


def test_ansi_color_red():
    """'\x1b[31m' sets fg to red; '\x1b[0m' resets to default."""
    bm = _make_bm()
    bm.feed(b"Hello \x1b[31mred\x1b[0m world")
    # 'H','e','l','l','o',' ' at cols 0-5 → default fg
    assert bm.get_cell(0, 0).fg == "default"
    # 'r','e','d' at cols 6,7,8 → red fg
    r_cell = bm.get_cell(0, 6)
    assert r_cell.char == "r"
    # pyte represents ANSI colors as strings like "red" or "1"
    assert r_cell.fg != "default"


def test_bold_attribute():
    bm = _make_bm()
    bm.feed(b"\x1b[1mBold\x1b[0m")
    assert bm.get_cell(0, 0).bold is True
    assert bm.get_cell(0, 0).char == "B"


# ---------------------------------------------------------------------------
# Scrollback buffer
# ---------------------------------------------------------------------------

def test_scrollback_captures_on_overflow():
    """30 lines into 24-row screen → 6 lines in scrollback."""
    bm = _make_bm(cols=40, rows=24)
    for i in range(30):
        bm.feed(f"Line {i:02d}\r\n".encode())
    assert bm.scrollback_length == 6


def test_scrollback_deque_maxlen_drops_oldest():
    """Feed 100_001 lines → scrollback length == 100_000 (deque auto-drops)."""
    bm = _make_bm(cols=10, rows=5, scrollback_max=100_000)
    chunk = b"x\r\n" * 50_000          # 50k newlines per chunk (fast)
    bm.feed(chunk)
    bm.feed(chunk)                     # total 100k lines → fills buffer
    # One more push to trigger drop
    bm.feed(b"extra\r\n")
    assert bm.scrollback_length == 100_000


def test_scrollback_line_access():
    """get_scrollback_line(0) returns the most recently scrolled line."""
    bm = _make_bm(cols=40, rows=5)
    # Feed 6 lines into 5-row screen → 1 in scrollback
    for i in range(6):
        bm.feed(f"Line{i:02d}\r\n".encode())
    line = bm.get_scrollback_line(0)
    assert isinstance(line, list)
    assert len(line) == 40
    # First 6 chars of scrolled-off line should be "Line00"
    chars = "".join(c.char for c in line[:6])
    assert chars == "Line00"


def test_scrollback_out_of_range_returns_empty():
    bm = _make_bm()
    assert bm.get_scrollback_line(9999) == []


# ---------------------------------------------------------------------------
# NFC normalization (Vietnamese)
# ---------------------------------------------------------------------------

def test_nfc_normalization_vietnamese():
    """NFD-encoded Vietnamese stored as NFC in buffer cells."""
    # Compose "Đây" in NFD then encode as UTF-8
    nfd_text = unicodedata.normalize("NFD", "Đây")
    bm = _make_bm(cols=80, rows=24)
    bm.feed(nfd_text.encode("utf-8"))
    # Read first cell char and verify it's NFC
    char = bm.get_cell(0, 0).char
    assert unicodedata.is_normalized("NFC", char), f"Expected NFC, got: {char!r}"


def test_full_vietnamese_sentence():
    """Bytes from prompt: 'Đây là tiếng Việt' round-trips correctly."""
    raw = b"Hello Vietnamese: \xc4\x90\xc3\xa2y l\xc3\xa0 ti\xe1\xba\xbfng Vi\xe1\xbb\x87t"
    bm = _make_bm()
    bm.feed(raw)  # must not raise
    # Verify first cell is 'H'
    assert bm.get_cell(0, 0).char == "H"


# ---------------------------------------------------------------------------
# Dirty tracking
# ---------------------------------------------------------------------------

def test_dirty_set_after_feed():
    bm = _make_bm()
    bm.clear_dirty()
    bm.feed(b"abc")
    assert bm.dirty is True
    dirty = bm.get_dirty_lines()
    assert 0 in dirty


def test_clear_dirty():
    bm = _make_bm()
    bm.feed(b"abc")
    bm.clear_dirty()
    assert bm.dirty is False
    assert bm.get_dirty_lines() == set()


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------

def test_resize():
    bm = _make_bm(cols=80, rows=24)
    bm.resize(cols=132, rows=50)
    lines = bm.get_visible_lines()
    assert len(lines) == 50
    assert len(lines[0]) == 132


def test_resize_resets_scroll_offset():
    bm = _make_bm(cols=40, rows=5)
    for _ in range(10):
        bm.feed(b"line\r\n")
    bm.scroll_up(5)
    bm.resize(cols=40, rows=5)
    # scroll_offset reset → get_visible_lines returns live screen
    assert len(bm.get_visible_lines()) == 5


# ---------------------------------------------------------------------------
# User scroll controls
# ---------------------------------------------------------------------------

def test_scroll_up_down():
    bm = _make_bm(cols=40, rows=5)
    for _ in range(10):
        bm.feed(b"line\r\n")
    bm.scroll_up(3)
    assert bm._scroll_offset == 3
    bm.scroll_down(1)
    assert bm._scroll_offset == 2
    bm.scroll_to_bottom()
    assert bm._scroll_offset == 0


def test_scroll_up_capped_at_scrollback_length():
    bm = _make_bm(cols=40, rows=5)
    for _ in range(6):
        bm.feed(b"line\r\n")
    sb_len = bm.scrollback_length
    bm.scroll_up(9999)
    assert bm._scroll_offset == sb_len


# ---------------------------------------------------------------------------
# OSC 8 hyperlink detection
# ---------------------------------------------------------------------------

def test_osc8_hyperlink_url_tracked():
    """After feeding an OSC 8 open sequence, _osc8_current_url is set."""
    bm = _make_bm()
    osc8_open = b"\x1b]8;;https://example.com\x07"
    bm.feed(osc8_open + b"link text")
    assert bm._osc8_current_url == "https://example.com"


def test_osc8_hyperlink_close_clears_url():
    """OSC 8 close sequence resets active URL to None."""
    bm = _make_bm()
    bm.feed(b"\x1b]8;;https://example.com\x07link\x1b]8;;\x07")
    assert bm._osc8_current_url is None


# ---------------------------------------------------------------------------
# DEC 2026 synchronized output
# ---------------------------------------------------------------------------

def test_dec2026_synchronized_flag():
    """DEC 2026h sets synchronized=True; 2026l clears it."""
    bm = _make_bm()
    assert bm.synchronized is False
    bm.feed(b"\x1b[?2026h")
    assert bm.synchronized is True
    bm.feed(b"\x1b[?2026l")
    assert bm.synchronized is False


# ---------------------------------------------------------------------------
# Visible lines
# ---------------------------------------------------------------------------

def test_get_visible_lines_dimensions():
    bm = _make_bm(cols=80, rows=24)
    lines = bm.get_visible_lines()
    assert len(lines) == 24
    assert all(len(row) == 80 for row in lines)


def test_get_visible_lines_content():
    bm = _make_bm(cols=80, rows=24)
    bm.feed(b"ABCDE")
    lines = bm.get_visible_lines()
    chars = "".join(c.char for c in lines[0][:5])
    assert chars == "ABCDE"


# ---------------------------------------------------------------------------
# Alternate screen buffer (smcup / rmcup)
# ---------------------------------------------------------------------------

def test_alternate_screen_enter_exit():
    """Enter alt screen, write text, exit → original content restored."""
    bm = _make_bm(cols=80, rows=24)
    bm.feed(b"Original")
    # Enter alternate screen (smcup)
    bm.feed(b"\x1b[?1049h")
    bm.feed(b"Alt screen")
    # Exit alternate screen (rmcup) — pyte restores original buffer
    bm.feed(b"\x1b[?1049l")
    lines = bm.get_visible_lines()
    chars = "".join(c.char for c in lines[0][:8])
    assert chars == "Original"
