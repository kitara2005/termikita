# Terminal Context Menu Research

**Date:** 2026-03-10
**Scope:** Context menu patterns across 8 modern terminal emulators
**Focus:** Right-click menu features, organization, & best practices

---

## Executive Summary

Modern terminal emulators vary significantly in context menu support:
- **Full-featured:** iTerm2, macOS Terminal, Windows Terminal, Warp
- **Limited:** Kitty (no context menu), Alacritty (paste-only), Hyper (minimal)
- **GNOME Terminal:** File manager integration, not in-terminal menu

**Key Finding:** No universal standard exists. Most implement copy/paste basics; advanced features (split, search, profiles) vary widely.

---

## 1. Standard Text Operations (Universal)

Present in nearly all terminals:

- **Copy** — Copy selected text to clipboard
- **Paste** — Paste from clipboard
- **Select All** — Select entire buffer/session
- **Clear Selection** — Deselect highlighted text

**Variants by terminal:**
- Windows Terminal & Warp: Support formatting preservation (HTML, RTF)
- iTerm2: Smart selection rules auto-populate menu based on content type (URLs, hex numbers, timestamps)

---

## 2. Terminal-Specific Operations

### Clear & Reset
- **Clear Buffer/Screen** — Clear visible terminal content
- **Clear Scrollback** — Erase entire scroll history
- **Reset Terminal** — Full ANSI state reset

### Search & Navigation
- **Search/Find** — Search buffer text (Windows Terminal, Warp, macOS Terminal)
- **Search Web** — Query selected text online (Windows Terminal Preview)

### URL & Special Content Handling
- **Open URL** — Click detected hyperlinks (Kitty, Windows Terminal, iTerm2)
- **Copy URL/Path** — Extract file paths or URLs separately (Warp, iTerm2)
- **Hex/Timestamp Conversion** — Display hex/date values (iTerm2 specific)

---

## 3. Tab Management

### Tab Creation & Navigation
- **New Tab** — Open new tab in current profile/shell
- **Duplicate Tab** — Copy current tab (Warp, Windows Terminal)
- **Close Tab** — End active tab session
- **Restore Closed Tab** — Undo recent tab closure (Warp)

### Tab-Level Context Menu
- Right-click on tab bar button → New tab, Restore, Launch configuration (Warp)
- Right-click on tab area → Tab switching via menu

---

## 4. Split Pane Operations

- **Split Pane Right** — Vertical split (Ctrl+Shift+D in Warp)
- **Split Pane Down** — Horizontal split (Ctrl+Shift+E in Warp)
- **Split in Any Direction** — Multi-directional splits (Warp)
- **Close Pane** — End active split
- **Focus Previous/Next Pane** — Navigate between splits

---

## 5. Configuration & Appearance

### Font & Display
- **Font Size Adjustment** — Increase/decrease text size
- **Font Selection** — Choose typeface
- **Opacity/Transparency** — Adjust window opacity (Ctrl+Shift scroll in Windows Terminal)

### Theme & Color
- **Select Theme** — Switch color schemes
- **Select Profile** — Load saved profile/shell configuration
- **Preferences** — Open settings dialog (Hyper)

---

## 6. Session & Shell Operations

### Profile Selection
- **New with Profile** — Launch specific shell/profile (macOS Terminal, Windows Terminal)
- **SSH Connections** — Quick SSH profile shortcuts (iTerm2 shell integration)

### Directory Management
- **Pin Directory** — Save folder for quick access (iTerm2 recent dirs)
- **Open at Current Directory** — Set working directory context (macOS Terminal, Warp)

---

## 7. File Manager Integration (macOS/Windows)

### System-Level Context Menu
- **Open in Terminal** — File browser → launch terminal at folder (macOS, Windows, GNOME)
- **Open in [Terminal Name]** — Specific emulator selection
- **Open Terminal as Admin** — Elevated privileges (Windows)

Note: These are Finder/File Explorer context menus, not in-terminal.

---

## 8. Terminal Emulator-Specific Findings

### iTerm2 (macOS)
**Strengths:**
- Smart selection rules (URLs, hex, timestamps, file paths auto-detected)
- Shell integration support (pin directories)
- Comprehensive character/encoding info on right-click
- Advanced semantic selection

**Gap:** Limited documentation on full context menu options

### macOS Terminal.app
**Strengths:**
- Native integration with Finder "Open in Terminal"
- Profile selection in context menu
- Service menu integration

**Limitation:** Minimal built-in context menu options

### Windows Terminal
**Strengths:**
- Rich context menu (experimental feature: `rightClickContextMenu`)
- Actions: Copy, Paste, Find, Duplicate tab, Split pane, Web search
- Configurable: Disable to use right-click for paste instead
- Copy formatting options (plain text, HTML, RTF)

**Feature:** `showContextMenu` action callable via keybinding

### Warp (Modern Terminal)
**Strengths:**
- Tab management: New tab, Restore closed, Run Launch Configuration
- Prompt context menu: Copy prompt, CWD, git branch, uncommitted count
- Split pane: Right-click to split in any direction
- URL/File path extraction

**Design:** Emphasizes quick actions over deep menus

### Kitty
**No native context menu** — Keyboard-focused design
- Right-click: Open URLs, expand selection semantically
- Mouse support: Double-click (word), triple-click (line), right-click (expand)
- Alternative: Configure all actions via `kitty.conf` keybindings

