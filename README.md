# Termikita

A lightweight, native macOS terminal emulator. CoreText rendering, no Electron — text is as crisp as Terminal.app.

<p align="center">
  <img src="assets/icon.png" width="128" alt="Termikita icon">
</p>

## Why?

Terminal.app is too basic. iTerm2 is too heavy. Termikita is in between — native rendering, theme support, and works well with Claude Code and modern CLI tools.

## Features

- Native CoreText rendering — Retina-sharp, no blurring
- 24-bit truecolor + 9 themes (Dracula, Nord, Catppuccin, ...)
- Vietnamese IME (Telex/VNI)
- Multi-tab, multi-window
- Nerd Font auto-detection
- Finder integration & dock bounce notifications
- 100K line scrollback

## Install

Download DMG from [**Releases**](https://github.com/kitara2005/termikita/releases/latest), drag to Applications.

Or build from source:

```bash
git clone https://github.com/kitara2005/termikita.git
cd termikita
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[build]"
python -m termikita
```

**Requires:** macOS 13+ (Ventura), Python 3.12+

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd+T` / `Cmd+N` | New tab / window |
| `Cmd+W` | Close tab |
| `Cmd+1`–`9` | Switch tab |
| `Cmd+=` / `-` / `0` | Zoom in / out / reset |
| `Cmd+C` / `Cmd+V` | Copy / paste |

## Configuration

`~/.config/termikita/config.json`:

```json
{
  "font_family": "SF Mono",
  "font_size": 13.0,
  "theme": "default-dark",
  "scrollback_lines": 100000
}
```

## Nerd Fonts

```bash
brew install font-symbols-only-nerd-font
```

## License

MIT
