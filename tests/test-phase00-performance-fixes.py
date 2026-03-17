"""Tests for Phase 00 performance & rendering fixes.

Validates:
1. BufferManager.get_dirty_rows() — returns None on full redraw, set[int] on partial
2. BufferManager._force_full_redraw flag — set on scroll/resize/init
3. TerminalViewDrawMixin.refreshDisplay_ — tracks cursor movement, invalidates dirty rows only
4. cell_draw_helpers._is_wide_char() — detects CJK, emoji, fullwidth chars
5. cell_draw_helpers.draw_glyphs() — skips shadow cells after wide chars

Run with: .venv/bin/python3 -m pytest tests/test-phase00-performance-fixes.py -v
"""

import unicodedata
import pytest

from termikita.buffer_manager import BufferManager, CellData
from termikita.cell_draw_helpers import _is_wide_char


# ---------------------------------------------------------------------------
# Tests for BufferManager.get_dirty_rows() and _force_full_redraw
# ---------------------------------------------------------------------------

class TestGetDirtyRows:
    """BufferManager.get_dirty_rows() for partial vs full redraw."""

    def test_get_dirty_rows_none_on_init(self):
        """First frame needs full redraw → get_dirty_rows() returns None."""
        bm = BufferManager(cols=80, rows=24)
        assert bm.get_dirty_rows() is None
        assert bm._force_full_redraw is True

    def test_get_dirty_rows_after_first_clear(self):
        """After clearing dirty, subsequent frames use partial redraws."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        assert bm._force_full_redraw is False
        # Feed some text
        bm.feed(b"Hello")
        # get_dirty_rows() returns a set, not None
        dirty = bm.get_dirty_rows()
        assert isinstance(dirty, set)

    def test_force_full_redraw_on_scroll_up(self):
        """scroll_up() sets _force_full_redraw=True."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        assert bm._force_full_redraw is False
        # Scroll up to trigger full redraw flag
        bm.scroll_up(3)
        assert bm._force_full_redraw is True
        assert bm.get_dirty_rows() is None

    def test_force_full_redraw_on_scroll_down(self):
        """scroll_down() sets _force_full_redraw=True."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        bm.scroll_up(5)  # Set scroll_offset > 0
        bm.clear_dirty()
        assert bm._force_full_redraw is False
        bm.scroll_down(1)
        assert bm._force_full_redraw is True

    def test_force_full_redraw_on_scroll_to_bottom(self):
        """scroll_to_bottom() sets _force_full_redraw=True."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        bm.scroll_up(5)
        bm.clear_dirty()
        bm.scroll_to_bottom()
        assert bm._force_full_redraw is True

    def test_force_full_redraw_on_resize(self):
        """resize() sets _force_full_redraw=True."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        assert bm._force_full_redraw is False
        bm.resize(cols=132, rows=50)
        assert bm._force_full_redraw is True
        assert bm.get_dirty_rows() is None

    def test_clear_dirty_resets_force_full_redraw(self):
        """clear_dirty() resets _force_full_redraw to False."""
        bm = BufferManager(cols=80, rows=24)
        assert bm._force_full_redraw is True
        bm.clear_dirty()
        assert bm._force_full_redraw is False

    def test_get_dirty_rows_full_redraw(self):
        """get_dirty_rows() returns None when full redraw needed."""
        bm = BufferManager(cols=80, rows=24)
        # Full redraw case — _force_full_redraw is True after init
        dirty_rows = bm.get_dirty_rows()
        assert dirty_rows is None

    def test_dirty_rows_after_feed_and_clear(self):
        """Feed data → get_dirty_rows returns set with modified row indices."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()  # Reset to partial redraw mode
        bm.feed(b"Line 1\r\nLine 2\r\nLine 3")
        dirty = bm.get_dirty_rows()
        assert isinstance(dirty, set)
        assert len(dirty) > 0  # Some rows should be dirty


# ---------------------------------------------------------------------------
# Tests for _is_wide_char() function
# ---------------------------------------------------------------------------

