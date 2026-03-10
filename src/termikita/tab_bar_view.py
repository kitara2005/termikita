"""Tab bar NSView for Termikita — renders clickable tab strip above terminal content.

Draws tab titles with active-tab highlight and a close (×) button per tab.
Communicates back to TabController via weak reference.
Height: 28 px (set by TabController).
"""

from __future__ import annotations

import objc  # type: ignore[import]
import AppKit
from AppKit import (  # type: ignore[import]
    NSView,
    NSColor,
    NSFont,
    NSBezierPath,
    NSString,
    NSMenu,
    NSMenuItem,
    NSMutableParagraphStyle,
    NSLineBreakByTruncatingTail,
    NSForegroundColorAttributeName,
    NSFontAttributeName,
    NSParagraphStyleAttributeName,
    NSTrackingArea,
    NSTrackingMouseMoved,
    NSTrackingActiveInKeyWindow,
    NSTrackingInVisibleRect,
)
from Foundation import NSMakeRect, NSMakePoint  # type: ignore[import]

# Layout constants
_TAB_MIN_WIDTH: float = 80.0
_TAB_MAX_WIDTH: float = 200.0
_CLOSE_AREA_WIDTH: float = 18.0   # px reserved at right of each tab for × button
_FONT_SIZE: float = 11.5
_BG_COLOR = (28, 28, 28)          # overall bar background
_ACTIVE_COLOR = (50, 50, 50)      # active tab background
_INACTIVE_COLOR = (36, 36, 36)    # inactive tab background
_HOVER_CLOSE_COLOR = (200, 70, 70)
_BORDER_COLOR = (60, 60, 60)
_TEXT_ACTIVE = (220, 220, 220)
_TEXT_INACTIVE = (140, 140, 140)


def _nscolor(rgb: tuple[int, int, int], alpha: float = 1.0) -> object:
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(
        rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha
    )


