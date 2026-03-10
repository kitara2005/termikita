"""Drawing and timer mixin for TerminalView.

Handles drawRect_, selection highlight rendering, scroll-wheel, resize,
and the 60 fps refresh + cursor-blink timers. Mixed into TerminalView.

Performance optimizations (Phase 00):
- Dirty-row invalidation: only redraws lines that changed
- Cursor blink: invalidates cursor cell only, not entire view
- Partial drawRect_: only draws rows intersecting the dirty rect
"""

from __future__ import annotations

from AppKit import (  # type: ignore[import]
    NSBezierPath,
    NSGraphicsContext,
    NSTimer,
    NSColor,
)
from Foundation import NSMakeRect  # type: ignore[import]

from termikita.color_resolver import resolve_color


class TerminalViewDrawMixin:
    """Drawing, timers, resize, and scroll helpers for TerminalView."""

    # ------------------------------------------------------------------
    # drawRect_ — partial redraw: only rows intersecting dirty rect
    # ------------------------------------------------------------------

    def drawRect_(self, rect: object) -> None:
        context = NSGraphicsContext.currentContext()
        if context is None or getattr(self, "_session", None) is None:
            return

        ch = self._renderer.cell_height
        if ch <= 0:
            return

        # Fill background only for the invalidated rect
        bg_rgb = self._theme_colors.get("background", (30, 30, 30))
        NSColor.colorWithCalibratedRed_green_blue_alpha_(
            bg_rgb[0] / 255.0, bg_rgb[1] / 255.0, bg_rgb[2] / 255.0, 1.0
        ).setFill()
        NSBezierPath.fillRect_(rect)

        # Determine which rows intersect with the dirty rect
        lines = self._session.buffer.get_visible_lines()
        first_row = max(0, int(rect.origin.y / ch))
        last_row = min(len(lines), int((rect.origin.y + rect.size.height) / ch) + 1)

        for row_idx in range(first_row, last_row):
            self._renderer.draw_line(context, row_idx * ch, lines[row_idx], self._theme_colors)

        # Draw cursor only if its row is within the dirty rect
        cursor_row, cursor_col, cursor_visible = self._session.buffer.get_cursor()
        at_bottom = self._session.buffer.is_at_bottom
        if cursor_visible and self._cursor_visible and at_bottom:
            if first_row <= cursor_row < last_row:
                cursor_color = resolve_color(
                    self._theme_colors.get("cursor", (255, 255, 255)),
                    is_fg=True,
                    theme=self._theme_colors,
                )
                self._renderer.draw_cursor(
                    context, cursor_row, cursor_col, "block", cursor_color
                )

        if self._selection_start and self._selection_end:
            self._draw_selection_highlight(self.bounds())

        if self._marked_text:
            self._renderer.draw_marked_text(
                context, self._marked_text, cursor_col, cursor_row, self._theme_colors,
            )

    def _draw_selection_highlight(self, bounds: object) -> None:
        """Shade selected cells with semi-transparent theme selection color."""
        sel_rgb = self._theme_colors.get("selection", (68, 68, 68))
        NSColor.colorWithCalibratedRed_green_blue_alpha_(
            sel_rgb[0] / 255.0, sel_rgb[1] / 255.0, sel_rgb[2] / 255.0, 0.5
        ).setFill()

        r0, c0 = self._selection_start
        r1, c1 = self._selection_end
        if (r0, c0) > (r1, c1):
            r0, c0, r1, c1 = r1, c1, r0, c0

        cw = self._renderer.cell_width
        ch = self._renderer.cell_height
        max_cols = int(bounds.size.width / cw) if cw > 0 else 0

        for row in range(r0, r1 + 1):
            col_start = c0 if row == r0 else 0
            col_end = c1 if row == r1 else max_cols
            if col_end > col_start:
                NSBezierPath.fillRect_(
                    NSMakeRect(col_start * cw, row * ch, (col_end - col_start) * cw, ch)
                )

    # ------------------------------------------------------------------
    # Scroll wheel
    # ------------------------------------------------------------------

    def scrollWheel_(self, event: object) -> None:
        delta = event.deltaY()
        if delta > 0:
            self._session.buffer.scroll_up(max(1, int(delta * 3)))
        elif delta < 0:
            self._session.buffer.scroll_down(max(1, int(abs(delta) * 3)))
        self.setNeedsDisplay_(True)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _start_timers(self) -> None:
        self._start_refresh_timer()
        self._start_cursor_blink()

    def _start_refresh_timer(self) -> None:
        self._refresh_timer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / 60.0, self, "refreshDisplay:", None, True
            )
        )

    def _start_cursor_blink(self) -> None:
        self._cursor_blink_timer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.5, self, "blinkCursor:", None, True
            )
        )

    def refreshDisplay_(self, timer: object) -> None:
        """60 fps poll — invalidates only dirty row rects for efficient redraw."""
        session = getattr(self, "_session", None)
        if not session or session.buffer.synchronized:
            return

        ch = self._renderer.cell_height
        w = self.bounds().size.width

        # Track cursor movement (pyte doesn't mark lines dirty for cursor-only moves)
        cursor_row, cursor_col, _ = session.buffer.get_cursor()
        prev = getattr(self, "_prev_cursor_pos", None)
        cursor_moved = prev is not None and prev != (cursor_row, cursor_col)
        self._prev_cursor_pos = (cursor_row, cursor_col)

        dirty_rows = session.buffer.get_dirty_rows()

        if dirty_rows is None:
            # Full redraw needed (scroll, resize, first frame)
            self.setNeedsDisplay_(True)
            session.buffer.clear_dirty()
        elif dirty_rows or cursor_moved:
            for row in dirty_rows:
                self.setNeedsDisplayInRect_(NSMakeRect(0, row * ch, w, ch))
            if cursor_moved and prev:
                # Erase cursor ghost at old position, draw at new
                self.setNeedsDisplayInRect_(NSMakeRect(0, prev[0] * ch, w, ch))
                self.setNeedsDisplayInRect_(NSMakeRect(0, cursor_row * ch, w, ch))
            session.buffer.clear_dirty()

    def blinkCursor_(self, timer: object) -> None:
        """Toggle cursor visibility — invalidate only the cursor cell."""
        self._cursor_visible = not self._cursor_visible
        session = getattr(self, "_session", None)
        if not session:
            return
        cursor_row, cursor_col, _ = session.buffer.get_cursor()
        cw = self._renderer.cell_width
        ch = self._renderer.cell_height
        self.setNeedsDisplayInRect_(NSMakeRect(cursor_col * cw, cursor_row * ch, cw, ch))
