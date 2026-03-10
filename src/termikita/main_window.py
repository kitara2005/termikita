"""Main application window for Termikita.

Creates and configures the NSWindow with a tab bar (28 px top strip) and a
content area that fills the remaining space.  Layout uses AppKit autoresizing
masks so resizing the window keeps proportions correct.
"""

from AppKit import (  # type: ignore[import]
    NSWindow,
    NSView,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSMakeSize,
    NSScreen,
    NSViewWidthSizable,
    NSViewHeightSizable,
    NSViewMinYMargin,
)

from termikita.constants import APP_NAME
from termikita.tab_bar_view import TabBarView

# Height of the tab strip in pixels — must match TabController.TAB_BAR_HEIGHT
TAB_BAR_HEIGHT: float = 28.0


class MainWindow:
    """Creates and configures the main application window.

    Attributes:
        window:       The underlying NSWindow instance.
        tab_bar:      The TabBarView sitting at the top of the window.
        content_view: The plain NSView that hosts TerminalView subviews.
    """

    def __init__(self, width: int, height: int) -> None:
        screen = NSScreen.mainScreen().frame()

        # Center window on screen
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2
        rect = NSMakeRect(x, y, width, height)

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_(APP_NAME)
        self.window.setMinSize_(NSMakeSize(400, 300))

        # ----------------------------------------------------------------
        # Build the subview hierarchy inside the window's content view
        # ----------------------------------------------------------------
        content = self.window.contentView()
        content_bounds = content.bounds()
        cw = content_bounds.size.width
        ch = content_bounds.size.height

        # --- Tab bar: anchored to top edge, full width, fixed height ---
        tab_bar_frame = NSMakeRect(0, ch - TAB_BAR_HEIGHT, cw, TAB_BAR_HEIGHT)
        self.tab_bar = TabBarView.alloc().initWithFrame_(tab_bar_frame)
        # Resize with window width; keep pinned to top (MinYMargin stays fixed)
        self.tab_bar.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin)
        content.addSubview_(self.tab_bar)

        # --- Content area: fills the rest (width + height flexible) ---
        content_frame = NSMakeRect(0, 0, cw, ch - TAB_BAR_HEIGHT)
        self.content_view = NSView.alloc().initWithFrame_(content_frame)
        self.content_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        content.addSubview_(self.content_view)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Bring the window to the front and make it key."""
        self.window.makeKeyAndOrderFront_(None)
