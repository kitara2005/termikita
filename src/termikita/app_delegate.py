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
)

from termikita.constants import APP_NAME
from termikita.config_manager import ConfigManager
from termikita.theme_manager import ThemeManager
from termikita.tab_controller import TabController
from termikita.main_window import MainWindow


class AppDelegate(NSObject):
    """Application delegate — entry point for the Cocoa event loop."""

    def applicationDidFinishLaunching_(self, notification: object) -> None:
        """Bootstrap config, themes, window, tab controller, and menu."""
        # --- Preferences & theme ---
        self._config = ConfigManager()
        self._theme_mgr = ThemeManager()
        self._theme_mgr.set_theme(self._config.theme)
        theme_colors = self._theme_mgr.get_active_theme()

        # --- Window ---
        self._main_window = MainWindow(
            self._config.window_width,
            self._config.window_height,
        )

        # --- Tab controller ---
        self._tab_ctrl = TabController(
            self._main_window.content_view,
            self._main_window.tab_bar,
            theme_colors,
        )

        # Check CLI --dir argument for starting directory
        start_dir = _parse_start_dir()

        # Open first terminal tab (with optional working directory)
        self._tab_ctrl.add_tab(working_dir=start_dir)

        # --- Menu bar ---
        self._setup_menu_bar()

        # --- Show window & activate app ---
        self._main_window.show()
        NSApp.activateIgnoringOtherApps_(True)

    def application_openFile_(self, app: object, path: str) -> bool:
        """Handle Finder "Open with Termikita" for folders.

        Called when a folder is dragged onto the dock icon or opened via
        Finder context menu Quick Action.
        """
        if os.path.isdir(path):
            self._tab_ctrl.add_tab(working_dir=path)
            NSApp.activateIgnoringOtherApps_(True)
            return True
        return False

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
        app_menu_item = NSMenuItem.alloc().init()
        app_menu_item.setSubmenu_(app_menu)
        main_menu.addItem_(app_menu_item)

        # Shell menu — tab management
        shell_menu = NSMenu.alloc().initWithTitle_("Shell")
        shell_menu.addItemWithTitle_action_keyEquivalent_(
            "New Tab", "newTab:", "t"
        )
        shell_menu.addItemWithTitle_action_keyEquivalent_(
            "Close Tab", "closeTab:", "w"
        )
        shell_menu_item = NSMenuItem.alloc().init()
        shell_menu_item.setSubmenu_(shell_menu)
        main_menu.addItem_(shell_menu_item)

        # Edit menu — clipboard + selection
        edit_menu = NSMenu.alloc().initWithTitle_("Edit")
        edit_menu.addItemWithTitle_action_keyEquivalent_(
            "Copy", "copy:", "c"
        )
        edit_menu.addItemWithTitle_action_keyEquivalent_(
            "Paste", "paste:", "v"
        )
        edit_menu.addItemWithTitle_action_keyEquivalent_(
            "Select All", "selectAll:", "a"
        )
        edit_menu_item = NSMenuItem.alloc().init()
        edit_menu_item.setSubmenu_(edit_menu)
        main_menu.addItem_(edit_menu_item)

        # Window menu — standard window controls
        window_menu = NSMenu.alloc().initWithTitle_("Window")
        window_menu.addItemWithTitle_action_keyEquivalent_(
            "Minimize", "performMiniaturize:", "m"
        )
        window_menu_item = NSMenuItem.alloc().init()
        window_menu_item.setSubmenu_(window_menu)
        main_menu.addItem_(window_menu_item)

        NSApp.setMainMenu_(main_menu)

    # ------------------------------------------------------------------
    # Menu action handlers
    # ------------------------------------------------------------------

    @objc.IBAction
    def newTab_(self, sender: object) -> None:
        """Cmd+T — open a new terminal tab."""
        self._tab_ctrl.add_tab()

    @objc.IBAction
    def closeTab_(self, sender: object) -> None:
        """Cmd+W — close the currently active tab."""
        self._tab_ctrl.close_tab(self._tab_ctrl.active_tab_index)


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
