"""NSView subclass for Termikita terminal display and input handling.

Composes three mixins:
- TerminalViewDrawMixin  — drawRect_, selection highlight, scroll, timers
- TerminalViewInputMixin — NSTextInputClient, mouse selection, clipboard

PyObjC only registers methods as ObjC selectors if they exist directly on the
class (not inherited from plain Python mixins). Every method that the ObjC
runtime must discover (drawRect_, NSTextInputClient protocol, mouse/scroll,
timer callbacks) is forwarded explicitly below.

Drawing uses isFlipped=True (top-left origin) so row 0 is at y=0.
"""

from __future__ import annotations

import objc  # type: ignore[import]
from AppKit import NSView, NSEventModifierFlagCommand, NSEventModifierFlagControl  # type: ignore[import]
from Foundation import NSNotFound  # type: ignore[import]

from termikita.terminal_session import TerminalSession
from termikita.text_renderer import TextRenderer
from termikita.terminal_view_draw import TerminalViewDrawMixin
from termikita.terminal_view_input import TerminalViewInputMixin
from termikita.input_handler import KEY_MAP
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
        self._marked_text: str | None = None
        self._marked_range: tuple[int, int] = (NSNotFound, 0)
        self._selected_range: tuple[int, int] = (0, 0)
        self._selection_start: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        self._cursor_visible: bool = True
        self._cursor_blink_timer: object = None
        self._refresh_timer: object = None
        self._back_buffer: object = None
        self._prev_cursor_pos: tuple[int, int] | None = None
        # Layer-backed view enables GPU compositing for smoother drawing
        self.setWantsLayer_(True)
        if self.layer():
            self.layer().setDrawsAsynchronously_(True)

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
    # PyObjC forwarding: drawing + timers (from TerminalViewDrawMixin)
    # ------------------------------------------------------------------

    def drawRect_(self, rect: object) -> None:
        TerminalViewDrawMixin.drawRect_(self, rect)

    def scrollWheel_(self, event: object) -> None:
        TerminalViewDrawMixin.scrollWheel_(self, event)

    def refreshDisplay_(self, timer: object) -> None:
        TerminalViewDrawMixin.refreshDisplay_(self, timer)

    def blinkCursor_(self, timer: object) -> None:
        TerminalViewDrawMixin.blinkCursor_(self, timer)

    # ------------------------------------------------------------------
    # PyObjC forwarding: NSTextInputClient (from TerminalViewInputMixin)
    # ------------------------------------------------------------------

    def insertText_replacementRange_(self, string: object, rng: object) -> None:
        TerminalViewInputMixin.insertText_replacementRange_(self, string, rng)

    def setMarkedText_selectedRange_replacementRange_(
        self, string: object, selRange: object, replRange: object
    ) -> None:
        TerminalViewInputMixin.setMarkedText_selectedRange_replacementRange_(
            self, string, selRange, replRange
        )

    def unmarkText(self) -> None:
        TerminalViewInputMixin.unmarkText(self)

    def hasMarkedText(self) -> bool:
        return TerminalViewInputMixin.hasMarkedText(self)

    def markedRange(self) -> object:
        return TerminalViewInputMixin.markedRange(self)

    def selectedRange(self) -> object:
        return TerminalViewInputMixin.selectedRange(self)

    def firstRectForCharacterRange_actualRange_(self, range_: object, actual: object) -> object:
        return TerminalViewInputMixin.firstRectForCharacterRange_actualRange_(
            self, range_, actual
        )

    def attributedSubstringForProposedRange_actualRange_(
        self, range_: object, actual: object
    ) -> None:
        return None

    def characterIndexForPoint_(self, point: object) -> int:
        return 0

    def validAttributesForMarkedText(self) -> list:
        return []

    # ------------------------------------------------------------------
    # PyObjC forwarding: mouse events (from TerminalViewInputMixin)
    # ------------------------------------------------------------------

    def mouseDown_(self, event: object) -> None:
        TerminalViewInputMixin.mouseDown_(self, event)

    def mouseDragged_(self, event: object) -> None:
        TerminalViewInputMixin.mouseDragged_(self, event)

    def mouseUp_(self, event: object) -> None:
        TerminalViewInputMixin.mouseUp_(self, event)

    # ------------------------------------------------------------------
    # PyObjC forwarding: context menu (from TerminalViewInputMixin)
    # ------------------------------------------------------------------

    def menuForEvent_(self, event: object) -> object:
        return TerminalViewInputMixin.menuForEvent_(self, event)

    def contextCopy_(self, sender: object) -> None:
        TerminalViewInputMixin.contextCopy_(self, sender)

    def contextPaste_(self, sender: object) -> None:
        TerminalViewInputMixin.contextPaste_(self, sender)

    def contextSelectAll_(self, sender: object) -> None:
        TerminalViewInputMixin.contextSelectAll_(self, sender)

    def contextClearBuffer_(self, sender: object) -> None:
        TerminalViewInputMixin.contextClearBuffer_(self, sender)

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------

    def keyDown_(self, event: object) -> None:
        modifiers = event.modifierFlags()
        if modifiers & NSEventModifierFlagCommand:
            self._handle_cmd_shortcut(event)
            return
        # Ctrl+letter → control character (0x01-0x1A)
        if modifiers & NSEventModifierFlagControl:
            chars = event.characters()
            if chars and len(chars) == 1:
                ch = chars[0].lower()
                if "a" <= ch <= "z":
                    self._session.write(bytes([ord(ch) - ord("a") + 1]))
                    return
        # Special keys (Return, Tab, Backspace, arrows, etc.) → write directly
        keycode = event.keyCode()
        if keycode in KEY_MAP:
            self._session.write(KEY_MAP[keycode])
            return
        # Regular character input → send UTF-8 bytes to PTY
        chars = event.characters()
        if chars:
            try:
                self._session.write(chars.encode("utf-8"))
            except (UnicodeEncodeError, AttributeError):
                pass

    def doCommandBySelector_(self, selector: object) -> None:
        pass

    def _handle_cmd_shortcut(self, event: object) -> None:
        chars = event.charactersIgnoringModifiers()
        if not chars:
            return
        key = chars[0].lower()
        if key == "c":
            if self._selection_start and self._selection_end:
                self._copy_selection()
            else:
                self._session.write(b"\x03")
        elif key == "v":
            self._paste_clipboard()
        elif key == "a":
            self._select_all()
        elif key == "k":
            self._session.write(b"\x0c")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def dealloc(self) -> None:
        try:
            if getattr(self, "_refresh_timer", None):
                self._refresh_timer.invalidate()
            if getattr(self, "_cursor_blink_timer", None):
                self._cursor_blink_timer.invalidate()
            if getattr(self, "_session", None):
                self._session.shutdown()
        except Exception:
            pass
        objc.super(TerminalView, self).dealloc()
