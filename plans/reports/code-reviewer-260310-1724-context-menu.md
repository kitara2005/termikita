# Code Review: Right-Click Context Menu Implementation

## Scope
- Files: `terminal_view_input.py`, `terminal_view.py`, `tab_bar_view.py`, `tab_controller.py`
- LOC changed: ~170 added
- Focus: Context menu PyObjC correctness, memory safety, edge cases

## Overall Assessment

Solid implementation. PyObjC selector/target pattern used correctly. Deferred close pattern prevents use-after-free crashes. A few medium-priority issues found around index staleness and IME regression.

---

## Critical Issues

None.

---

## High Priority

### 1. `close_other_tabs` index shifts `keep_index` semantics

**File:** `tab_controller.py:187-194`

The reverse-iteration approach works correctly for `self.tabs.pop()` because closing higher indices first preserves lower indices. However, each `close_tab()` call also triggers `select_tab()`, which:
- Calls `removeFromSuperview()` on the currently active view
- Calls `addSubview_()` on the new active view
- Calls `makeFirstResponder_()`

This means N-1 unnecessary select/re-layout cycles happen. With 10 tabs, 9 select_tab calls fire with full UI re-layout.

**Recommendation:** Add a batch-close method or suppress `select_tab` during batch operations:
```python
def close_other_tabs(self, keep_index: int) -> None:
    if keep_index < 0 or keep_index >= len(self.tabs):
        return
    tabs_to_close = [t for i, t in enumerate(self.tabs) if i != keep_index]
    kept = self.tabs[keep_index]
    for tab in tabs_to_close:
        _stop_view_timers(tab.view)
        try:
            tab.session.shutdown()
        except Exception:
            pass
        tab.view._session = None
        tab.view.removeFromSuperview()
    self.tabs = [kept]
    self.active_tab_index = -1
    self.select_tab(0)
```

### 2. IME regression -- `interpretKeyEvents_` removed from `keyDown_`

**File:** `terminal_view.py:200-224`

The diff shows `self.interpretKeyEvents_([event])` was replaced with direct `self._session.write(chars.encode("utf-8"))`. This **breaks Vietnamese IME and CJK input** -- the entire purpose of the `NSTextInputClient` mixin. Without `interpretKeyEvents_`, the system text input manager never gets keystrokes, so `setMarkedText_selectedRange_replacementRange_` and `insertText_replacementRange_` never fire.

**This is a regression** from the prior implementation. The original code routed through `interpretKeyEvents_` which triggers the IME composition flow.

**Recommendation:** Restore `interpretKeyEvents_` as the fallback for non-special keys:
```python
def keyDown_(self, event: object) -> None:
    modifiers = event.modifierFlags()
    if modifiers & NSEventModifierFlagCommand:
        self._handle_cmd_shortcut(event)
        return
    if modifiers & NSEventModifierFlagControl:
        chars = event.characters()
        if chars and len(chars) == 1:
            ch = chars[0].lower()
            if "a" <= ch <= "z":
                self._session.write(bytes([ord(ch) - ord("a") + 1]))
                return
    keycode = event.keyCode()
    if keycode in KEY_MAP:
        self._session.write(KEY_MAP[keycode])
        return
    # Route through Text Input System for IME support
    self.interpretKeyEvents_([event])
```

---

## Medium Priority

### 3. `_context_menu_tab_index` not initialized in `initWithFrame_`

**File:** `tab_bar_view.py:262, 291, 298`

`_context_menu_tab_index` is only set inside `menuForEvent_`. The `contextCloseTab_` and `contextCloseOtherTabs_` actions use `getattr(self, "_context_menu_tab_index", -1)` defensively, which handles the missing attr case. But this is fragile; the attribute should be initialized in `initWithFrame_` alongside `_pending_close_idx` for consistency.

**Fix:** Add `self._context_menu_tab_index = -1` to `initWithFrame_`.

### 4. Stale `_context_menu_tab_index` after tab mutations

**File:** `tab_bar_view.py:288-299`

If between right-click and menu-item selection another tab is closed (e.g., PTY exits, triggering `flush_pending_closes`), `_context_menu_tab_index` could point to wrong tab or be out of bounds. The bounds check in `contextCloseTab_` (line 292) guards against OOB, but the wrong tab could still be closed silently.

