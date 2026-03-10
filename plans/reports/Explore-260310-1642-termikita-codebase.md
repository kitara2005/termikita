# Termikita Codebase Exploration Report

**Date:** 2026-03-10  
**Project:** Termikita v0.1.1 — Native macOS Terminal Emulator  
**Scope:** Architecture, source file purposes, menu implementations, mouse event handling

---

## 1. PROJECT OVERVIEW

**Termikita** is a native macOS terminal emulator written in Python using PyObjC.

- **Language:** Python 3.12+
- **UI Framework:** AppKit (PyObjC)
- **Terminal Parsing:** pyte (VT100 emulation)
- **Total Source Files:** 22 Python modules
- **Total LOC:** ~2,989 lines (excluding tests)
- **Version:** 0.1.1
- **Key Dependencies:**
  - `pyobjc-framework-Cocoa` (macOS AppKit bindings)
  - `pyobjc-framework-CoreText` (text rendering)
  - `pyobjc-framework-Quartz` (graphics)
  - `pyte` (VT100 terminal emulation)

---

## 2. ARCHITECTURE OVERVIEW

### Module Organization (22 files, ~3k LOC)

```
src/termikita/
├── __init__.py                    # Entry point, app launcher
├── __main__.py                    # CLI entry
├── app_delegate.py                # NSApplicationDelegate, menu bar setup (131 lines)
├── main_window.py                 # NSWindow + layout (88 lines)
├── tab_controller.py              # Tab management orchestrator (288 lines)
├── tab_bar_view.py                # Tab strip renderer (279 lines)
├── terminal_view.py               # Core terminal NSView (241 lines)
├── terminal_view_input.py         # NSTextInputClient, selection, clipboard (171 lines)
├── terminal_view_draw.py          # Rendering, timers, scroll (135 lines)
├── terminal_session.py            # PTY + Buffer orchestrator (140 lines)
├── buffer_manager.py              # VT100 parsing, scrollback (244 lines)
├── pty_manager.py                 # PTY spawning, I/O thread (252 lines)
├── text_renderer.py               # CoreText rendering engine (180 lines)
├── glyph_atlas.py                 # Glyph caching (119 lines)
├── cell_draw_helpers.py           # Low-level drawing (121 lines)
├── theme_manager.py               # Theme loading, color resolution (139 lines)
├── color_resolver.py              # ANSI/named color lookup (108 lines)
├── color_utils.py                 # Hex↔RGB conversion (47 lines)
├── config_manager.py              # JSON config persistence (131 lines)
├── input_handler.py               # Key code → ESC sequence mapping (81 lines)
├── constants.py                   # App-wide constants (39 lines)
└── unicode_utils.py               # NFC normalization for Vietnamese (35 lines)
```

### High-Level Architecture

```
NSApplication
  ↓
AppDelegate (app_delegate.py)
  ├─ Menu bar setup (NSMenu, NSMenuItem)
  ├─ ConfigManager (preferences)
  ├─ ThemeManager (color themes)
  └─ MainWindow
       ├─ TabBarView (28px strip at top)
       │   ├─ Tab rendering (title, close button)
       │   ├─ Mouse event handling (select tab, close)
       │   └─ Hover state tracking
       │
       └─ Content View (NSView container)
            └─ TerminalView (currently active)
                 ├─ TextRenderer (CoreText)
                 ├─ TerminalSession
                 │   ├─ BufferManager (pyte VT100 parsing)
                 │   └─ PTYManager (shell spawning, I/O thread)
                 └─ NSTextInputClient protocol (IME support)
```

---

## 3. SOURCE FILES DETAILED PURPOSES

### Core Application Lifecycle

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 16 | Main entry point; launches NSApplication, instantiates AppDelegate |
| `__main__.py` | 4 | CLI wrapper for `python -m termikita` |
| `app_delegate.py` | 131 | NSApplicationDelegate; bootstraps config/theme/window/tabs, **builds menu bar** |
| `main_window.py` | 88 | Creates NSWindow, sets up tab bar + content view layout |

### Tab Management

| File | Lines | Purpose |
|------|-------|---------|
| `tab_controller.py` | 288 | Orchestrates tab list; add/close/select/next/prev; owns TerminalSession lifetime |
| `tab_bar_view.py` | 279 | NSView rendering the tab strip; **mouse event handling** (select, close, hover) |

### Terminal Display & Input