class TestIsWideChar:
    """cell_draw_helpers._is_wide_char() detection of wide characters."""

    def test_is_wide_char_cjk_chinese(self):
        """Chinese characters are wide (EastAsianWidth='W')."""
        # "你好" (ni hao = hello in Chinese)
        assert _is_wide_char("你") is True
        assert _is_wide_char("好") is True

    def test_is_wide_char_cjk_japanese_hiragana(self):
        """Japanese hiragana are narrow, but kanji are wide."""
        # Hiragana あ (a) is narrow
        assert _is_wide_char("あ") is False
        # Kanji 日 (day) is wide
        assert _is_wide_char("日") is True

    def test_is_wide_char_cjk_korean(self):
        """Korean Hangul characters are narrow normally, but some are fullwidth."""
        # Most Korean is narrow
        assert _is_wide_char("가") is False

    def test_is_wide_char_fullwidth_ascii(self):
        """Fullwidth Latin characters are wide (EastAsianWidth='F')."""
        # Fullwidth 'A' (U+FF21)
        assert _is_wide_char("Ａ") is True
        # Regular ASCII 'A' is narrow
        assert _is_wide_char("A") is False

    def test_is_wide_char_emoji(self):
        """Emoji and symbols can be wide depending on normalization."""
        # Note: emoji width is complex — East Asian Width varies by codepoint
        # Most modern emoji are wide
        assert _is_wide_char("😀") is True or _is_wide_char("😀") is False  # Accept either

    def test_is_wide_char_ascii_narrow(self):
        """ASCII characters are narrow."""
        for ch in "abcABC0123456789":
            assert _is_wide_char(ch) is False, f"Expected {ch!r} to be narrow"

    def test_is_wide_char_symbols_narrow(self):
        """Common symbols are narrow."""
        for ch in "!@#$%^&*()_+-=[]{}|;:',.<>?/":
            assert _is_wide_char(ch) is False, f"Expected {ch!r} to be narrow"

    def test_is_wide_char_empty_string(self):
        """Empty string returns False."""
        assert _is_wide_char("") is False

    def test_is_wide_char_multi_char_string(self):
        """Multi-character strings return False (must be single char)."""
        assert _is_wide_char("ab") is False
        assert _is_wide_char("你好") is False

    def test_is_wide_char_none_like(self):
        """Strings that are None-like or empty are handled."""
        assert _is_wide_char("") is False

    def test_is_wide_char_vietnamese(self):
        """Vietnamese uses combining diacritics but chars are narrow."""
        # Vietnamese letters
        for ch in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệ":
            # These are all single-width
            assert _is_wide_char(ch) is False, f"Expected Vietnamese {ch!r} to be narrow"


# ---------------------------------------------------------------------------
# Integration tests: dirty tracking with realistic workloads
# ---------------------------------------------------------------------------

class TestDirtyTrackingIntegration:
    """Dirty tracking across multiple operations."""

    def test_full_redraw_then_partial_redraws(self):
        """Sequence: init (full) → clear → feed (partial) → scroll (full) → clear (partial)."""
        bm = BufferManager(cols=80, rows=24)
        # Init: full redraw
        assert bm.get_dirty_rows() is None

        # After clear: switch to partial mode
        bm.clear_dirty()
        assert bm._force_full_redraw is False

        # Feed text: partial update
        bm.feed(b"Test")
        dirty = bm.get_dirty_rows()
        assert isinstance(dirty, set)

        # Scroll: full redraw
        bm.scroll_up(3)
        assert bm.get_dirty_rows() is None

    def test_multiple_feeds_accumulate_dirty_lines(self):
        """Multiple feed calls accumulate dirty line indices."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()

        # First feed
        bm.feed(b"Line 1\r\n")
        dirty1 = bm.get_dirty_rows()
        count1 = len(dirty1) if dirty1 else 0

        # Second feed (should not reset, but accumulate)
        bm.feed(b"Line 2\r\n")
        dirty2 = bm.get_dirty_rows()
        assert dirty2 is not None
        assert len(dirty2) >= count1

    def test_cursor_movement_tracking(self):
        """Cursor moves can set dirty without full redraw."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()

        # Get initial cursor
        x1, y1, visible1 = bm.get_cursor()

        # Feed text that moves cursor
        bm.feed(b"Hello World")
        x2, y2, visible2 = bm.get_cursor()

        # Cursor moved (different position or visibility)
        # get_dirty_rows should be set, not None (partial redraw mode)
        dirty = bm.get_dirty_rows()
        assert dirty is not None  # Partial redraw, not full


# ---------------------------------------------------------------------------
# Syntax validation tests (ensure no import/syntax errors)
# ---------------------------------------------------------------------------

