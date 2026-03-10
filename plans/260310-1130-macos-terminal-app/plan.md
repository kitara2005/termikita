---
title: "Termikita — Native macOS Terminal Emulator"
description: "Termikita: Python-based macOS terminal app with PyObjC, pyte, CoreText — full Unicode/Vietnamese support"
status: complete
priority: P1
effort: 12d
branch: main
tags: [macos, terminal, pyobjc, pyte, coretext, unicode]
created: 2026-03-10
---

# Termikita — Implementation Plan

## Context Links
- [Architecture Research](../reports/researcher-260310-1127-terminal-architecture.md)
- [UX Features Research](../reports/researcher-260310-1127-terminal-ux-features.md)
- [Vietnamese IME Research](../reports/researcher-260310-1147-vietnamese-ime-compatibility.md)
- [Claude Code CLI Research](../reports/researcher-260310-1154-claude-code-cli-support.md)
- [AI Terminal Feasibility Research](../reports/researcher-260310-1216-ai-terminal-feasibility.md)

## Tech Stack
- **GUI:** PyObjC (Cocoa — NSApplication, NSWindow, NSView)
- **VT100 Parser:** pyte (Screen + Stream)
- **Text Rendering:** CoreText via PyObjC
- **PTY:** Python `pty` + `os` + threading
- **Config:** JSON files (~/.config/termikita/)
- **Packaging:** py2app for .app bundle

## Architecture (High Level)
```
NSApplication
  -> NSWindow + TabViewController
       -> TerminalView (NSView)  -- renders grid via CoreText
       -> TerminalSession         -- owns PTY + pyte Screen
       -> InputHandler            -- keyboard/mouse -> PTY
  -> ThemeManager                 -- JSON themes, color palette
  -> ConfigManager                -- user preferences persistence
```

## Phases

| # | Phase | Est | Status |
|---|-------|-----|--------|
| 01 | [Project Setup](phase-01-project-setup.md) | 0.5d | complete |
| 02 | [PTY Management](phase-02-pty-management.md) | 1d | complete |
| 03 | [Terminal Buffer & VT100](phase-03-terminal-buffer-vt100.md) | 1.5d | complete |
| 04 | [Text Rendering](phase-04-text-rendering.md) | 2d | complete |
| 05 | [Terminal View](phase-05-terminal-view.md) | 2d | complete |
| 06 | [Multi-Tab Support](phase-06-multi-tab-support.md) | 1.5d | complete |
| 07 | [Theme System](phase-07-theme-system.md) | 1d | complete |
| 08 | [Settings & Preferences](phase-08-settings-preferences.md) | 1d | complete |
| 09 | [App Shell & Packaging](phase-09-app-shell-packaging.md) | 1.5d | complete |
| 10 | [Developer UX v1.1](phase-10-developer-ux-v11.md) | 1.5d | planned |

## Key Dependencies
- Phases 02, 03 can be developed somewhat in parallel
- Phase 04 depends on 03 (needs grid data)
- Phase 05 depends on 02 + 03 + 04 (integration layer)
- Phases 06, 07, 08 depend on 05 (need working terminal view)
- Phase 09 depends on all prior phases
- Phase 10 depends on 05 (terminal view must be working); begins after v1.0 ships

## Design Philosophy

> Build an excellent terminal that AI tools render beautifully into. Don't try to parse AI semantics from ANSI output.

Termikita's job is to be a fast, correct, responsive terminal. Claude Code already renders markdown → ANSI-formatted text with colors, spinners, and syntax highlighting. The terminal displays it. The terminal does not re-parse or re-interpret what Claude Code has already rendered.

## MVP Scope (v1.0)
- Single window, multi-tab terminal
- Full VT100/xterm escape sequence support (via pyte)
- Unicode + Vietnamese diacritics (NFC normalization)
- NSTextInputClient for Vietnamese IME (GoTiengViet, EVKey, built-in Telex)
- Claude Code CLI optimized (truecolor, streaming latency <10ms, 30-60 FPS)
- Pre-defined themes (Dracula, Nord, Solarized, etc.)
- Font selection (monospace only)
- Scrollback buffer (100k lines, ring buffer via collections.deque)
- Copy/paste, search in scrollback
- Standard macOS shortcuts (Cmd+T/W/N/Q/,)
- Config dir: `~/.config/termikita/`
- Glyph atlas cache (CTFont+char → CGGlyph, pre-populated ASCII range)
- Double buffering (off-screen render → flip, no flicker during streaming)
- OSC 8 hyperlink storage (detect and store; rendering in v1.1)

## v1.1 Scope (Developer UX — Phase 10)
- File path detection + clickable (open in default editor)
- Error/stacktrace highlighting (Python, Node.js, Rust panics)
- Code block navigation (Cmd+Up/Down)
- OSC 8 hyperlink rendering (render links stored in v1.0)

## Explicitly Out of Scope (never build)
- **AI streaming parser / markdown re-rendering** — Claude Code already renders via ANSI; re-parsing is lossy and fragile
- **Claude state detection** (thinking/editing/running) — no structured state data exposed; heuristics break on any Claude update
- **Task tracker from AI output** — fragile regex on numbered lists; redundant with Claude Code's own output
- **Context usage monitor** — Claude Code already displays this; parsing + re-displaying = redundant clutter
- **Collapsible sections** — breaks terminal abstraction; copy/paste and search break; standard `less` pager does this better
- **GPU Metal rendering** — CoreText + double buffering achieves 60 FPS target; Metal adds 2+ weeks for marginal gain
- **AI activity timeline** — requires structured API data Claude Code doesn't expose; ANSI reconstruction is unreliable
- **Syntax re-highlighting via tree-sitter** — Claude Code already syntax-highlights; re-highlighting causes visual flicker

Also out of scope: split panes, inline images, plugin system, session restore, ligature rendering
