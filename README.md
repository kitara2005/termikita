# Termikita

A lightweight, native macOS terminal emulator built with Python and AppKit. Renders text with CoreText for crisp, Retina-quality output — no Electron, no web views, no GPU layers.

Built for developers who use Claude Code, vim, and modern CLI tools daily.

<p align="center">
  <img src="assets/icon.png" width="128" alt="Termikita icon">
</p>

## Why Termikita?

Terminal.app is too basic — no themes, poor Nerd Font support, limited tab UX. iTerm2 is feature-rich but heavy. Termikita sits in between: lightweight, native rendering, and works great with modern TUI apps like Claude Code.

## Highlights

- **Native macOS rendering** — CoreText + AppKit, same drawing path as Terminal.app
- **Retina-sharp text** — subpixel positioning, no layer-backed blurring
- **Full Unicode & Vietnamese IME** — NFC normalization, Telex/VNI input via NSTextInputClient
- **24-bit truecolor** — correct colors for Claude Code, vim, bat, delta, lazygit
- **9 color themes** — Dracula, Nord, Catppuccin Mocha, Gruvbox, One Dark, Solarized, and more
- **Nerd Font auto-detection** — Powerline/devicons just work, no manual config
- **Multi-tab, multi-window** — each tab runs its own PTY process
- **Finder integration** — right-click "Open in Termikita", drag folders to dock icon
- **Dock bounce & notifications** — alerts when long-running commands finish in background
- **100K line scrollback** — smooth scrolling, stable viewport during streaming output

## Works Great With

| Tool | Status |
|------|--------|
| Claude Code | Tested daily — cursor, colors, spinners, IME all work correctly |
| vim / neovim | Alternate screen, cursor shapes, 24-bit color |
| tmux | Nested sessions, passthrough sequences |
| lazygit / htop | Full TUI rendering |
| bat / delta / fzf | Syntax highlighting, 256/truecolor |

---

## Installation

### Download

