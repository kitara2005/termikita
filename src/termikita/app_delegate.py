"""NSApplicationDelegate for Termikita — bootstraps the app on launch.

Wires together ConfigManager, ThemeManager, MainWindow, and TabController,
builds the macOS menu bar, and opens the first terminal tab.
Handles Finder "Open Here" via application:openFile: for folder paths.
"""

import os
import sys

import objc  # type: ignore[import]
from AppKit import (  # type: ignore[import]
    NSObject,
    NSApp,
    NSMenu,
    NSMenuItem,
    NSApplication,
)
from Foundation import NSAppleEventManager  # type: ignore[import]

from termikita.constants import APP_NAME
from termikita.config_manager import ConfigManager
from termikita.theme_manager import ThemeManager
from termikita.tab_controller import TabController
from termikita.main_window import MainWindow


class AppDelegate(NSObject):
    """Application delegate — entry point for the Cocoa event loop."""

    def applicationDidFinishLaunching_(self, notification: object) -> None:
        """Bootstrap config, themes, window, tab controller, and menu."""
        # Register Apple Event handler for 'open document' (odoc) events.
        # PyObjC doesn't auto-dispatch these to application:openFile: reliably.
        try:
            aem = NSAppleEventManager.sharedAppleEventManager()
            aem.setEventHandler_andSelector_forEventClass_andEventID_(
                self, "handleOpenDocumentEvent:withReplyEvent:",
                int.from_bytes(b"aevt", "big"),  # kCoreEventClass
                int.from_bytes(b"odoc", "big"),   # kAEOpenDocuments
            )
            # Also register URL scheme handler (termikita://)
            aem.setEventHandler_andSelector_forEventClass_andEventID_(
                self, "handleGetURLEvent:withReplyEvent:",
                int.from_bytes(b"GURL", "big"),  # kInternetEventClass
                int.from_bytes(b"GURL", "big"),   # kAEGetURL
            )
        except Exception:
            pass

        # --- Preferences & theme ---
        self._config = ConfigManager()
        self._theme_mgr = ThemeManager()
        self._theme_mgr.set_theme(self._config.theme)
        self._theme_colors = self._theme_mgr.get_active_theme()

        # Track all open windows: list of (MainWindow, TabController) pairs
        self._windows: list[tuple[MainWindow, TabController]] = []
        # Flag: set True when Services/odoc/GURL handler opens content
        self._external_open_handled = False

        # --- First window ---
        main_win, tab_ctrl = self._create_window()
        self._windows.append((main_win, tab_ctrl))
        # Keep references for compatibility (Services handlers, default tab, etc.)
        self._main_window = main_win
        self._tab_ctrl = tab_ctrl

        # --- Menu bar ---
        self._setup_menu_bar()

        # --- Register as NSServices provider ---
        NSApp.setServicesProvider_(self)

        # --- Show window & activate app ---
        self._main_window.show()
        NSApp.activateIgnoringOtherApps_(True)

        # Defer default tab — give Services/odoc/GURL handlers a chance to open
        # their own tab first. If no tab was opened after a short delay, open default.
        start_dir = _parse_start_dir()
        if start_dir:
            # Explicit --dir arg: open immediately
            self._tab_ctrl.add_tab(working_dir=start_dir)
        else:
            # Delay default tab so Services handler can run first
            self.performSelector_withObject_afterDelay_(
                "openDefaultTabIfNeeded", None, 0.5
            )

    def _create_window(self) -> tuple[MainWindow, TabController]:
        """Create a new MainWindow + TabController pair.

        The TabController gets an on_last_tab_closed callback so it closes
        its window (instead of terminating the app) when the last tab exits.
        """
        win = MainWindow(self._config.window_width, self._config.window_height)

        # Cascade new windows so they don't stack exactly on top of each other
        if self._windows:
            offset = len(self._windows) * 22
            frame = win.window.frame()
            win.window.setFrameOrigin_((frame.origin.x + offset, frame.origin.y - offset))

        tab_ctrl = TabController(
            win.content_view,
            win.tab_bar,
            self._theme_colors,
            config=self._config,
        )
        # Wire up the "last tab closed" callback to close the window
        tab_ctrl._on_last_tab_closed = lambda tc=tab_ctrl, w=win: self._close_window(w, tc)
        return win, tab_ctrl

    def _close_window(self, win: MainWindow, tab_ctrl: TabController) -> None:
        """Remove a window from tracking and close it. Quit if last window."""
        pair = (win, tab_ctrl)
        if pair in self._windows:
            self._windows.remove(pair)
        win.window.close()
        # Update convenience refs to the frontmost remaining window
        if self._windows:
            self._main_window, self._tab_ctrl = self._windows[-1]
        else:
            NSApp.terminate_(None)

    def _active_tab_ctrl(self) -> TabController:
        """Return the TabController for the currently key window."""
        key_win = NSApp.keyWindow()
        if key_win is not None:
            for win, tc in self._windows:
                if win.window == key_win:
                    return tc
        # Fallback to first window's controller
        return self._tab_ctrl

    def openDefaultTabIfNeeded(self):
        """Open default $HOME tab only if no tab was opened by event handlers."""
        if self._external_open_handled:
            # External handler opened content — close the empty default window
            # if it has no tabs (e.g. Services opened a separate new window)
            first_win, first_tc = self._windows[0]
            if len(first_tc.tabs) == 0:
                self._windows.remove((first_win, first_tc))
                first_win.window.close()
                if self._windows:
                    self._main_window, self._tab_ctrl = self._windows[-1]
            return
        if len(self._tab_ctrl.tabs) == 0:
            self._tab_ctrl.add_tab(working_dir=os.path.expanduser("~"))

    def handleOpenDocumentEvent_withReplyEvent_(self, event, reply):
        """Handle 'odoc' Apple Event — open folder in new tab."""
        from Foundation import NSAppleEventDescriptor  # type: ignore[import]
        direct_obj = event.paramDescriptorForKeyword_(int.from_bytes(b"----", "big"))
        if direct_obj is None:
            return
        count = direct_obj.numberOfItems()
        for i in range(1, count + 1):
            desc = direct_obj.descriptorAtIndex_(i)
            url = desc.fileURLValue() if desc else None
            if url:
                path = url.path()
                if os.path.isdir(path):
                    self._external_open_handled = True
                    self._tab_ctrl.add_tab(working_dir=path)
        NSApp.activateIgnoringOtherApps_(True)

    def handleGetURLEvent_withReplyEvent_(self, event, reply):
        """Handle termikita:// URL scheme via Apple Event (fallback)."""
        direct_obj = event.paramDescriptorForKeyword_(int.from_bytes(b"----", "big"))
        if direct_obj is None:
            return
        url_str = direct_obj.stringValue()
        self._open_termikita_url(url_str)

    def application_openURLs_(self, app, urls):
        """Handle termikita:// URL scheme (modern delegate method).

        Called by NSApplication after launch — no race condition.
        URL format: termikita:///path/to/folder
        """
        for url in urls:
            self._open_termikita_url(str(url.absoluteString()))

    def _open_termikita_url(self, url_str):
        """Parse termikita:// URL and open folder in new tab."""
        if not url_str or not url_str.startswith("termikita://"):
            return
        from urllib.parse import unquote
        # Extract path: termikita:///path → /path
        path = unquote(url_str[len("termikita://"):])
        if os.path.isdir(path):
            self._external_open_handled = True
            self._tab_ctrl.add_tab(working_dir=path)
            NSApp.activateIgnoringOtherApps_(True)

    # ------------------------------------------------------------------
    # NSServices handler — "New Termikita Tab Here" in Finder context menu
    # ------------------------------------------------------------------

    @objc.typedSelector(b"v@:@@o^@")
    def newTermikitaTabHere_userData_error_(self, pboard, userData, error):
        """Handle Finder Services 'New Termikita Tab Here'.

        Called by macOS when user right-clicks folder → Services → New Termikita Tab Here.
        Reads file paths from pasteboard and opens a new tab for each directory.
        Returns None on success, error string on failure (PyObjC convention for error: out param).
        """
        try:
            paths = pboard.propertyListForType_("NSFilenamesPboardType")
            if not paths:
                return
            for path in paths:
                path = str(path)
                if os.path.isdir(path):
                    self._external_open_handled = True
                    self._tab_ctrl.add_tab(working_dir=path)
            NSApp.activateIgnoringOtherApps_(True)
        except Exception as e:
            return str(e)

    @objc.typedSelector(b"v@:@@o^@")
    def newTermikitaWindowHere_userData_error_(self, pboard, userData, error):
        """Handle Finder Services 'New Termikita Window Here'.

        Opens a new Termikita window at the selected folder.
        """
        try:
            paths = pboard.propertyListForType_("NSFilenamesPboardType")
            if not paths:
                return
            first_dir = None
            for path in paths:
                path = str(path)
                if os.path.isdir(path):
                    first_dir = path
                    break
            if first_dir:
                self._external_open_handled = True
                win, tc = self._create_window()
                self._windows.append((win, tc))
                tc.add_tab(working_dir=first_dir)
                win.show()
            NSApp.activateIgnoringOtherApps_(True)
        except Exception as e:
            return str(e)

    def applicationShouldTerminateAfterLastWindowClosed_(self, app: object) -> bool:
        """Quit the app when the last window is closed."""
        return True

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _setup_menu_bar(self) -> None:
        """Build the macOS menu bar with standard application shortcuts."""
        main_menu = NSMenu.alloc().init()

        # App menu (auto-assigned by macOS to the first item)
        app_menu = NSMenu.alloc().initWithTitle_(APP_NAME)
        app_menu.addItemWithTitle_action_keyEquivalent_(
            "About " + APP_NAME, "orderFrontStandardAboutPanel:", ""
        )
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_(
            "Quit " + APP_NAME, "terminate:", "q"
        )
        app_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            APP_NAME, None, ""
        )
        app_item.setSubmenu_(app_menu)
        main_menu.addItem_(app_item)

        # Shell menu — tab and window management
        shell_menu = NSMenu.alloc().initWithTitle_("Shell")
        shell_menu.addItemWithTitle_action_keyEquivalent_(
            "New Window", "newWindow:", "n"
        )
        shell_menu.addItemWithTitle_action_keyEquivalent_(
            "New Tab", "newTab:", "t"
        )
        shell_menu.addItem_(NSMenuItem.separatorItem())
        shell_menu.addItemWithTitle_action_keyEquivalent_(
            "Close Tab", "closeTab:", "w"
        )
        shell_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Shell", None, ""
        )
        shell_item.setSubmenu_(shell_menu)
        main_menu.addItem_(shell_item)

        # Edit menu — clipboard + selection
        # Delegate strips system-injected items (Writing Tools, AutoFill, etc.)
        edit_menu = NSMenu.alloc().initWithTitle_("Edit")
        edit_menu.setDelegate_(self)
        self._edit_menu = edit_menu
        self._populate_edit_menu(edit_menu)
        edit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Edit", None, ""
        )
        edit_item.setSubmenu_(edit_menu)
        main_menu.addItem_(edit_item)

        # View menu — font zoom + theme picker
        view_menu = NSMenu.alloc().initWithTitle_("View")
        view_menu.addItemWithTitle_action_keyEquivalent_("Bigger", "zoomIn:", "=")
        view_menu.addItemWithTitle_action_keyEquivalent_("Smaller", "zoomOut:", "-")
        view_menu.addItemWithTitle_action_keyEquivalent_("Default Size", "zoomReset:", "0")
        view_menu.addItem_(NSMenuItem.separatorItem())
        # Theme submenu — dynamically lists available themes with checkmark
        theme_submenu = NSMenu.alloc().initWithTitle_("Theme")
        theme_submenu.setDelegate_(self)
        self._theme_menu = theme_submenu  # keep ref for dynamic rebuild
        self._rebuild_theme_menu()
        theme_holder = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Theme", None, ""
        )
        theme_holder.setSubmenu_(theme_submenu)
        view_menu.addItem_(theme_holder)
        view_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "View", None, ""
        )
        view_item.setSubmenu_(view_menu)
        main_menu.addItem_(view_item)

        # Format menu — font panel
        format_menu = NSMenu.alloc().initWithTitle_("Format")
        font_submenu = NSMenu.alloc().initWithTitle_("Font")
        font_submenu.addItemWithTitle_action_keyEquivalent_(
            "Show Fonts", "orderFrontFontPanel:", ""
        )
        font_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Font", None, ""
        )
        font_item.setSubmenu_(font_submenu)
        format_menu.addItem_(font_item)
        format_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Format", None, ""
        )
        format_item.setSubmenu_(format_menu)
        main_menu.addItem_(format_item)

        # Window menu — standard window controls
        window_menu = NSMenu.alloc().initWithTitle_("Window")
        window_menu.addItemWithTitle_action_keyEquivalent_(
            "Minimize", "performMiniaturize:", "m"
        )
        window_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Window", None, ""
        )
        window_item.setSubmenu_(window_menu)
        main_menu.addItem_(window_item)

        NSApp.setMainMenu_(main_menu)

    # ------------------------------------------------------------------
    # Menu action handlers
    # ------------------------------------------------------------------

    @objc.IBAction
    def newWindow_(self, sender: object) -> None:
        """Cmd+N — open a new terminal window."""
        win, tc = self._create_window()
        self._windows.append((win, tc))
        tc.add_tab()
        win.show()
        # Update convenience refs to the new window
        self._main_window = win
        self._tab_ctrl = tc

    @objc.IBAction
    def newTab_(self, sender: object) -> None:
        """Cmd+T — open a new terminal tab in the active window."""
        self._active_tab_ctrl().add_tab()

    @objc.IBAction
    def closeTab_(self, sender: object) -> None:
        """Cmd+W — close the currently active tab."""
        tc = self._active_tab_ctrl()
        tc.close_tab(tc.active_tab_index)

    @objc.IBAction
    def zoomIn_(self, sender: object) -> None:
        """Cmd+= — increase font size."""
        self._active_tab_ctrl().zoom_in()

    @objc.IBAction
    def zoomOut_(self, sender: object) -> None:
        """Cmd+- — decrease font size."""
        self._active_tab_ctrl().zoom_out()

    @objc.IBAction
    def zoomReset_(self, sender: object) -> None:
        """Cmd+0 — reset font size to default."""
        self._active_tab_ctrl().zoom_reset()

    # ------------------------------------------------------------------
    # Edit menu — strip system-injected items
    # ------------------------------------------------------------------

    def _populate_edit_menu(self, menu: object) -> None:
        """Add only our Edit menu items (Copy, Paste, Select All)."""
        menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
        menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
        menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")

    def menuNeedsUpdate_(self, menu: object) -> None:
        """Rebuild Edit menu to strip Writing Tools, AutoFill, Dictation, etc."""
        if menu is not getattr(self, "_edit_menu", None):
            return
        menu.removeAllItems()
        self._populate_edit_menu(menu)

    # ------------------------------------------------------------------
    # Theme picker
    # ------------------------------------------------------------------

    def _rebuild_theme_menu(self) -> None:
        """Populate theme submenu with available themes, checkmark on active."""
        menu = self._theme_menu
        menu.removeAllItems()
        active = self._config.theme
        for name in self._theme_mgr.get_theme_names():
            # Human-readable label: "default-dark" → "Default Dark"
            label = name.replace("-", " ").title()
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                label, "selectTheme:", ""
            )
            item.setRepresentedObject_(name)
            item.setTarget_(self)
            if name == active:
                from AppKit import NSOnState  # type: ignore[import]
                item.setState_(NSOnState)
            menu.addItem_(item)

    def selectTheme_(self, sender: object) -> None:
        """Handle theme selection from View → Theme submenu."""
        name = sender.representedObject()
        if not name:
            return
        colors = self._theme_mgr.set_theme(name)
        self._theme_colors = colors
        self._config.set("theme", name)
        self._config.save()
        # Apply to all windows
        for _win, tc in self._windows:
            tc.set_theme(colors)
        self._rebuild_theme_menu()


def _parse_start_dir() -> str | None:
    """Extract --dir <path> from sys.argv if present."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--dir" and i + 1 < len(args):
            path = args[i + 1]
            return path if os.path.isdir(path) else None
        # Also accept a bare directory path as first argument
        if i == 0 and os.path.isdir(arg):
            return arg
    return None
