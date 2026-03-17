"""Multi-tab terminal management for Termikita.

TabController owns a list of TabItems and orchestrates which TerminalView is
visible in the content NSView. A TabBarView sits above the content area.

The controller does NOT own the NSWindow — it receives content_view + tab_bar
from the app delegate (Phase 09).

Public interface:
    add_tab()             — Cmd+T
    close_tab(index)      — Cmd+W
    select_tab(index)     — Cmd+1-9
    next_tab()            — Cmd+Shift+]
    prev_tab()            — Cmd+Shift+[
    get_active_session()  — current TerminalSession
    get_active_view()     — current TerminalView
    flush_pending_closes()— call from main-thread timer to process exited tabs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from termikita.terminal_session import TerminalSession
from termikita.terminal_view import TerminalView
from termikita.text_renderer import TextRenderer
from termikita.constants import (
    DEFAULT_COLS,
    DEFAULT_ROWS,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_SCROLLBACK,
)

TAB_BAR_HEIGHT: float = 28.0

# Font zoom bounds and step (points)
_FONT_SIZE_MIN = 8.0
_FONT_SIZE_MAX = 36.0
_FONT_SIZE_STEP = 1.0

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


@dataclass
class TabItem:
    """One terminal tab: session + view + display title."""
    session: TerminalSession
    view: TerminalView
    title: str = "Terminal"


class TabController:
    """Manages a list of TabItems, swaps views in content_view on tab switch."""

    def __init__(
        self,
        content_view: object,
        tab_bar_view: object,
        theme_colors: Optional[dict] = None,
        on_title_change: Optional[object] = None,
        config: Optional[object] = None,
    ) -> None:
        self._content_view = content_view
        self._tab_bar = tab_bar_view
        self._theme_colors = theme_colors or DEFAULT_THEME
        self._on_window_title_change = on_title_change
        self._on_last_tab_closed: object = None  # callback when last tab closes
        self._pending_close_indices: list[int] = []
        self._config = config  # ConfigManager for persisting font/settings

        self.tabs: list[TabItem] = []
        self.active_tab_index: int = -1

        if self._tab_bar is not None:
            self._tab_bar._controller = self

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tab(self, working_dir: str | None = None) -> TabItem:
        """Create a new terminal tab and make it active.

        Args:
            working_dir: Optional starting directory for the shell process.
        """
        renderer = TextRenderer()
        # Use config font if available, otherwise fall back to constants
        font_family = self._config.font_family if self._config else DEFAULT_FONT_FAMILY
        font_size = self._config.font_size if self._config else DEFAULT_FONT_SIZE
        renderer.set_font(font_family, font_size)
        cols, rows = self._grid_size(renderer)

        # Read shell and scrollback from config if available
        shell = self._config.shell if self._config else ""
        scrollback = self._config.scrollback_lines if self._config else DEFAULT_SCROLLBACK
        session = TerminalSession(
            cols=cols,
            rows=rows,
            on_output_callback=None,
            on_title_change=self._on_tab_title_change,
            on_exit=self._on_tab_exit,
            on_activity=_request_user_attention,
            working_dir=working_dir,
            shell=shell or None,
            scrollback_lines=scrollback,
        )

        from AppKit import NSViewWidthSizable, NSViewHeightSizable  # type: ignore[import]

        bounds = self._content_view.bounds()
        view = TerminalView.alloc().initWithFrame_(bounds)
        view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

        # initWithFrame_ auto-creates an internal session; replace it with ours
        # so the controller owns session lifetime.
        _stop_view_timers(view)
        if hasattr(view, "_session") and view._session is not None:
            view._session.shutdown()
        view._session = session
        view._renderer = renderer
        view._theme_colors = self._theme_colors
        _start_view_timers(view)
        view.setNeedsDisplay_(True)

        # Wire font change callback for NSFontPanel integration
        view._on_font_change = lambda fam, sz: self.set_font(fam, sz)

        tab = TabItem(session=session, view=view, title="Terminal")
        self.tabs.append(tab)
        self.select_tab(len(self.tabs) - 1)
        return tab

    def close_tab(self, index: int) -> None:
        """Shutdown and remove tab at index. Quits app when last tab closed."""
        if index < 0 or index >= len(self.tabs):
            return

        tab = self.tabs[index]
        _stop_view_timers(tab.view)
        try:
            tab.session.shutdown()
        except Exception:
            pass
        tab.view._session = None
        tab.view._on_font_change = None  # break reference cycle
        tab.view.removeFromSuperview()
        self.tabs.pop(index)

        if not self.tabs:
            # Last tab closed — notify owner to close the window
            if self._on_last_tab_closed is not None:
                self._on_last_tab_closed()
            else:
                # Fallback: quit if no callback registered
                try:
                    from AppKit import NSApp  # type: ignore[import]
                    NSApp.terminate_(None)
                except Exception:
                    pass
            return

        new_active = min(self.active_tab_index, len(self.tabs) - 1)
        self.active_tab_index = -1  # reset so select_tab re-adds subview
        self.select_tab(new_active)

    def select_tab(self, index: int) -> None:
        """Show tab at index, hide previous active view."""
        if index < 0 or index >= len(self.tabs):
            return

        if 0 <= self.active_tab_index < len(self.tabs):
            self.tabs[self.active_tab_index].view.removeFromSuperview()

        self.active_tab_index = index
        tab = self.tabs[index]
        tab.view.setFrame_(self._content_view.bounds())
        self._content_view.addSubview_(tab.view)

        win = self._content_view.window()
        if win is not None:
            win.makeFirstResponder_(tab.view)

        self._update_window_title()
        self._refresh_tab_bar()

    def next_tab(self) -> None:
        if self.tabs:
            self.select_tab((self.active_tab_index + 1) % len(self.tabs))

    def prev_tab(self) -> None:
        if self.tabs:
            self.select_tab((self.active_tab_index - 1) % len(self.tabs))

    def get_active_session(self) -> Optional[TerminalSession]:
        if 0 <= self.active_tab_index < len(self.tabs):
            return self.tabs[self.active_tab_index].session
        return None

    def get_active_view(self) -> Optional[TerminalView]:
        if 0 <= self.active_tab_index < len(self.tabs):
            return self.tabs[self.active_tab_index].view
        return None

    def close_other_tabs(self, keep_index: int) -> None:
        """Close all tabs except the one at keep_index. Single select_tab at end."""
        if keep_index < 0 or keep_index >= len(self.tabs):
            return
        kept_tab = self.tabs[keep_index]
        # Teardown all other tabs without triggering select_tab each time
        for i, tab in enumerate(self.tabs):
            if i != keep_index:
                _stop_view_timers(tab.view)
                try:
                    tab.session.shutdown()
                except Exception:
                    pass
                tab.view._session = None
                tab.view.removeFromSuperview()
        self.tabs = [kept_tab]
        self.active_tab_index = -1
        self.select_tab(0)

    def set_font(self, family: str, size: float) -> None:
        """Update font for all tabs, recalculate metrics, resize PTYs, persist."""
        if self._config:
            self._config.set("font_family", family)
            self._config.set("font_size", size)
            self._config.save()
        from termikita.cell_draw_helpers import invalidate_glyph_cache
        invalidate_glyph_cache()
        for tab in self.tabs:
            tab.view._renderer.set_font(family, size)
            # Trigger frame recalculation which handles PTY resize
            tab.view.setFrameSize_(tab.view.frame().size)
        # Update NSFontManager selected font for font panel sync
        try:
            from AppKit import NSFontManager  # type: ignore[import]
            active_view = self.get_active_view()
            if active_view and active_view._renderer.primary_font:
                fm = NSFontManager.sharedFontManager()
                fm.setSelectedFont_isMultiple_(active_view._renderer.primary_font, False)
        except Exception:
            pass

    def zoom_in(self) -> None:
        """Increase font size by 1pt (Cmd+=)."""
        current = self._config.font_size if self._config else DEFAULT_FONT_SIZE
        new_size = min(current + _FONT_SIZE_STEP, _FONT_SIZE_MAX)
        family = self._config.font_family if self._config else DEFAULT_FONT_FAMILY
        self.set_font(family, new_size)

    def zoom_out(self) -> None:
        """Decrease font size by 1pt (Cmd+-)."""
        current = self._config.font_size if self._config else DEFAULT_FONT_SIZE
        new_size = max(current - _FONT_SIZE_STEP, _FONT_SIZE_MIN)
        family = self._config.font_family if self._config else DEFAULT_FONT_FAMILY
        self.set_font(family, new_size)

    def zoom_reset(self) -> None:
        """Reset font size to default (Cmd+0)."""
        from termikita.config_manager import DEFAULTS
        family = self._config.font_family if self._config else DEFAULT_FONT_FAMILY
        self.set_font(family, DEFAULTS["font_size"])

    def set_theme(self, theme_colors: dict) -> None:
        """Push a new theme to all existing tabs."""
        self._theme_colors = theme_colors
        for tab in self.tabs:
            tab.view._theme_colors = theme_colors
            tab.view.setNeedsDisplay_(True)

    def handle_content_resize(self) -> None:
        """Call after window resize to update active view frame."""
        if 0 <= self.active_tab_index < len(self.tabs):
            self.tabs[self.active_tab_index].view.setFrame_(
                self._content_view.bounds()
            )

    def flush_pending_closes(self) -> None:
        """Close tabs that exited. Call from main-thread timer (e.g. 60 fps refresh)."""
        if not self._pending_close_indices:
            return
        for idx in sorted(set(self._pending_close_indices), reverse=True):
            if 0 <= idx < len(self.tabs) and not self.tabs[idx].session.is_alive:
                self.close_tab(idx)
        self._pending_close_indices.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _grid_size(self, renderer: TextRenderer) -> tuple[int, int]:
        try:
            bounds = self._content_view.bounds()
            cw, ch = renderer.get_cell_dimensions()
            if cw > 0 and ch > 0:
                return (
                    max(1, int(bounds.size.width / cw)),
                    max(1, int(bounds.size.height / ch)),
                )
        except Exception:
            pass
        return DEFAULT_COLS, DEFAULT_ROWS

    def _update_window_title(self) -> None:
        try:
            session = self.get_active_session()
            title = (session.title if session else "") or "Termikita"
            win = self._content_view.window()
            if win is not None:
                win.setTitle_(title)
            if self._on_window_title_change is not None:
                self._on_window_title_change(title)
        except Exception:
            pass

    def _refresh_tab_bar(self) -> None:
        if self._tab_bar is not None:
            try:
                self._tab_bar.setNeedsDisplay_(True)
            except Exception:
                pass

    def _on_tab_title_change(self, new_title: str) -> None:
        """PTY thread callback — update tab.title and window title."""
        for tab in self.tabs:
            if tab.session.title == new_title:
                tab.title = new_title or "Terminal"
                break
        active = self.get_active_session()
        if active and active.title == new_title:
            self._update_window_title()
        self._refresh_tab_bar()

    def _on_tab_exit(self, exit_code: int) -> None:
        """PTY thread callback — queue tab index for main-thread close."""
        for i, tab in enumerate(self.tabs):
            if not tab.session.is_alive:
                self._pending_close_indices.append(i)
                break


# ------------------------------------------------------------------
# Module-level helpers (keep TabController under 200 lines)
# ------------------------------------------------------------------

def _stop_view_timers(view: TerminalView) -> None:
    """Invalidate refresh and cursor-blink timers on a TerminalView."""
    try:
        if getattr(view, "_refresh_timer", None):
            view._refresh_timer.invalidate()
            view._refresh_timer = None
        if getattr(view, "_cursor_blink_timer", None):
            view._cursor_blink_timer.invalidate()
            view._cursor_blink_timer = None
    except Exception:
        pass


def _start_view_timers(view: TerminalView) -> None:
    """Restart timers on a TerminalView after session replacement."""
    try:
        if hasattr(view, "_start_timers"):
            view._start_timers()
    except Exception:
        pass


from AppKit import NSObject, NSApp, NSCriticalRequest  # type: ignore[import]


class _DockBouncer(NSObject):
    """Dispatch dock bounce + macOS notification to main thread.

    NSApp.requestUserAttention_ must be called from the main thread for
    reliable behavior. This helper bridges PTY read thread → main thread.
    """

    def bounce_(self, _sender: object) -> None:
        try:
            if not NSApp.isActive():
                # Continuous bounce until user clicks dock icon
                NSApp.requestUserAttention_(NSCriticalRequest)
                _post_notification()
        except Exception:
            pass


# Singleton bouncer — created once, reused for all notifications
_bouncer = _DockBouncer.alloc().init()


def _post_notification() -> None:
    """Post a macOS notification banner via NSUserNotification."""
    try:
        from Foundation import (  # type: ignore[import]
            NSUserNotification,
            NSUserNotificationCenter,
        )
        notif = NSUserNotification.alloc().init()
        notif.setTitle_("Termikita")
        notif.setInformativeText_("Command completed")
        notif.setSoundName_(None)  # silent — dock bounce is enough audio cue
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        center.deliverNotification_(notif)
    except Exception:
        pass


def _request_user_attention() -> None:
    """Bounce dock icon + show notification when a command likely finished.

    Called from PTY read thread — dispatch to main thread for reliable
    NSApp.isActive() and requestUserAttention_ behavior.
    """
    try:
        _bouncer.performSelectorOnMainThread_withObject_waitUntilDone_(
            "bounce:", None, False
        )
    except Exception:
        pass
