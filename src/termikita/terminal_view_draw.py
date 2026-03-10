"""Drawing and timer mixin for TerminalView.

Handles drawRect_, selection highlight rendering, scroll-wheel, resize,
and the 60 fps refresh + cursor-blink timers. Mixed into TerminalView.
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
    # drawRect_
    # ------------------------------------------------------------------

    def drawRect_(self, rect: object) -> None:
        context = NSGraphicsContext.currentContext()
        if context is None:
            return

        bounds = self.bounds()
        bg_rgb = self._theme_colors.get("background", (30, 30, 30))
        NSColor.colorWithCalibratedRed_green_blue_alpha_(
            bg_rgb[0] / 255.0, bg_rgb[1] / 255.0, bg_rgb[2] / 255.0, 1.0
        ).setFill()
        NSBezierPath.fillRect_(bounds)

        lines = self._session.buffer.get_visible_lines()
        ch = self._renderer.cell_height
        for row_idx, cells in enumerate(lines):
            self._renderer.draw_line(context, row_idx * ch, cells, self._theme_colors)

        cursor_row, cursor_col, cursor_visible = self._session.buffer.get_cursor()
        at_bottom = self._session.buffer._scroll_offset == 0
        if cursor_visible and self._cursor_visible and at_bottom:
            cursor_color = resolve_color(
                self._theme_colors.get("cursor", (255, 255, 255)),
                is_fg=True,
                theme=self._theme_colors,
            )
            self._renderer.draw_cursor(context, cursor_row, cursor_col, "block", cursor_color)

        if self._selection_start and self._selection_end:
            self._draw_selection_highlight(bounds)

        if self._marked_text:
            self._renderer.draw_marked_text(
                context,
                self._marked_text,
                cursor_col,
                cursor_row,
                self._theme_colors,
            )

        self._session.buffer.clear_dirty()

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
        """60 fps poll — triggers redraw when buffer has dirty lines."""
        if self._session and self._session.buffer.dirty:
            if not self._session.buffer.synchronized:
                self.setNeedsDisplay_(True)

    def blinkCursor_(self, timer: object) -> None:
        """Toggle cursor visibility every 0.5 s."""
        self._cursor_visible = not self._cursor_visible
        self.setNeedsDisplay_(True)
