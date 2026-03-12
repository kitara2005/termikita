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
from AppKit import (  # type: ignore[import]
    NSCursor,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
    NSView,
)
from Foundation import NSNotFound, NSTimer  # type: ignore[import]

# Protocol conformance required for macOS text input system (IME composition).
# Without this, inputContext() returns None and Vietnamese Telex/VNI keyboards
# fall back to raw character input instead of composition events.
NSTextInputClient = objc.protocolNamed("NSTextInputClient")

from termikita.constants import (
    DEFAULT_COLS,
    DEFAULT_ROWS,
    TERMINAL_PADDING_X,
    TERMINAL_PADDING_Y,
    get_font_smoothing_enabled,
)
from termikita.input_handler import KEY_MAP
from termikita.terminal_session import TerminalSession
from termikita.unicode_utils import normalize_text
from termikita.terminal_view_draw import TerminalViewDrawMixin
from termikita.terminal_view_input import TerminalViewInputMixin
from termikita.text_renderer import TextRenderer

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


class TerminalView(NSView, TerminalViewDrawMixin, TerminalViewInputMixin, protocols=[NSTextInputClient]):
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
        # Font smoothing preference from macOS system defaults
        self._font_smoothing: bool = get_font_smoothing_enabled()

    def _init_session(self) -> None:
        cw, ch = self._renderer.get_cell_dimensions()
        bounds = self.bounds()
        usable_w = bounds.size.width - TERMINAL_PADDING_X * 2
        usable_h = bounds.size.height - TERMINAL_PADDING_Y * 2
        cols = max(1, int(usable_w / cw)) if cw > 0 else DEFAULT_COLS
        rows = max(1, int(usable_h / ch)) if ch > 0 else DEFAULT_ROWS
        self._session = TerminalSession(cols=cols, rows=rows)

    # ------------------------------------------------------------------
    # NSView overrides
    # ------------------------------------------------------------------

    def isFlipped(self) -> bool:
        return True

    def isOpaque(self) -> bool:
        """View fills entire rect — enables optimized text rendering."""
        return True

    def acceptsFirstResponder(self) -> bool:
        return True

    def becomeFirstResponder(self) -> bool:
        return True

    def viewDidMoveToWindow(self) -> None:
        """Set layer contentsScale to match Retina backing scale factor."""
        self._sync_layer_scale()

    def viewDidChangeBackingProperties(self) -> None:
        """Re-sync contentsScale when moving between displays."""
        self._sync_layer_scale()

    def resetCursorRects(self) -> None:
        """Set I-beam cursor over terminal area (like native Terminal.app)."""
        self.addCursorRect_cursor_(self.bounds(), NSCursor.IBeamCursor())

    def _sync_layer_scale(self) -> None:
        """Ensure layer contentsScale matches Retina backing scale factor.

        Without this, layer-backed views render at 1x on Retina displays,
        causing text to appear blurry.
        """
        layer = self.layer()
        if not layer:
            return
        window = self.window()
        if window:
            scale = window.backingScaleFactor()
        else:
            # Fallback: use main screen scale before window is available
            from AppKit import NSScreen  # type: ignore[import]
            screen = NSScreen.mainScreen()
            scale = screen.backingScaleFactor() if screen else 2.0
        layer.setContentsScale_(scale)
        layer.setOpaque_(True)

    def setFrameSize_(self, newSize: object) -> None:
        objc.super(TerminalView, self).setFrameSize_(newSize)
        if not hasattr(self, "_renderer") or not self._renderer:
            return
        cw, ch = self._renderer.get_cell_dimensions()
        if cw <= 0 or ch <= 0:
            return
        new_cols = max(1, int((newSize.width - TERMINAL_PADDING_X * 2) / cw))
        new_rows = max(1, int((newSize.height - TERMINAL_PADDING_Y * 2) / ch))
        # Buffer resizes immediately (correct rendering). PTY SIGWINCH is
        # debounced so the shell only redraws once after drag settles.
        if hasattr(self, "_session") and self._session:
            if new_cols != self._session.cols or new_rows != self._session.rows:
                self._session.resize(new_cols, new_rows)
                self._schedule_pty_resize(new_cols, new_rows)
        self.setNeedsDisplay_(True)

    def _schedule_pty_resize(self, cols: int, rows: int) -> None:
        """Debounce PTY resize — only send SIGWINCH 150ms after last change."""
        if hasattr(self, "_resize_timer") and self._resize_timer:
            self._resize_timer.invalidate()
        self._pending_cols = cols
        self._pending_rows = rows
        self._resize_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.15, self, b"_firePtyResize:", None, False
        )

    def _firePtyResize_(self, timer: object) -> None:
        """Timer callback — send debounced SIGWINCH to the shell."""
        self._resize_timer = None
        if hasattr(self, "_session") and self._session:
            self._session.resize_pty(self._pending_cols, self._pending_rows)

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

    def insertText_(self, string: object) -> None:
        """NSResponder insertText: — called by interpretKeyEvents_ for regular chars."""
        from Foundation import NSMakeRange  # type: ignore[import]
        TerminalViewInputMixin.insertText_replacementRange_(
            self, string, NSMakeRange(NSNotFound, 0)
        )

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
        # Special keys (Return, Tab, Backspace, arrows) ALWAYS go directly to PTY.
        # If IME is composing, COMMIT composed text first, then send the special key.
        keycode = event.keyCode()
        if keycode in KEY_MAP:
            if self.hasMarkedText():
                # Backspace during composition: let IME shorten the marked text
                # (e.g. "việ" + backspace → "vi") instead of committing + sending DEL.
                if keycode == 0x33:  # Backspace
                    ic = self.inputContext()
                    if ic:
                        ic.handleEvent_(event)
                        return
                # Other special keys: commit marked text then send the key.
                if self._marked_text:
                    self._session.write(normalize_text(self._marked_text).encode("utf-8"))
                self._marked_text = None
                self._marked_range = (NSNotFound, 0)
                ic = self.inputContext()
                if ic:
                    ic.discardMarkedText()
            self._session.write(KEY_MAP[keycode])
            return
        # Route through NSTextInputContext for proper IME composition lifecycle.
        ic = self.inputContext()
        if ic:
            ic.handleEvent_(event)
        else:
            # interpretKeyEvents_ bypasses IME composition — only safe for ASCII.
            # When inputContext is None, send characters directly to PTY with
            # NFC normalization instead (avoids character loss for Vietnamese).
            chars = event.characters()
            if chars:
                self._session.write(normalize_text(str(chars)).encode("utf-8"))

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