**Recommendation:** Store the tab identity (e.g., `id(tab)` or the `TabItem` ref) instead of the index, then resolve the current index at action time:
```python
self._context_menu_tab_ref = self._controller.tabs[tab_idx]
# Later in action:
try:
    idx = self._controller.tabs.index(self._context_menu_tab_ref)
except ValueError:
    return  # tab already gone
```

### 5. `contextClearBuffer_` sends form-feed, not a true clear

**File:** `terminal_view_input.py:228-231`

`\x0c` (form-feed) behavior depends on the shell/application running inside the PTY. In `bash`, it clears the screen but preserves scrollback. In `vim` or `less`, it may do nothing or something unexpected. Consider also calling `self._session.buffer.clear()` or sending `\x1b[2J\x1b[H` (VT100 erase display + cursor home) for a more predictable clear.

### 6. File sizes exceed 200-line guideline

Per project rules, files should stay under 200 lines:
- `terminal_view_input.py`: 231 lines
- `terminal_view.py`: 260 lines
- `tab_bar_view.py`: 336 lines
- `tab_controller.py`: 297 lines

`tab_bar_view.py` is the most over -- context menu methods (lines 252-303) could be extracted into a `TabBarContextMenuMixin`. `terminal_view.py` forwarding is inherently verbose but could benefit from a code-gen approach or reducing to only truly needed selectors.

---

## Low Priority

### 7. `contextDuplicateTab_` just opens a new blank tab

**File:** `tab_bar_view.py:301-303`

"Duplicate Tab" calls `self._controller.add_tab()`, which creates a fresh shell session. A user expects "duplicate" to open the same working directory. Could pass `cwd` from the duplicated tab's session:
```python
def contextDuplicateTab_(self, sender: object) -> None:
    if self._controller:
        # Future: pass cwd from source tab
        self._controller.add_tab()
```
Low priority since current behavior is functional, just misleading naming.

### 8. Paste item always enabled even when clipboard is empty

**File:** `terminal_view_input.py:194-195`

The Paste menu item is always enabled. Standard macOS behavior grays out Paste when clipboard has no text. Could check pasteboard contents:
```python
from AppKit import NSPasteboard, NSPasteboardTypeString
pb = NSPasteboard.generalPasteboard()
has_text = pb.stringForType_(NSPasteboardTypeString) is not None
paste_item.setEnabled_(has_text)
```

---

## Positive Observations

1. **Deferred close pattern** -- `performSelector_withObject_afterDelay_` correctly prevents use-after-free in `mouseDown_` and context menu handlers
2. **Consistent target/action** -- All menu items correctly set explicit `setTarget_()` rather than relying on responder chain for custom selectors
3. **`setAutoenablesItems_(False)`** -- Correctly disables auto-enable so manual `setEnabled_` calls work
4. **Guard clauses** -- Both `menuForEvent_` implementations guard against nil controller and invalid hit-test results
5. **PyObjC forwarding documented** -- Docstring in `terminal_view.py` clearly explains why forwarding is needed
6. **Reverse iteration** in `close_other_tabs` handles index shifting correctly at the data level

---

## Recommended Actions (Prioritized)

1. **[HIGH]** Restore `interpretKeyEvents_` in `keyDown_` to fix IME regression
2. **[HIGH]** Optimize `close_other_tabs` to avoid N-1 redundant `select_tab` cycles
3. **[MED]** Initialize `_context_menu_tab_index` in `initWithFrame_`
4. **[MED]** Store tab reference instead of index for stale-index safety
5. **[MED]** Use VT100 escape for Clear Buffer instead of form-feed
6. **[LOW]** Rename "Duplicate Tab" or implement actual cwd duplication
7. **[LOW]** Conditionally disable Paste when clipboard empty

---

## Metrics

- Type Coverage: N/A (Python, no strict mypy in use)
- Test Coverage: Manual testing only (no automated tests for GUI)
- Linting Issues: Not measured (no linter run requested)

---

## Unresolved Questions

1. Was the `interpretKeyEvents_` removal intentional (e.g., to fix a double-input bug)? If so, IME support needs an alternative path.
2. Should "Duplicate Tab" inherit working directory? Requires `TerminalSession` to expose `cwd` (via `/proc` or `lsof`).
3. Should context menu items use key equivalents (e.g., Cmd+C for Copy) for discoverability, or would that conflict with the menu bar shortcuts?
