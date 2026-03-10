"""NSView subclass for Termikita terminal display and input handling.

Composes three mixins:
- TerminalViewDrawMixin  — drawRect_, selection highlight, scroll, timers
- TerminalViewInputMixin — NSTextInputClient, mouse selection, clipboard

Drawing uses isFlipped=True (top-left origin) so row 0 is at y=0.
"""

from __future__ import annotations

import objc  # type: ignore[import]
from AppKit import NSView, NSEventModifierFlagCommand  # type: ignore[import]
from Foundation import NSNotFound  # type: ignore[import]

from termikita.terminal_session import TerminalSession
from termikita.text_renderer import TextRenderer
from termikita.terminal_view_draw import TerminalViewDrawMixin
from termikita.terminal_view_input import TerminalViewInputMixin
from termikita.constants import DEFAULT_COLS, DEFAULT_ROWS

# Default theme — Phase 07 will load from JSON
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


class TerminalView(NSView, TerminalViewDrawMixin, TerminalViewInputMixin):
    """Interactive terminal NSView with IME, selection, and 60 fps rendering."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initWithFrame_(self, frame: object) -> "TerminalView":
        self = objc.super(TerminalView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._init_state()
        self._init_session()
        self._start_timers()
        return self

    def _init_state(self) -> None:
        self._renderer = TextRenderer()
        self._theme_colors = DEFAULT_THEME
        # NSTextInputClient state
        self._marked_text: str | None = None
        self._marked_range: tuple[int, int] = (NSNotFound, 0)
        self._selected_range: tuple[int, int] = (0, 0)
        # Selection state
        self._selection_start: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        # Cursor blink
        self._cursor_visible: bool = True
        self._cursor_blink_timer: object = None
        self._refresh_timer: object = None
        self._back_buffer: object = None

    def _init_session(self) -> None:
        cw, ch = self._renderer.get_cell_dimensions()
        bounds = self.bounds()
        cols = max(1, int(bounds.size.width / cw)) if cw > 0 else DEFAULT_COLS
        rows = max(1, int(bounds.size.height / ch)) if ch > 0 else DEFAULT_ROWS
        self._session = TerminalSession(cols=cols, rows=rows)

    # ------------------------------------------------------------------
    # NSView overrides
    # ------------------------------------------------------------------

    def isFlipped(self) -> bool:
        """Top-left origin — row 0 at y=0, rows increase downward."""
        return True

    def acceptsFirstResponder(self) -> bool:
        return True

    def becomeFirstResponder(self) -> bool:
        return True

    def setFrameSize_(self, newSize: object) -> None:
        objc.super(TerminalView, self).setFrameSize_(newSize)
        if not hasattr(self, "_renderer") or not self._renderer:
            return
        cw, ch = self._renderer.get_cell_dimensions()
        if cw <= 0 or ch <= 0:
            return
        new_cols = max(1, int(newSize.width / cw))
        new_rows = max(1, int(newSize.height / ch))
        if hasattr(self, "_session") and self._session:
            self._session.resize(new_cols, new_rows)
        self._back_buffer = None
        self.setNeedsDisplay_(True)

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------

    def keyDown_(self, event: object) -> None:
        if event.modifierFlags() & NSEventModifierFlagCommand:
            self._handle_cmd_shortcut(event)
            return
        # Route through Text Input System for IME (Vietnamese, CJK, etc.)
        self.interpretKeyEvents_([event])

    def doCommandBySelector_(self, selector: object) -> None:
        """Called by interpretKeyEvents_ for keys not consumed by IME."""
        pass  # Special keys handled via insertText_ path in the mixin

    def _handle_cmd_shortcut(self, event: object) -> None:
        chars = event.charactersIgnoringModifiers()
        if not chars:
            return
        key = chars[0].lower()
        if key == "c":
            if self._selection_start and self._selection_end:
                self._copy_selection()
            else:
                self._session.write(b"\x03")  # Ctrl+C / SIGINT
        elif key == "v":
            self._paste_clipboard()
        elif key == "a":
            self._select_all()
        elif key == "k":
            self._session.write(b"\x0c")  # Ctrl+L clear screen

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def dealloc(self) -> None:
        if self._refresh_timer:
            self._refresh_timer.invalidate()
        if self._cursor_blink_timer:
            self._cursor_blink_timer.invalidate()
        if hasattr(self, "_session") and self._session:
            self._session.shutdown()
        objc.super(TerminalView, self).dealloc()