class TabBarView(NSView):
    """Horizontal tab strip — renders tabs with titles and close buttons."""

    # objc instance vars
    _controller = objc.ivar()       # weak ref to TabController (not retained)
    _hover_tab_index = objc.ivar()  # int or None — tab index under cursor
    _hover_close = objc.ivar()      # bool — cursor is over close area

    def initWithFrame_(self, frame: object) -> "TabBarView":
        self = objc.super(TabBarView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._controller = None
        self._hover_tab_index = -1
        self._hover_close = False
        self._pending_close_idx = -1
        self._context_menu_tab_index = -1
        # Tracking area added in viewDidMoveToWindow_ / updateTrackingAreas
        return self

    def updateTrackingAreas(self) -> None:
        """Rebuild tracking area whenever geometry changes."""
        # Remove old tracking areas
        for area in list(self.trackingAreas()):
            self.removeTrackingArea_(area)
        # Add new full-bounds tracking area for mouse-moved events
        opts = NSTrackingMouseMoved | NSTrackingActiveInKeyWindow | NSTrackingInVisibleRect
        area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), opts, self, None
        )
        self.addTrackingArea_(area)
        objc.super(TabBarView, self).updateTrackingAreas()

    # ------------------------------------------------------------------
    # NSView overrides
    # ------------------------------------------------------------------

    def isFlipped(self) -> bool:
        return True

    def acceptsFirstResponder(self) -> bool:
        return False  # let TerminalView keep focus

    def isOpaque(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def drawRect_(self, rect: object) -> None:
        """Render the full tab bar."""
        if self._controller is None:
            return

        bounds = self.bounds()
        bar_w = bounds.size.width
        bar_h = bounds.size.height

        # Background
        _nscolor(_BG_COLOR).setFill()
        NSBezierPath.fillRect_(bounds)

        tabs = self._controller.tabs
        if not tabs:
            return

        active_idx = self._controller.active_tab_index
        tab_w = self._tab_width(bar_w, len(tabs))
        font = NSFont.systemFontOfSize_(_FONT_SIZE)

        for i, tab in enumerate(tabs):
            x = i * tab_w
            is_active = (i == active_idx)

            # Tab background
            bg = _ACTIVE_COLOR if is_active else _INACTIVE_COLOR
            _nscolor(bg).setFill()
            NSBezierPath.fillRect_(NSMakeRect(x, 0, tab_w, bar_h))

            # Right border separator
            _nscolor(_BORDER_COLOR).setFill()
            NSBezierPath.fillRect_(NSMakeRect(x + tab_w - 1, 0, 1, bar_h))

            # Bottom border (active tab has no bottom line — merges with content)
            if not is_active:
                _nscolor(_BORDER_COLOR).setFill()
                NSBezierPath.fillRect_(NSMakeRect(x, bar_h - 1, tab_w, 1))

            # Close button
            close_x = x + tab_w - _CLOSE_AREA_WIDTH
            hover_this_close = (
                self._hover_tab_index == i and self._hover_close
            )
            close_color = _HOVER_CLOSE_COLOR if hover_this_close else (
                _TEXT_ACTIVE if is_active else _TEXT_INACTIVE
            )
            self._draw_close_button(close_x + 3, bar_h / 2, _nscolor(close_color))

            # Title text — left-aligned, truncated, right margin for close btn
            text_x = x + 8.0
            text_w = tab_w - 8.0 - _CLOSE_AREA_WIDTH
            text_color = _nscolor(_TEXT_ACTIVE if is_active else _TEXT_INACTIVE)
            self._draw_label(tab.title, text_x, 0, text_w, bar_h, font, text_color)

        # Bottom border line under entire bar
        _nscolor(_BORDER_COLOR).setFill()
        NSBezierPath.fillRect_(NSMakeRect(0, bar_h - 1, bar_w, 1))

    def _draw_close_button(self, cx: float, cy: float, color: object) -> None:
        """Draw × glyph centered at (cx, cy)."""
        r = 4.0
        color.setStroke()
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(1.5)
        path.moveToPoint_(NSMakePoint(cx - r, cy - r))
        path.lineToPoint_(NSMakePoint(cx + r, cy + r))
        path.moveToPoint_(NSMakePoint(cx + r, cy - r))
        path.lineToPoint_(NSMakePoint(cx - r, cy + r))
        path.stroke()

    def _draw_label(
        self,
        text: str,
        x: float,
        y: float,
        w: float,
        h: float,
        font: object,
        color: object,
    ) -> None:
        """Draw truncated title centred vertically in the tab."""
        try:
            para = NSMutableParagraphStyle.alloc().init()
            para.setLineBreakMode_(NSLineBreakByTruncatingTail)
            attrs = {
                NSForegroundColorAttributeName: color,
                NSFontAttributeName: font,
                NSParagraphStyleAttributeName: para,
            }
            ns_str = AppKit.NSString.stringWithString_(text)
            attr_str = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                ns_str, attrs
            )
            # Vertically centre
            text_h = attr_str.size().height
            ty = y + (h - text_h) / 2.0
            attr_str.drawInRect_(NSMakeRect(x, ty, w, text_h + 2))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mouseDown_(self, event: object) -> None:
        """Select tab or close tab on click."""
        if self._controller is None:
            return
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        tab_idx, on_close = self._hit_test(loc)
        if tab_idx < 0:
            return
        if on_close:
            # Defer close to next run loop iteration — calling close_tab
            # synchronously from mouseDown_ can deallocate this view while
            # the event handler is still on the call stack, causing a crash.
            self._pending_close_idx = tab_idx
            self.performSelector_withObject_afterDelay_(
                "deferredCloseTab:", None, 0.0
            )
        else:
            self._controller.select_tab(tab_idx)

    def deferredCloseTab_(self, sender: object) -> None:
        """Timer callback — close the tab that was queued by mouseDown_."""
        idx = getattr(self, "_pending_close_idx", -1)
        if idx >= 0 and self._controller is not None:
            self._controller.close_tab(idx)
        self._pending_close_idx = -1

    def mouseMoved_(self, event: object) -> None:
        """Update hover state for close button highlight."""
        if self._controller is None:
            return
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        tab_idx, on_close = self._hit_test(loc)
        changed = (self._hover_tab_index != tab_idx or self._hover_close != on_close)
        self._hover_tab_index = tab_idx
        self._hover_close = on_close
        if changed:
            self.setNeedsDisplay_(True)

    def mouseExited_(self, event: object) -> None:
        if self._hover_tab_index != -1 or self._hover_close:
            self._hover_tab_index = -1
            self._hover_close = False
            self.setNeedsDisplay_(True)

    # ------------------------------------------------------------------
    # Context menu (right-click on tab)
    # ------------------------------------------------------------------

    def menuForEvent_(self, event: object) -> object:
        """Build context menu for right-clicked tab."""
        if self._controller is None:
            return None
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        tab_idx, _ = self._hit_test(loc)
        if tab_idx < 0:
            return None
        self._context_menu_tab_index = tab_idx

        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        new_tab = menu.addItemWithTitle_action_keyEquivalent_("New Tab", "contextNewTab:", "")
        new_tab.setTarget_(self)

        close_tab = menu.addItemWithTitle_action_keyEquivalent_("Close Tab", "contextCloseTab:", "")
        close_tab.setTarget_(self)

        close_others = menu.addItemWithTitle_action_keyEquivalent_("Close Other Tabs", "contextCloseOtherTabs:", "")
        close_others.setTarget_(self)
        close_others.setEnabled_(len(self._controller.tabs) > 1)

        menu.addItem_(NSMenuItem.separatorItem())

        dup_tab = menu.addItemWithTitle_action_keyEquivalent_("Duplicate Tab", "contextDuplicateTab:", "")
        dup_tab.setTarget_(self)

        return menu

    def contextNewTab_(self, sender: object) -> None:
        if self._controller:
            self._controller.add_tab()

    def contextCloseTab_(self, sender: object) -> None:
        """Close the right-clicked tab (deferred to avoid crash)."""
        if self._controller:
            idx = self._context_menu_tab_index
            if 0 <= idx < len(self._controller.tabs):
                self._pending_close_idx = idx
                self.performSelector_withObject_afterDelay_("deferredCloseTab:", None, 0.0)

    def contextCloseOtherTabs_(self, sender: object) -> None:
        if self._controller:
            idx = self._context_menu_tab_index
            if 0 <= idx < len(self._controller.tabs):
                self._controller.close_other_tabs(idx)

    def contextDuplicateTab_(self, sender: object) -> None:
        if self._controller:
            self._controller.add_tab()

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _tab_width(self, bar_w: float, n: int) -> float:
        """Compute per-tab width clamped to [_TAB_MIN_WIDTH, _TAB_MAX_WIDTH]."""
        if n <= 0:
            return _TAB_MAX_WIDTH
        w = bar_w / n
        return max(_TAB_MIN_WIDTH, min(_TAB_MAX_WIDTH, w))

    def _hit_test(self, point: object) -> tuple[int, bool]:
        """Return (tab_index, on_close). tab_index=-1 if outside any tab."""
        if self._controller is None:
            return -1, False
        tabs = self._controller.tabs
        if not tabs:
            return -1, False
        bar_w = self.bounds().size.width
        bar_h = self.bounds().size.height
        tab_w = self._tab_width(bar_w, len(tabs))
        px = point.x
        py = point.y
        if py < 0 or py > bar_h:
            return -1, False
        idx = int(px / tab_w)
        if idx < 0 or idx >= len(tabs):
            return -1, False
        # Is point in the close-button region?
        close_x_start = idx * tab_w + tab_w - _CLOSE_AREA_WIDTH
        on_close = px >= close_x_start
        return idx, on_close