Grab the latest DMG from [**Releases**](https://github.com/kitara2005/termikita/releases/latest) — open it and drag Termikita to Applications.

**Requirements:** macOS 13.0 (Ventura) or later.

### Build from source

```bash
git clone https://github.com/kitara2005/termikita.git
cd termikita
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[build]"

# Run directly
python -m termikita

# Build .app bundle
python setup.py py2app        # → dist/Termikita.app

# Build DMG installer
bash build-dmg.sh             # → dist/Termikita.dmg
```

**Requirements:** Python 3.12+, macOS 13.0 (Ventura) or later.

---

## Features

### Multi-Tab & Multi-Window

Each tab runs its own shell process with a dedicated PTY. Multiple windows supported with cascading placement.

| Shortcut | Action |
|---|---|
| `Cmd+T` | New tab |
| `Cmd+N` | New window |
| `Cmd+W` | Close tab |
| `Cmd+1`–`9` | Switch to tab by number |
| `Cmd+Shift+]` / `[` | Next / previous tab |

### Text Rendering

CoreText renders each line as grouped `CTLine` runs — the same API that powers TextEdit and Xcode. No layer-backed views means no scaling artifacts on Retina displays.

- **Font variants:** bold, italic, bold-italic via NSFontManager
- **Font cascade:** primary font → Nerd Font (auto-detected) → Lucida Grande → LastResort
- **Block elements:** pixel-snapped box drawing and block art (█▄▀─│├┘)
- **Decorations:** underline, strikethrough at subpixel precision

### Font Selection & Zoom

| Shortcut | Action |
|---|---|
| `Cmd+=` | Zoom in (+1pt) |
| `Cmd+-` | Zoom out (-1pt) |
| `Cmd+0` | Reset to default size |

Font range: 8pt – 36pt. Changes persist across sessions. Open the system font panel from **Format → Font → Show Fonts**.

### Color Themes

9 bundled themes — switch from **View → Theme**:

| Theme | Style |
|---|---|
| `default-dark` | Light gray on dark (default) |
| `default-light` | Dark text on light background |
| `dracula` | Purple-accented dark |
| `nord` | Arctic, blue-tinted |
| `solarized-dark` / `light` | Ethan Schoonover's palette |
| `gruvbox-dark` | Retro warm dark |
| `one-dark` | Atom One Dark |
| `catppuccin-mocha` | Pastel dark, warm tones |

Custom themes: add a `.json` file to `themes/` directory.

### Cursor

Three cursor styles with blinking: **Block**, **Beam** (I-bar), **Underline**. Shape controlled by apps via `DECSCUSR`. Visibility (`DECTCEM`) strictly respected — TUI frameworks like Ink/Claude Code that render their own cursor work correctly.

### Terminal Emulation

Full VT100/xterm emulation via [pyte](https://github.com/selectel/pyte):

- **Colors:** 16 ANSI, 256 indexed, 24-bit RGB
- **Attributes:** bold, italic, underline, reverse video, strikethrough
- **Alternate screen:** DECSET/DECRST 1049 with scrollback save/restore
- **Terminal queries:** DA1, DSR (cursor position)
- **Hyperlinks:** OSC 8 per-cell
- **Window title:** OSC 2
- **Synchronized output:** DEC 2026

### Scrollback

100,000 lines by default. Scrollback freezes during alternate-screen apps (vim, less, htop).

- Mouse wheel scrolls history in normal mode
- Mouse wheel sends arrow keys in alternate screen (vim/less navigation)
- Scroll position stays stable when new output arrives
- Snaps to bottom on keyboard input

### Copy, Paste & Selection

| Shortcut | Action |
|---|---|
| `Cmd+C` | Copy selection (or interrupt if no selection) |
| `Cmd+V` | Paste from clipboard |
| `Cmd+A` | Select all visible lines |
| Mouse drag | Select text region |

Image paste: saves to temp file and inserts the path.

### Finder Integration

- **Services menu** (right-click in Finder): "New Termikita Tab/Window Here"
- **Drag & drop:** folders onto dock icon
- **URL scheme:** `open "termikita:///path/to/folder"`
- **Command line:** `termikita /path/to/folder`

### Background Notifications

When Termikita is in background: dock bounce + macOS notification when commands finish. Triggered by TUI app exit, shell output after silence, or BEL character.

---

## Configuration

Settings stored in `~/.config/termikita/config.json`:

```json
{
  "font_family": "SF Mono",
  "font_size": 13.0,
  "theme": "default-dark",
  "scrollback_lines": 100000,
  "window_width": 800,
  "window_height": 500,
  "shell": ""
}
```

| Key | Default | Description |
|---|---|---|
| `font_family` | `"SF Mono"` | Monospace font name |
| `font_size` | `13.0` | Font size in points (8–36) |
| `theme` | `"default-dark"` | Theme name |
| `scrollback_lines` | `100000` | Max scrollback buffer |
| `window_width` | `800` | Initial window width (px) |
| `window_height` | `500` | Initial window height (px) |
| `shell` | `""` | Shell path; empty = `$SHELL` or `/bin/zsh` |

---

## Architecture

```
┌─────────────────────────────────────────┐
│              AppDelegate                │  Cocoa lifecycle, menu bar, Services
├──────────┬──────────────────────────────┤
│ TabBar   │       TabController          │  Multi-tab orchestration
├──────────┴──────────────────────────────┤
│              TerminalView               │  NSView + NSTextInputClient
│  ┌─────────────────┬──────────────────┐ │
│  │  DrawMixin      │  InputMixin      │ │  drawRect_, mouse, keyboard, IME
│  └────────┬────────┴──────────────────┘ │
├───────────┼─────────────────────────────┤
│     TextRenderer + CellDrawHelpers      │  CoreText CTLine, glyph atlas
├───────────┼─────────────────────────────┤
│    TerminalSession                      │  Owns PTY + Buffer
│  ┌────────┴────────┬──────────────────┐ │
│  │  PTYManager     │  BufferManager   │ │  Fork/exec, pyte VT100 parser
│  └─────────────────┴──────────────────┘ │
└─────────────────────────────────────────┘
```

- **PTY read thread** feeds data into BufferManager (pyte). Main thread polls dirty flags at 60 fps.
- **CoreText** renders lines as style-grouped CTLine runs. PUA characters isolated into single-cell runs.
- **No `setWantsLayer_(True)`** — layer-backed views blur text on Retina. Termikita draws directly like Terminal.app.

---

## Environment Variables

| Variable | Value |
|---|---|
| `TERM` | `xterm-256color` |
| `COLORTERM` | `truecolor` |
| `LANG` | `en_US.UTF-8` (if not set) |
| `PROMPT_EOL_MARK` | `""` (suppresses zsh `%`) |

---

## Nerd Fonts

Auto-detects installed Nerd Fonts via NSFontManager. For full icon support:

```bash
brew install font-symbols-only-nerd-font
```

---

## Vietnamese IME

Full Telex/VNI support via `NSTextInputClient`. When using CLI tools with `/` commands (e.g. Claude Code), press `Cmd+Space` to switch to English input first — this is a macOS IME limitation.

---

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,build]"
python -m termikita          # Run
ruff check src/              # Lint
mypy src/termikita/          # Type check
```

---

## Contributing

Issues, bug reports, and PRs are welcome at [github.com/kitara2005/termikita](https://github.com/kitara2005/termikita).

## License

MIT
