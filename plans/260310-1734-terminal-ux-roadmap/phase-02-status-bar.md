# Phase 02: Status Bar

## Overview
- **Priority:** P0
- **Status:** TODO
- **Effort:** Low (~150 LOC new)
- Bottom status bar showing shell info, CWD, git branch, terminal size.

## Design

```
┌──────────────────────────────────────────┐
│ Tab Bar                                  │
├──────────────────────────────────────────┤
│                                          │
│           Terminal Content                │
│                                          │
├──────────────────────────────────────────┤
│ zsh  │  ~/project  │  main  │  80×24    │
└──────────────────────────────────────────┘
```

**Height:** 22px (compact, like VS Code)
**Sections:**
- Shell name (zsh/bash/fish)
- Current working directory (from OSC 7 or title parsing)
- Git branch (parse from shell prompt or run `git branch`)
- Terminal grid size (cols × rows)

## Architecture

New module: `status_bar_view.py` (~100 LOC)
- `StatusBarView(NSView)` — draws 22px bar at bottom
- Updated by `TabController` when active tab changes or on timer

## Related Code Files

**Create:**
- `src/termikita/status_bar_view.py`

**Modify:**
- `src/termikita/main_window.py` — add status bar below content view, adjust layout
- `src/termikita/tab_controller.py` — update status bar on tab switch
- `src/termikita/terminal_session.py` — expose CWD info (from OSC 7 if available)

## Implementation Steps

1. Create `StatusBarView(NSView)` with fixed 22px height
2. Draw 4 sections with separator lines, matching theme colors
3. In `main_window.py`, add status bar at bottom:
   - Tab bar: top 28px
   - Status bar: bottom 22px
   - Content view: remaining space
4. `TabController` calls `status_bar.update(shell, cwd, branch, cols, rows)` on:
   - Tab switch
   - Window resize
   - Title change callback (CWD often in title)
5. Git branch: parse from terminal title or run `git rev-parse --abbrev-ref HEAD` periodically

## CWD Detection Strategy

Priority order:
1. **OSC 7** (if shell sends it) — most reliable
2. **OSC 2 title parsing** — many prompts include CWD in title
3. **`/proc/PID/cwd`** equivalent — `os.readlink(f"/proc/{pid}/cwd")` (Linux) or `lsof -p PID` (macOS)
4. **Fallback:** `$HOME`

## Success Criteria
- [ ] 22px status bar visible at bottom
- [ ] Shows shell name
- [ ] Shows current directory (truncated if long)
- [ ] Shows git branch when in a repo
- [ ] Shows terminal grid size
- [ ] Updates on tab switch and resize
- [ ] Matches active theme colors