| File | Lines | Purpose |
|------|-------|---------|
| `terminal_view.py` | 241 | Main terminal NSView; mixes in drawing + input mixins; forwards PyObjC selectors |
| `terminal_view_draw.py` | 135 | Mixin: drawRect_, selection highlight, scroll wheel, 60fps + blink timers |
| `terminal_view_input.py` | 171 | Mixin: NSTextInputClient (IME), **mouse selection**, copy/paste |

### Session & PTY Management

| File | Lines | Purpose |
|------|-------|---------|
| `terminal_session.py` | 140 | Owns one PTY + BufferManager; bridges I/O; dispatches title change callbacks |
| `pty_manager.py` | 252 | PTY spawning, shell env setup, I/O thread read/write, SIGWINCH resize |
| `buffer_manager.py` | 244 | VT100 parsing via pyte; scrollback ring buffer; dirty line tracking; OSC 8 hyperlinks |

### Rendering & Fonts

| File | Lines | Purpose |
|------|-------|---------|
| `text_renderer.py` | 180 | CoreText-based renderer; font loading, metrics, delegates to cell_draw_helpers |
| `glyph_atlas.py` | 119 | Glyph caching; warm cache on font change |
| `cell_draw_helpers.py` | 121 | Low-level drawing: backgrounds, glyphs, decorations (bold, italic, underline) |

### Themes & Configuration

| File | Lines | Purpose |
|------|-------|---------|
| `theme_manager.py` | 139 | Loads JSON theme files; resolves hex colors to RGB |
| `color_resolver.py` | 108 | ANSI color lookup; foreground/background attribute resolution |
| `color_utils.py` | 47 | Hex ↔ RGB conversion helpers |
| `config_manager.py` | 131 | JSON config persistence (~/.config/termikita/config.json) |

### Utilities

| File | Lines | Purpose |
|------|-------|---------|
| `input_handler.py` | 81 | Key code → ESC sequence mapping (special keys: arrows, F-keys, etc.) |
| `constants.py` | 39 | App-wide constants: font defaults, theme dir, terminal env vars |
| `unicode_utils.py` | 35 | NFC text normalization (Vietnamese diacritic support) |

---

## 4. MENU/CONTEXT MENU IMPLEMENTATION

### **4a. Menu Bar Construction**

**Location:** `/Users/long-nguyen/Documents/Ca-nhan/terminal/src/termikita/app_delegate.py`, lines 64-117

**Method:** `_setup_menu_bar()`

**Current Menu Structure:**

```
Termikita                           (App menu)
├── About Termikita
├── ─────────────
└── Quit Termikita               (Cmd+Q)

Shell                             (Tab management)
├── New Tab                       (Cmd+T)
└── Close Tab                     (Cmd+W)

Edit                              (Clipboard + selection)
├── Copy                          (Cmd+C)
├── Paste                         (Cmd+V)
└── Select All                    (Cmd+A)

Window                            (Window controls)
└── Minimize                      (Cmd+M)
```

**Implementation Pattern:**

```python
# 1. Create main menu
main_menu = NSMenu.alloc().init()

# 2. For each submenu:
submenu = NSMenu.alloc().initWithTitle_("Submenu Name")
submenu.addItemWithTitle_action_keyEquivalent_("Item", "action:", "keyEquiv")

# 3. Create menu item wrapper
submenu_item = NSMenuItem.alloc().init()
submenu_item.setSubmenu_(submenu)
main_menu.addItem_(submenu_item)

# 4. Attach to app
NSApp.setMainMenu_(main_menu)
```

**Action Handlers (IBAction methods):**
- `newTab_(sender)` → `_tab_ctrl.add_tab()`
- `closeTab_(sender)` → `_tab_ctrl.close_tab()`

---

### **4b. Context/Right-Click Menus**

**Status:** ❌ NOT IMPLEMENTED

**Search Results:**
- No `rightMouseDown:` method found in TerminalView
- No `menuForEvent:` override found
- No `contextMenu` property
- No `rightClick` or `popup_menu` implementations

**Code Search Summary:**

```
Files with NSMenu/menu setup:
├── app_delegate.py          (menu bar only)
├── tab_bar_view.py          (no context menu)
├── terminal_view.py         (no right-click handler)
└── terminal_view_input.py   (no right-click handler)

Missing implementations:
❌ rightMouseDown_()
❌ menuForEvent_()
❌ Context menu for terminal content area
❌ Tab context menu (right-click on tab)
```

---

## 5. MOUSE EVENT HANDLING

### **5a. Terminal View (terminal_view.py + terminal_view_input.py)**

**Left-Click Selection:**
- `mouseDown_(event)` → Start selection at cursor point
- `mouseDragged_(event)` → Extend selection end
- `mouseUp_(event)` → Collapse zero-length selections

