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
    "plist": {
        "CFBundleName": "Termikita",
        "CFBundleDisplayName": "Termikita",
        "CFBundleIdentifier": "com.termikita.app",
        "CFBundleVersion": "0.1.1",
        "CFBundleShortVersionString": "0.1.1",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
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
