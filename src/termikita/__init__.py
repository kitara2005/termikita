"""Termikita - Native macOS terminal emulator with full Unicode/Vietnamese support."""

__version__ = "0.1.7"
__author__ = "Termikita"


def main() -> None:
    """Launch the Termikita terminal emulator."""
    from AppKit import NSApplication, NSApplicationActivationPolicyRegular  # type: ignore[import]
    from termikita.app_delegate import AppDelegate

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