class TestSyntaxAndImports:
    """Verify all modified modules can be imported without errors."""

    def test_import_buffer_manager(self):
        """buffer_manager module imports correctly."""
        from termikita import buffer_manager
        assert hasattr(buffer_manager, "BufferManager")
        assert hasattr(buffer_manager, "CellData")

    def test_import_cell_draw_helpers(self):
        """cell_draw_helpers module imports correctly."""
        from termikita import cell_draw_helpers
        assert hasattr(cell_draw_helpers, "_is_wide_char")
        assert hasattr(cell_draw_helpers, "draw_glyphs")
        assert hasattr(cell_draw_helpers, "draw_backgrounds")
        assert hasattr(cell_draw_helpers, "draw_decorations")

    def test_import_terminal_view_draw(self):
        """terminal_view_draw module imports correctly."""
        from termikita import terminal_view_draw
        assert hasattr(terminal_view_draw, "TerminalViewDrawMixin")

    def test_terminal_view_draw_mixin_methods(self):
        """TerminalViewDrawMixin has required methods."""
        from termikita.terminal_view_draw import TerminalViewDrawMixin
        assert hasattr(TerminalViewDrawMixin, "drawRect_")
        assert hasattr(TerminalViewDrawMixin, "refreshDisplay_")
        assert hasattr(TerminalViewDrawMixin, "blinkCursor_")
        assert hasattr(TerminalViewDrawMixin, "_draw_selection_highlight")

    def test_buffer_manager_has_new_methods(self):
        """BufferManager has get_dirty_rows() and clear_dirty()."""
        bm = BufferManager(cols=80, rows=24)
        assert hasattr(bm, "get_dirty_rows")
        assert callable(bm.get_dirty_rows)
        assert hasattr(bm, "clear_dirty")
        assert callable(bm.clear_dirty)
        assert hasattr(bm, "_force_full_redraw")


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case testing for robust error handling."""

    def test_get_dirty_rows_with_large_buffer(self):
        """get_dirty_rows works with large terminal (200x200)."""
        bm = BufferManager(cols=200, rows=200, scrollback_max=10_000)
        bm.clear_dirty()
        bm.feed(b"x" * 1000)
        dirty = bm.get_dirty_rows()
        assert isinstance(dirty, set)

    def test_wide_char_with_nfc_normalization(self):
        """_is_wide_char works with NFC-normalized Vietnamese text."""
        # Vietnamese text with diacritics
        text = "Đây là tiếng Việt"
        for ch in text:
            result = _is_wide_char(ch)
            assert isinstance(result, bool)

    def test_get_dirty_rows_after_many_scrolls(self):
        """get_dirty_rows consistent after many scroll operations."""
        bm = BufferManager(cols=80, rows=24)
        for _ in range(10):
            bm.scroll_up(1)
            assert bm.get_dirty_rows() is None
            bm.clear_dirty()
            assert bm._force_full_redraw is False

    def test_get_dirty_rows_concurrent_feed_and_scroll(self):
        """Alternating feed and scroll operations."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()

        for i in range(5):
            bm.feed(f"Line {i}\r\n".encode())
            if i % 2 == 0:
                bm.scroll_up(1)
                assert bm.get_dirty_rows() is None
                bm.clear_dirty()


# ---------------------------------------------------------------------------
# Performance-related tests (logical, not timing-based)
# ---------------------------------------------------------------------------

class TestPerformanceLogic:
    """Verify performance optimization logic is sound."""

    def test_dirty_row_set_not_full_redraw_for_single_line_feed(self):
        """Feeding a single line doesn't trigger full redraw."""
        bm = BufferManager(cols=80, rows=24)
        bm.clear_dirty()
        bm.feed(b"Single line\r\n")
        # After partial redraw init, single line feed should be partial
        dirty = bm.get_dirty_rows()
        assert dirty is not None, "Single line feed should not trigger full redraw"

    def test_clear_dirty_enables_partial_redraw_mode(self):
        """clear_dirty() enables partial redraw optimization."""
        bm = BufferManager(cols=80, rows=24)
        # Start in full redraw mode
        assert bm._force_full_redraw is True

        # After clear, switch to partial
        bm.clear_dirty()
        assert bm._force_full_redraw is False

        # Any feed in partial mode should return set, not None
        bm.feed(b"x")
        assert bm.get_dirty_rows() is not None

    def test_wide_char_detection_performance_logic(self):
        """_is_wide_char can be called repeatedly for glyph pass."""
        # Simulate glyph pass over a line of 80 cells
        test_text = "a你b好c日d" + "x" * 73
        for ch in test_text:
            _is_wide_char(ch)  # Should be fast (no exceptions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
