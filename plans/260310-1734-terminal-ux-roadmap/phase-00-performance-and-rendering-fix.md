# Phase 00: Performance & Rendering Fix (CRITICAL)

## Overview
- **Priority:** P0 (HIGHEST — do first)
- **Status:** DONE
- **Effort:** Medium (~200 LOC changes)
- Fix slow typing feel and rendering issues visible in Claude Code session.
- **Completed:** 2026-03-10

## Problems Identified

### A. Typing feels sluggish (low effective refresh)
**Root cause:** `drawRect_` redraws ALL lines every frame.
- 60fps timer fires → `setNeedsDisplay_(True)` → full redraw of every cell
- `blinkCursor_` also forces full redraw every 0.5s even when nothing changed
- Each redraw iterates all visible lines × all cells → CoreText draw per cell
- With 80×24 = 1,920 cells per frame at 60fps = 115,200 cell draws/sec

### B. UI display issues (from screenshot)
- Wide characters (emoji, CJK) may not render correctly — terminal uses fixed-width cells but emoji are double-width
- Claude Code status bar uses emoji (🔥🪙🌿📁) which need 2 cells
- Some text may overflow or overlap

## Fixes

### Fix 1: Dirty-line tracking (biggest impact)
Only redraw lines that actually changed, not all lines.

```python
# In drawRect_, instead of:
for row_idx, cells in enumerate(lines):
    self._renderer.draw_line(...)

# Do:
dirty_rows = self._session.buffer.get_dirty_rows()
if dirty_rows is None:
    # Full redraw (resize, scroll, etc.)
    for row_idx, cells in enumerate(lines):
        self._renderer.draw_line(...)
else:
    # Partial redraw — only changed rows
    for row_idx in dirty_rows:
        # Clear row area first, then draw
        self._clear_row(row_idx)
        self._renderer.draw_line(context, row_idx * ch, lines[row_idx], self._theme_colors)
```

### Fix 2: Layer-backed view for GPU compositing
```python
def initWithFrame_(self, frame):
    ...
    self.setWantsLayer_(True)  # Enable CALayer backing
    self.layer().setDrawsAsynchronously_(True)
```
Layer-backed views use GPU compositing → much smoother scrolling/drawing.

### Fix 3: Cursor blink — only redraw cursor region
```python
def blinkCursor_(self, timer):
    self._cursor_visible = not self._cursor_visible
    # Only invalidate cursor cell, not entire view
    cursor_row, cursor_col, _ = self._session.buffer.get_cursor()
    cw, ch = self._renderer.cell_width, self._renderer.cell_height
    self.setNeedsDisplayInRect_(NSMakeRect(cursor_col * cw, cursor_row * ch, cw, ch))
```

### Fix 4: Double-width character support
- Check `unicodedata.east_asian_width(char)` for W/F → 2 cells
- Renderer skips next cell after drawing wide char
- Glyph atlas stores width metadata

### Fix 5: Reduce unnecessary redraws
- `refreshDisplay_` currently redraws when `dirty` flag set — good
- But `blinkCursor_` always forces redraw — fix with region invalidation
- Skip `setNeedsDisplay_` if view is not visible/minimized

## Related Code Files

**Modify:**
- `src/termikita/terminal_view_draw.py` — dirty-line redraw, cursor-only blink, layer-backed
- `src/termikita/buffer_manager.py` — track dirty rows (not just dirty flag)
- `src/termikita/text_renderer.py` — wide char support
- `src/termikita/terminal_view.py` — enable layer backing in init

## Implementation Steps

1. **buffer_manager.py**: Add `_dirty_rows: set[int]` tracking
   - Mark specific rows dirty on write/scroll
   - `get_dirty_rows()` returns set or None (None = full redraw needed)
   - Scroll/resize → set `_dirty_rows = None` (force full redraw)

2. **terminal_view_draw.py**:
   - `drawRect_` checks dirty rows → partial redraw
   - `blinkCursor_` → `setNeedsDisplayInRect_` for cursor cell only
   - Enable `setWantsLayer_(True)` in init

3. **text_renderer.py**:
   - Add `east_asian_width` check in `draw_line()`
   - Wide chars → draw at double cell width, skip next cell

4. **Verify**: Build & run, compare typing responsiveness

## Expected Impact
- **Typing latency**: ~10x reduction (redraw 1-2 lines vs 24)
- **CPU usage**: Significant drop during idle (cursor blink is 1 cell vs full screen)
- **Wide chars**: Emoji and CJK render correctly in Claude Code status bar

## Success Criteria
- [x] Typing feels instant (no visible lag)
- [x] Cursor blinks without full-screen redraw
- [x] Emoji in Claude Code status bar render at correct width
- [x] CPU usage drops when terminal is idle
- [x] Scrolling through long output is smooth
- [x] Layer-backed view enabled
