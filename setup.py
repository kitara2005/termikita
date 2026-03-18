"""py2app build script for Termikita .app bundle.

py2app 0.28+ rejects install_requires on the distribution object, but
setuptools automatically populates it from pyproject.toml. We patch
py2app's build_app command to clear it before the validation check runs.
"""

import py2app.build_app as _build_app
from setuptools import setup

# Save the original finalize_options so we can wrap it
_orig_finalize = _build_app.py2app.finalize_options


def _patched_finalize(self):
    # Clear install_requires before py2app validates it
    if hasattr(self.distribution, "install_requires"):
        self.distribution.install_requires = []
    _orig_finalize(self)


_build_app.py2app.finalize_options = _patched_finalize

# Entry point for the application
APP = ["src/termikita/__main__.py"]

# Theme JSON files bundled into Resources/themes/
DATA_FILES = [
    (
        "themes",
        [
            "themes/default-dark.json",
            "themes/default-light.json",
            "themes/dracula.json",
            "themes/nord.json",
            "themes/solarized-dark.json",
            "themes/solarized-light.json",
            "themes/gruvbox-dark.json",
            "themes/one-dark.json",
            "themes/catppuccin-mocha.json",
        ],
    )
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/Termikita.icns",
    "plist": {
        "CFBundleName": "Termikita",
        "CFBundleDisplayName": "Termikita",
        "CFBundleIdentifier": "com.termikita.app",
        "CFBundleVersion": "0.1.2",
        "CFBundleShortVersionString": "0.1.2",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        # Allow opening folders from Finder (drag to dock, "Open With")
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Folder",
                "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["public.folder"],
            },
        ],
        # Custom URL scheme: termikita:///path/to/folder
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "com.termikita.open",
                "CFBundleURLSchemes": ["termikita"],
            },
        ],
        # TCC privacy usage descriptions — required for child processes
        # running inside the terminal to request system permissions.
        # Without these, macOS silently denies access (no dialog shown).
        "NSMicrophoneUsageDescription":
            "An application in Termikita wants to use your microphone.",
        "NSCameraUsageDescription":
            "An application in Termikita wants to use your camera.",
        "NSAppleEventsUsageDescription":
            "An application in Termikita wants to control other applications.",
        "NSLocationWhenInUseUsageDescription":
            "An application in Termikita wants to use your location.",
        "NSDesktopFolderUsageDescription":
            "An application in Termikita wants to access your Desktop folder.",
        "NSDocumentsFolderUsageDescription":
            "An application in Termikita wants to access your Documents folder.",
        "NSDownloadsFolderUsageDescription":
            "An application in Termikita wants to access your Downloads folder.",
        "NSRemovableVolumesUsageDescription":
            "An application in Termikita wants to access removable volumes.",
        "NSContactsUsageDescription":
            "An application in Termikita wants to access your contacts.",
        "NSCalendarsUsageDescription":
            "An application in Termikita wants to access your calendars.",
        "NSPhotoLibraryUsageDescription":
            "An application in Termikita wants to access your photos.",
        # NSServices — "New Termikita Tab Here" in Finder right-click menu
        # Like iTerm2, registered in Info.plist for auto-discovery (no user config)
        "NSServices": [
            {
                "NSMessage": "newTermikitaTabHere",
                "NSPortName": "Termikita",
                "NSMenuItem": {
                    "default": "New Termikita Tab Here",
                },
                "NSRequiredContext": {},
                "NSSendTypes": [
                    "NSFilenamesPboardType",
                    "public.plain-text",
                ],
            },
            {
                "NSMessage": "newTermikitaWindowHere",
                "NSPortName": "Termikita",
                "NSMenuItem": {
                    "default": "New Termikita Window Here",
                },
                "NSRequiredContext": {},
                "NSSendTypes": [
                    "NSFilenamesPboardType",
                    "public.plain-text",
                ],
            },
        ],
    },
    # Top-level packages to bundle
    "packages": ["termikita", "pyte"],
    # Explicit imports that py2app static analysis may miss
    "includes": [
        "objc",
        "AppKit",
        "Foundation",
        "CoreText",
        "Quartz",
        "pyobjc_framework_Cocoa",
        "pyobjc_framework_CoreText",
        "pyobjc_framework_Quartz",
    ],
}

setup(
    app=APP,
    name="Termikita",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
