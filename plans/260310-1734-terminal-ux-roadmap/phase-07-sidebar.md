# Phase 07: Sidebar (Session Info Panel)

## Overview
- **Priority:** P2
- **Status:** TODO
- **Effort:** High (~500 LOC)
- Toggleable sidebar showing session context: files modified, errors, code blocks.

## Layout
```
┌──────────────────────────────────────────┐
│ Tab Bar                                  │
├────────────────────────┬─────────────────┤
│                        │ SESSION         │
│   Terminal Content     │ FILES MODIFIED  │
│                        │ CODE BLOCKS     │
│                        │ ERRORS          │
├────────────────────────┴─────────────────┤
│ Status Bar                               │
└──────────────────────────────────────────┘
```

**Toggle:** `Cmd+\` or menu item
**Width:** 250px, resizable via `NSSplitView`

## Architecture
- `sidebar_view.py` — NSView with scrollable sections
- `session_tracker.py` — parses terminal output for files, errors, code blocks
- Modify `main_window.py` to use `NSSplitView` for terminal + sidebar

## Detection Heuristics
- **Files modified**: Parse Claude CLI output for file paths with "created", "modified", "edited"
- **Errors**: Detect common error patterns (traceback, Error:, FAIL, etc.)
- **Code blocks**: Track fenced code blocks from Phase 06

## Success Criteria
- [ ] Sidebar toggles with Cmd+\
- [ ] Shows files modified by Claude
- [ ] Shows detected errors
- [ ] Clickable items open files/jump to errors