**Flow:**
1. Event location converted from window → view coordinates
2. Pixel position mapped to grid (row, col) via cell dimensions
3. Selection state tracked: `_selection_start`, `_selection_end`
4. Redraw triggered on change

**No Right-Click Handler:** TerminalView does NOT override `rightMouseDown_`

---

### **5b. Tab Bar View (tab_bar_view.py)**

**Mouse Events Implemented:**
- `mouseDown_(event)` → Hit-test; select tab or queue close
- `mouseMoved_(event)` → Update hover state for close button highlight
- `mouseExited_(event)` → Reset hover state
- Tracking area setup for mouse-moved events

**Hit Testing:**
```python
def _hit_test(point) -> (tab_index, on_close):
    # Return tab index & whether point is in close button region
```

**Close Button Logic:**
- Close area: rightmost 18px of tab
- Deferred close via `performSelector_withObject_afterDelay_` (safe dealloc)

**No Right-Click Handler:** TabBarView does NOT override `rightMouseDown_`

---

## 6. CURRENT FEATURES

### ✅ Implemented

| Category | Feature |
|----------|---------|
| **Tabs** | Add (Cmd+T), Close (Cmd+W), Select, Switch (visual indicators) |
| **Editing** | Copy (Cmd+C), Paste (Cmd+V), Select All (Cmd+A), Mouse selection |
| **Display** | Line-based rendering, selection highlight, cursor blink, scroll wheel |
| **Keyboard** | Ctrl+letter → control char, special keys (arrows, F-keys, etc.) |
| **IME** | Full NSTextInputClient protocol (Vietnamese composition) |
| **Themes** | JSON theme loading, dark/light themes, ANSI color palette |
| **Config** | Persistent preferences (~/.config/termikita/config.json) |
| **Scrollback** | 100k line ring buffer, scroll up/down |
| **PTY** | Shell spawning, SIGWINCH on resize, UTF-8 I/O |
| **VT100** | Full pyte parsing, OSC 2 window title, OSC 8 hyperlinks, DEC 2026 sync |

### ❌ Not Implemented

| Category | Feature |
|----------|---------|
| **Context Menus** | Right-click menu on terminal content |
| **Tab Context Menu** | Right-click on tab (rename, properties, etc.) |
| **Search** | Find/grep in terminal |
| **Profile System** | Save/load terminal profiles |
| **Keyboard Shortcuts** | Beyond current (Cmd+T, W, C, V, A, K) |
| **Preferences GUI** | Settings dialog; currently JSON only |
| **Split Panes** | Tmux-like split view |
| **Sessions** | Save/restore terminal state |

---

## 7. CONFIGURATION & PREFERENCES

### ConfigManager (config_manager.py)

**Location:** `~/.config/termikita/config.json`

**Schema:**
```json
{
  "font_family": "SF Mono",
  "font_size": 13.0,
  "theme": "default-dark",
  "scrollback_lines": 100000,
  "cursor_style": "block",      // "block" | "beam" | "underline"
  "cursor_blink": true,
  "line_height": 1.2,
  "window_width": 800,
  "window_height": 500,
  "shell": "",                  // auto-detect if empty
  "confirm_close": true
}
```

---

## 8. THEME SYSTEM

### ThemeManager (theme_manager.py)

**Theme Location:** `themes/` directory at project root (or `Resources/themes` in .app bundle)

**Theme File Format:**
```json
{
  "name": "Custom Theme",
  "colors": {
    "foreground": "#cccccc",
    "background": "#1e1e1e",
    "cursor": "#ffffff",
    "selection": "#444444",
    "ansi": ["#000000", "#cc0000", ...]  // 16 colors
  }
}
```

**Color Resolution:** Hex → (R, G, B) tuples for AppKit drawing

---

## 9. KEY ARCHITECTURAL DECISIONS

### Thread Safety
- **Single PTY read thread** feeds BufferManager
- **Main thread** polls `buffer.dirty` via 60fps refresh timer
- **No explicit locking** needed (single-producer/consumer at I/O rates)

### Rendering Pipeline
1. PTY thread: `buffer.feed(bytes)` → pyte parsing
2. Main thread (timer): check `buffer.dirty` → `setNeedsDisplay_`
3. drawRect_: renders visible lines + cursor + selection + IME

### PyObjC Pattern
- Mixin classes (TerminalViewDrawMixin, TerminalViewInputMixin) for code organization
- Explicit method forwarding in main class (PyObjC requires methods directly on class)
- `@objc.IBAction` decorator for action handlers