### Alacritty
**Minimal context menu** — Right-click pastes selection by default
- Designed for keyboard-first workflows
- Feature request open for full context menu support
- No built-in UI for common terminal operations

### Hyper
**Minimal in-terminal menu** — System integration focus
- Preferences option on right-click
- File browser integration: "Open Hyper here"
- Feature requests for expanded menu options (new tab, copy, paste, close tab)

### GNOME Terminal
**No in-terminal context menu** — File manager integration instead
- Nautilus (file manager) provides "Open in Terminal"
- Extensions available: gnome-terminal-nautilus
- Customizable via Nautilus Preferences

---

## 9. Context Menu Design Patterns

### Pattern 1: Copy-Paste First (Universal)
All terminals prioritize copy/paste as primary operations:
- **Decision Point:** Auto-copy-on-select vs. explicit copy?
- **Windows Terminal:** Configurable via `copyOnSelect` setting
- **Warp:** Implicit support for quick clipboard actions

### Pattern 2: Smart Content Detection
Most modern terminals detect content type and provide context-aware actions:
- **iTerm2:** Hex conversion, timestamp parsing, semantic selection
- **Windows Terminal:** URL detection and web search
- **Kitty:** Semantic double-click selection

### Pattern 3: Tab Bar Right-Click
Separate context menu on tab bar for tab operations:
- **Warp:** Dedicated tab bar menu
- **Windows Terminal:** Tab actions via context menu
- **Kitty/Alacritty:** No dedicated tab menu

### Pattern 4: Disabled by Default
Some modern terminals disable context menu by default:
- **Windows Terminal:** Disabled by default (config: `rightClickContextMenu: false`)
- **Alacritty:** No option (right-click = paste)
- **Reason:** Avoid interference with paste workflows

---

## 10. Configuration & Customization Approaches

### JSON/Config File Based (Modern)
- **Windows Terminal:** `settings.json` with `rightClickContextMenu` flag
- **Kitty:** `kitty.conf` for all keybindings (no UI menu)
- **Warp:** Settings UI + config

### Preferences Dialog (Traditional)
- **macOS Terminal:** Preferences pane
- **iTerm2:** Preferences window
- **Hyper:** Preferences on right-click

### No Context Menu Option (Minimalist)
- **Alacritty:** Config file only, no UI menus
- **Kitty:** Keyboard-first, config-only approach

---

## 11. Missing Patterns & Gaps

### Rarely Implemented
- **Bookmark URLs** — Save interesting links
- **Copy with Line Numbers** — For debugging/documentation
- **Session Recording** — Start/stop session capture
- **Send to Script/Macro** — Execute custom actions
- **Multiple selection contexts** — Context-aware menu changes per item type

### Why Gaps Exist
1. **Keyboard Focus Culture** — Power users prefer keybindings
2. **Complexity Trade-off** — Context menus add UX overhead
3. **Platform Fragmentation** — macOS/Windows/Linux have different UI conventions
4. **Minimal By Design** — Alacritty, Kitty explicitly avoid UI bloat

---

## 12. Actionable Recommendations for Termikita

### Must-Have (MVP)
1. **Copy/Paste** with formatting option
2. **Select All**
3. **Clear Buffer**
4. **Tab operations** (New Tab, Close Tab, Duplicate)
5. **Split pane** (Right/Down/Close)

### Should-Have (Polish)
6. **Search/Find** buffer text
7. **Smart URL detection** (click to open)
8. **Profile selection** on right-click
9. **Theme/Font size** quick access
10. **Open at current directory** context

### Nice-to-Have (Future)
- Hex/timestamp conversion (iTerm2-style)
- Web search selected text (Windows Terminal style)
- Restore closed tab (Warp style)
- Shell integration features
- Custom action menu items

### Design Decision
- **Default:** Context menu enabled (unlike Windows Terminal which disables by default)
  - Modern users expect right-click menus
  - Termikita targets macOS where context menus are standard
  - Configurable toggle in preferences for power users who prefer paste-on-right-click

---

## Unresolved Questions

1. **Termikita implementation priority** — Which menu items are highest priority for launch?
2. **Custom actions** — Support user-defined right-click actions?
3. **Content-aware menus** — Smart detection of URLs, file paths, hex values?
4. **macOS native integration** — Should app menu bar be separate from context menus?
5. **Keyboard alternative** — Shift+F10 or other keybinding to show menu?

---

## Sources

- [iTerm2 Menu Items Documentation](https://iterm2.com/documentation-menu-items.html)
- [Windows Terminal Interaction Settings](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/interaction)
- [Warp Documentation - Keyboard Shortcuts](https://docs.warp.dev/features/keyboard-shortcuts)
- [Warp Documentation - Files, Links & Scripts](https://docs.warp.dev/terminal/more-features/files-and-links)
- [Alacritty GitHub Issues - Right Click Support](https://github.com/alacritty/alacritty/issues/5604)
- [Kitty GitHub Issue - Standard Right-click Menu](https://github.com/kovidgoyal/kitty/issues/7632)
- [Hyper GitHub - Context Menu Feature Request](https://github.com/vercel/hyper/issues/265)
- [GNOME Terminal - Open in Terminal Context Menu](https://discourse.gnome.org/t/right-click-menu-in-directory-open-in-terminal-only-opens-gnome-default-terminal/21480)
