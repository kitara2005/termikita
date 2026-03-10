# Termikita UX Roadmap — From Terminal to AI Dev Tool

**Date:** 2026-03-10
**Status:** Planning
**Codebase:** ~3,146 LOC (22 PyObjC modules)

## Philosophy

Transform Termikita from basic terminal into an **AI-aware dev terminal** — incrementally, KISS/YAGNI first. Each phase delivers standalone value. No phase depends on future phases.

## Phase Overview

| # | Phase | Impact | Effort | Priority | Status |
|---|-------|--------|--------|----------|--------|
| 00 | **Performance & Rendering Fix** | **Critical** | **Medium** | **P0 FIRST** | **DONE** |
| 01 | Smart Right-Click Menu (context detection) | High | Medium | P0 | TODO |
| 02 | Status Bar | High | Low | P0 | TODO |
| 03 | Tab Enhancements (rename, split) | Medium | Medium | P1 | TODO |
| 04 | Font Ligatures + Better Typography | Medium | Low | P1 | TODO |
| 05 | Smart File/URL Detection & Click | High | Medium | P1 | TODO |
| 06 | Syntax Highlighting for Code Blocks | High | High | P2 | TODO |
| 07 | Sidebar (session info, files, errors) | High | High | P2 | TODO |
| 08 | Command Block Rendering | Very High | Very High | P3 | TODO |
| 09 | Claude AI Integration (explain, fix) | Very High | Very High | P3 | TODO |
| 10 | Animations & Polish | Low | Low | P3 | TODO |

## Priority Legend

- **P0**: Do next — high impact, reasonable effort
- **P1**: Quick wins or solid improvements
- **P2**: Major features requiring new architecture
- **P3**: Aspirational — transforms terminal into AI dev tool

## Current Capabilities (Already Done)

- [x] Basic context menu (Copy/Paste/Select All/Clear Buffer/New Tab/Close Tab)
- [x] Tab bar context menu (New Tab/Close Tab/Close Other Tabs/Duplicate Tab)
- [x] 9 themes (Dracula, Nord, Solarized, Catppuccin, etc.)
- [x] Configurable font family/size
- [x] VT100 parsing, OSC 2 titles, OSC 8 hyperlinks
- [x] Vietnamese IME support
- [x] 100k scrollback buffer

## Architecture Impact

| Phase | New Files | Modified Files | New Dependencies |
|-------|-----------|---------------|------------------|
| 01 | `content_detector.py` | `terminal_view_input.py` | None |
| 02 | `status_bar_view.py` | `main_window.py`, `tab_controller.py` | None |
| 03 | `split_view_controller.py` | `tab_bar_view.py`, `tab_controller.py` | None |
| 04 | None | `text_renderer.py`, `config_manager.py` | None |
| 05 | `link_detector.py` | `terminal_view_draw.py`, `terminal_view_input.py` | None |
| 06 | `syntax_highlighter.py` | `buffer_manager.py`, `terminal_view_draw.py` | `pygments` |
| 07 | `sidebar_view.py`, `session_tracker.py` | `main_window.py` | None |
| 08 | `block_renderer.py`, `command_parser.py` | Major refactor of rendering | None |
| 09 | `claude_integration.py` | `terminal_view_input.py` | None |
| 10 | None | Various view files | None |

## Detailed Phase Files

- [Phase 00](phase-00-performance-and-rendering-fix.md) — **CRITICAL** Dirty-line redraw, layer-backed view, wide char/emoji, cursor blink opt
- [Phase 01](phase-01-smart-context-menu.md) — Smart right-click with file/URL/error detection
- [Phase 02](phase-02-status-bar.md) — Bottom status bar (shell, CWD, git branch)
- [Phase 03](phase-03-tab-enhancements.md) — Rename tab, split panes
- [Phase 04](phase-04-font-ligatures.md) — Font ligatures, better typography
- [Phase 05](phase-05-smart-links.md) — Clickable file paths, URLs, error locations
- [Phase 06](phase-06-syntax-highlighting.md) — Code block syntax highlighting
- [Phase 07](phase-07-sidebar.md) — Session info sidebar
- [Phase 08](phase-08-command-blocks.md) — Command/output block rendering
- [Phase 09](phase-09-claude-integration.md) — AI actions (explain, fix, refactor)
- [Phase 10](phase-10-polish-animations.md) — Smooth animations & micro-interactions
