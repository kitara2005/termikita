# Phase 03: Tab Enhancements (Rename + Split)

## Overview
- **Priority:** P1
- **Status:** TODO
- **Effort:** Medium (~300 LOC)

## Features

### 3a. Rename Tab
- Double-click tab title → inline text field for editing
- Or right-click → "Rename Tab" → shows text field
- Tab title persists until renamed again or shell updates it

### 3b. Split Terminal (Horizontal/Vertical)
- Right-click tab → "Split Right" / "Split Down"
- Uses `NSSplitView` to divide content area
- Each split has its own TerminalView + TerminalSession
- Focus follows mouse click

## Menu Additions (Tab Bar)
```
New Tab
Close Tab
Close Other Tabs
Rename Tab          ← NEW
Duplicate Tab
───────────────────
Split Right         ← NEW
Split Down          ← NEW
```

## Architecture

**Rename:** Overlay `NSTextField` on tab bar at tab position → commit on Enter/focus-loss.

**Split:** New `SplitViewController` wrapping `NSSplitView`. Each pane is a TerminalView. TabController manages split state per tab.

## Related Code Files

**Create:**
- `src/termikita/split_view_controller.py` (~150 LOC)

**Modify:**
- `src/termikita/tab_bar_view.py` — add rename UI + menu items
- `src/termikita/tab_controller.py` — manage split state per TabItem

## Success Criteria
- [ ] Double-click tab → rename inline
- [ ] Split Right creates vertical split
- [ ] Split Down creates horizontal split
- [ ] Each split pane independent terminal
- [ ] Close split pane returns to single view
