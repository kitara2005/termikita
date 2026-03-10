"""NSTextInputClient protocol methods and selection/clipboard helpers for TerminalView.

Imported as a mixin by terminal_view.py. Provides:
- Vietnamese IME support via NSTextInputClient methods
- Mouse selection tracking
- Copy/paste via NSPasteboard
- Select-all helper
"""

from __future__ import annotations

from AppKit import (  # type: ignore[import]
    NSMenu,
    NSMenuItem,
    NSApp,
)
from Foundation import NSNotFound, NSMakeRange  # type: ignore[import]


class TerminalViewInputMixin:
    """NSTextInputClient protocol + selection helpers.

    Mixed into TerminalView. Assumes self._session, self._renderer,
    self._marked_text, self._marked_range, self._selected_range,
    self._selection_start, self._selection_end are all defined by the host.
    """

    # ------------------------------------------------------------------
    # NSTextInputClient — required methods
    # ------------------------------------------------------------------

    def insertText_replacementRange_(self, string: object, replacementRange: object) -> None:
        """IME commits final composed text, or regular key character input."""
        self._marked_text = None
        self._marked_range = (NSNotFound, 0)
        text = str(string)
        if text:
            self._session.write(text.encode("utf-8"))
        self.setNeedsDisplay_(True)

    def setMarkedText_selectedRange_replacementRange_(
        self, string: object, selRange: object, replRange: object
    ) -> None:
        """Called while IME is composing — display but do NOT send to PTY."""
        self._marked_text = str(string) if string else None
        if self._marked_text:
            self._marked_range = (0, len(self._marked_text))
        else:
            self._marked_range = (NSNotFound, 0)
        self._selected_range = (selRange.location, selRange.length)
        self.setNeedsDisplay_(True)

    def unmarkText(self) -> None:
        """Cancel/commit any in-progress IME composition."""
        self._marked_text = None
        self._marked_range = (NSNotFound, 0)
        self.setNeedsDisplay_(True)

    def hasMarkedText(self) -> bool:
        return bool(self._marked_text)

    def markedRange(self) -> object:
        return NSMakeRange(self._marked_range[0], self._marked_range[1])

    def selectedRange(self) -> object:
        return NSMakeRange(self._selected_range[0], self._selected_range[1])

    def firstRectForCharacterRange_actualRange_(
        self, range_: object, actualRangePtr: object
    ) -> object:
        """Return screen rect for IME candidate window placement near cursor."""
        from Foundation import NSMakeRect  # type: ignore[import]

        cursor_row, cursor_col, _ = self._session.buffer.get_cursor()
        x = cursor_col * self._renderer.cell_width
        # isFlipped=True: y grows downward, so cursor top = row * cell_height
        y = cursor_row * self._renderer.cell_height
        rect = NSMakeRect(x, y, 0, self._renderer.cell_height)
        try:
            window_rect = self.convertRect_toView_(rect, None)
            return self.window().convertRectToScreen_(window_rect)
        except Exception:
            return rect

    def attributedSubstringForProposedRange_actualRange_(
        self, range_: object, actualRangePtr: object
    ) -> None:
        return None

    def characterIndexForPoint_(self, point: object) -> int:
        return 0

    def validAttributesForMarkedText(self) -> list:
        return []

    # ------------------------------------------------------------------
    # Mouse selection
    # ------------------------------------------------------------------

    def mouseDown_(self, event: object) -> None:
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        col = int(point.x / self._renderer.cell_width)
        row = int(point.y / self._renderer.cell_height)
        self._selection_start = (row, max(0, col))
        self._selection_end = None
        self.setNeedsDisplay_(True)

    def mouseDragged_(self, event: object) -> None:
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        col = int(point.x / self._renderer.cell_width)
        row = int(point.y / self._renderer.cell_height)
        self._selection_end = (row, max(0, col))
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event: object) -> None:
        # Collapse zero-length selection
        if self._selection_start == self._selection_end:
            self._selection_start = None
            self._selection_end = None
            self.setNeedsDisplay_(True)

    # ------------------------------------------------------------------
    # Clipboard helpers
    # ------------------------------------------------------------------

    def _copy_selection(self) -> None:
        """Copy selected text from buffer to the system clipboard."""
        if not self._selection_start or not self._selection_end:
            return
        lines = self._session.buffer.get_visible_lines()
        r0, c0 = self._selection_start
        r1, c1 = self._selection_end
        # Normalise so start <= end
        if (r0, c0) > (r1, c1):
            r0, c0, r1, c1 = r1, c1, r0, c0

        parts: list[str] = []
        for row in range(r0, r1 + 1):
            if row >= len(lines):
                break
            row_cells = lines[row]
            col_start = c0 if row == r0 else 0
            col_end = c1 if row == r1 else len(row_cells)
            segment = "".join(cell.char for cell in row_cells[col_start:col_end])
            parts.append(segment.rstrip())
        selected_text = "\n".join(parts)

        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString  # type: ignore[import]
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(selected_text, NSPasteboardTypeString)
        except Exception:
            pass

    def _paste_clipboard(self) -> None:
        """Paste clipboard text to PTY as UTF-8 bytes."""
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString  # type: ignore[import]
            pb = NSPasteboard.generalPasteboard()
            text = pb.stringForType_(NSPasteboardTypeString)
            if text:
                self._session.write(str(text).encode("utf-8"))
        except Exception:
            pass

    def _select_all(self) -> None:
        """Select all visible lines."""
        lines = self._session.buffer.get_visible_lines()
        if not lines:
            return
        self._selection_start = (0, 0)
        last_row = len(lines) - 1
        last_col = len(lines[last_row]) if lines[last_row] else 0
        self._selection_end = (last_row, last_col)
        self.setNeedsDisplay_(True)

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------

    def menuForEvent_(self, event: object) -> object:
        """Build and return context menu for right-click on terminal area."""
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        # Copy — disabled when no selection
        copy_item = menu.addItemWithTitle_action_keyEquivalent_("Copy", "contextCopy:", "")
        copy_item.setTarget_(self)
        has_selection = bool(self._selection_start and self._selection_end)
        copy_item.setEnabled_(has_selection)

        # Paste
        paste_item = menu.addItemWithTitle_action_keyEquivalent_("Paste", "contextPaste:", "")
        paste_item.setTarget_(self)

        # Select All
        sel_all_item = menu.addItemWithTitle_action_keyEquivalent_("Select All", "contextSelectAll:", "")
        sel_all_item.setTarget_(self)

        menu.addItem_(NSMenuItem.separatorItem())

        # Clear Buffer
        clear_item = menu.addItemWithTitle_action_keyEquivalent_("Clear Buffer", "contextClearBuffer:", "")
        clear_item.setTarget_(self)

        menu.addItem_(NSMenuItem.separatorItem())

        # New Tab / Close Tab — target the app delegate
        delegate = NSApp.delegate()
        new_tab = menu.addItemWithTitle_action_keyEquivalent_("New Tab", "newTab:", "")
        new_tab.setTarget_(delegate)

        close_tab = menu.addItemWithTitle_action_keyEquivalent_("Close Tab", "closeTab:", "")
        close_tab.setTarget_(delegate)

        return menu

    def contextCopy_(self, sender: object) -> None:
        self._copy_selection()

    def contextPaste_(self, sender: object) -> None:
        self._paste_clipboard()

    def contextSelectAll_(self, sender: object) -> None:
        self._select_all()

    def contextClearBuffer_(self, sender: object) -> None:
        """Send VT100 erase-screen + cursor-home to clear terminal buffer."""
        if self._session:
            self._session.write(b"\x1b[2J\x1b[H")