### Deferred Deallocation
- Tab close deferred via `performSelector_withObject_afterDelay_` (safe from crash)
- Prevents deallocating view while event handler on call stack

---

## 10. FILE DEPENDENCIES & IMPORTS

### Import Graph (Simplified)

```
app_delegate.py
├── ConfigManager
├── ThemeManager
├── MainWindow
│   └── TabBarView
│       └── TabController
└── TabController
    ├── TerminalView
    │   ├── TerminalSession
    │   │   ├── PTYManager
    │   │   └── BufferManager
    │   │       └── pyte (external)
    │   ├── TextRenderer
    │   │   ├── GlyphAtlas
    │   │   └── cell_draw_helpers
    │   └── NSTextInputClient mixin

ThemeManager ← ColorUtils
ConfigManager ← (standalone, JSON)
```

---

## 11. SIZE BREAKDOWN

```
Code Organization by Size:
────────────────────────────
UI Layer (NSView, events):        ~700 LOC
  - TerminalView + mixins: 547 LOC
  - TabBarView: 279 LOC

Session/PTY/Buffer Layer:          ~636 LOC
  - BufferManager: 244 LOC
  - PTYManager: 252 LOC
  - TerminalSession: 140 LOC

Rendering Layer:                   ~420 LOC
  - TextRenderer: 180 LOC
  - GlyphAtlas: 119 LOC
  - CellDrawHelpers: 121 LOC

Config/Theme/Color:               ~417 LOC
  - ThemeManager: 139 LOC
  - ConfigManager: 131 LOC
  - ColorResolver: 108 LOC
  - ColorUtils: 47 LOC
  - ConstantsHandlers: 39 LOC

Utils:                             ~116 LOC
  - InputHandler: 81 LOC
  - UnicodeUtils: 35 LOC

App Bootstrap:                     ~307 LOC
  - AppDelegate: 131 LOC
  - TabController: 288 LOC
  - MainWindow: 88 LOC

Total: ~2,989 LOC
```

---

## 12. COMPILATION & TESTING

### Build System
- **Backend:** setuptools (pyproject.toml)
- **Packaging:** py2app (macOS .app bundle, .dmg distribution)
- **Type Checking:** mypy (optional)
- **Linting:** ruff (line-length: 100)

### Tests
```
tests/
├── test-buffer-manager.py
├── test-pty-buffer-pipeline.py
└── __init__.py
```

Test tags: `@pytest.mark.slow` for live PTY tests

---

## 13. CURRENT LIMITATIONS & GAPS

### No Context Menu System
- **Terminal View:** No right-click handler
  - Could add: Copy, Paste, Select All, Clear, Open URL, Search
- **Tab Bar:** No right-click handler
  - Could add: Close, Rename, Properties, Move

### No Keyboard Shortcuts Beyond Core
- Missing: Cmd+1-9 (select tab by number)
- Missing: Cmd+Shift+] / Cmd+Shift+[ (next/prev tab)
- Missing: Font size increase/decrease

### Configuration
- Config is JSON-only; no GUI
- No theme switcher in app; must edit config

### Text Selection
- Only left-click selection; no keyboard selection
- No word/line double-click selection

---

## 14. RECOMMENDATIONS FOR CONTEXT MENU IMPLEMENTATION

### Option 1: Quick Right-Click Menu (Terminal View)

**Location:** terminal_view_input.py

```python
def rightMouseDown_(self, event: object) -> None:
    """Show context menu on right-click."""
    menu = NSMenu.alloc().init()
    menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "")
    menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "")
    menu.addItem_(NSMenuItem.separatorItem())
    menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "")
    NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)
```

### Option 2: Tab Context Menu (Tab Bar View)

**Location:** tab_bar_view.py

```python
def rightMouseDown_(self, event: object) -> None:
    """Show context menu on right-click of tab."""
    loc = self.convertPoint_fromView_(event.locationInWindow(), None)
    tab_idx, _ = self._hit_test(loc)
    if tab_idx >= 0:
        menu = NSMenu.alloc().init()
        menu.addItemWithTitle_action_keyEquivalent_("Close", "closeTab:", "")
        NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)
```

---

## UNRESOLVED QUESTIONS

1. **Are hyperlinks (OSC 8) interactive?** BufferManager parses them, but no click handler implemented.
2. **Should Cmd+K (clear) be added to menu?** Currently keyboard-only.
3. **Is there a preferences dialog planned?** Config is JSON-only currently.
4. **Multi-window support?** Currently single NSWindow; NSWindowController available.
5. **Should context menus include theme switching?** No GUI for it yet.

---

**End of Report**
