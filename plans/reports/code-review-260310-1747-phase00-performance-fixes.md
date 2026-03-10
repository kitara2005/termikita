# Code Review: Phase 00 Performance & Rendering Fixes

**Reviewer:** code-reviewer
**Date:** 2026-03-10
**Scope:** 4 files, ~65 LOC added (net), focused on dirty-row invalidation, cursor blink optimization, wide-char shadow cell skip, layer-backed view

## Scope

- `src/termikita/buffer_manager.py` (257 LOC) -- dirty tracking extension
- `src/termikita/terminal_view_draw.py` (176 LOC) -- partial drawRect_, smart refresh
- `src/termikita/terminal_view.py` (264 LOC) -- layer-backed init, cursor pos tracking
- `src/termikita/cell_draw_helpers.py` (142 LOC) -- wide-char detection + shadow skip
- Scout findings included below

## Overall Assessment

Solid performance optimization. The dirty-row invalidation design is correct for the single-producer/single-consumer threading model. The partial `drawRect_` and cursor-only blink invalidation should measurably reduce GPU/CPU work. Wide-char handling is appropriate for pyte's buffer model. A few issues found, ranging from a potential race window to minor code hygiene.

---

## Critical Issues

None found.

---

## High Priority

### H1. Thread safety window between get_dirty_rows() and clear_dirty()

**File:** `terminal_view_draw.py:151-164`

The PTY read thread calls `buffer.feed()` which mutates `pyte.Screen.dirty` (a set). Meanwhile `refreshDisplay_` on the main thread reads `get_dirty_rows()` which calls `set(self._screen.dirty)` -- creating a snapshot. Between the snapshot and `clear_dirty()`, new dirty rows can be added by the PTY thread and immediately cleared without ever being drawn.

**Impact:** Occasionally a changed row may not redraw until the next feed cycle (typically <16ms later), causing a one-frame flicker. In practice, at terminal I/O rates with a 60fps timer, this is unlikely to be visible.

**Recommendation:** Acceptable for v1. If upgrading to v2, consider a threading.Lock around dirty read+clear, or swap to an atomic "dirty epoch" counter. The existing comment in `terminal_session.py` L27-31 acknowledges this design tradeoff.

### H2. `_force_full_redraw` also has no thread guard

**File:** `buffer_manager.py:113, 192, 199, 203, 207, 216`

The `_force_full_redraw` bool is set by `scroll_up/down/to_bottom` (called from main thread via scrollWheel_) and by `resize` (main thread), so this is safe for scroll/resize. But `feed()` on the PTY thread does NOT set it, and `clear_dirty()` clears it on the main thread -- so the read/write pattern is actually single-writer for this flag. **No actual bug here**, but document the invariant.

### H3. IME input broken -- interpretKeyEvents_ removed

**File:** `terminal_view.py:203-227`

The `keyDown_` rewrite removed `self.interpretKeyEvents_([event])` and replaced it with direct KEY_MAP + `chars.encode("utf-8")`. This **breaks Vietnamese IME** (and CJK IME) because the NSTextInputClient protocol requires `interpretKeyEvents_` to be called for the IME composition cycle to work. Without it, `setMarkedText_selectedRange_replacementRange_` and `insertText_replacementRange_` will never be called by the text input system.

**Impact:** Core feature regression for Vietnamese/CJK users. The README and phase plan specifically mention Vietnamese text support.

**Recommendation:** Restore `interpretKeyEvents_` as the fallback path after KEY_MAP and Ctrl handling:

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
    # Route through Text Input System for IME (Vietnamese, CJK, etc.)
    self.interpretKeyEvents_([event])
```

This keeps Ctrl and special key handling direct while preserving IME for regular text.

**Note:** This change is technically outside the "Phase 00 performance fixes" scope -- it appears to be a broader keyboard input rewrite that happened in the same commit. However, since it shipped with the same diff, it must be flagged.

---

## Medium Priority

### M1. Dead code: `get_dirty_lines()` method

**File:** `buffer_manager.py:187-188`

`get_dirty_lines()` is never called from production code. Only called from tests. It duplicates `get_dirty_rows()` but without the `_force_full_redraw` check, which could confuse future maintainers.

**Recommendation:** Keep for backward compat with existing tests but add a deprecation comment, or update tests to use `get_dirty_rows()` and remove `get_dirty_lines()`.

### M2. Private attribute access in drawRect_

**File:** `terminal_view_draw.py:58`

```python
at_bottom = self._session.buffer._scroll_offset == 0
```

Accessing `_scroll_offset` private attribute crosses the encapsulation boundary. This is fragile if BufferManager internals change.

**Recommendation:** Add a public property:
```python
# buffer_manager.py
@property
def is_at_bottom(self) -> bool:
    return self._scroll_offset == 0
```

### M3. Selection highlight not clipped to dirty rect

**File:** `terminal_view_draw.py:70-71`

```python
if self._selection_start and self._selection_end:
    self._draw_selection_highlight(self.bounds())
```

When a partial rect invalidation occurs, `_draw_selection_highlight` still draws over `self.bounds()`, which draws selection rectangles outside the dirty rect. AppKit clips to the dirty rect automatically, so this is not visually broken, but it does unnecessary work.

**Recommendation:** Low priority. AppKit's clipping prevents visual artifacts. For future optimization, clip selection drawing to the intersecting row range.

### M4. `_is_wide_char` misses multi-codepoint emoji

**File:** `cell_draw_helpers.py:59-63`

The function only checks single characters (`len(ch) != 1 -> False`). Multi-codepoint emoji sequences (e.g., flag emoji, skin-tone modifiers, ZWJ sequences) will not be detected as wide. However, pyte's buffer stores individual codepoints per cell, so multi-codepoint sequences would already be split across cells. This is correct for the current pyte model.

**Recommendation:** No action needed now. Add a comment explaining the single-codepoint assumption matches pyte's buffer model.

### M5. Hiragana is actually wide in Unicode East Asian Width

**File:** `tests/test-phase00-performance-fixes.py:123-124`

The test comment says "Japanese hiragana are narrow" and asserts `_is_wide_char("あ") is False`, but hiragana "あ" (U+3042) has `East_Asian_Width=W` (Wide) in Unicode. This test assertion is wrong -- it should expect `True`.

**Impact:** If the test passes, it means something is wrong with the detection. Need to verify. If it fails, the test itself is buggy.

**Recommendation:** Fix the test:
```python
def test_is_wide_char_cjk_japanese_hiragana(self):
    """Japanese hiragana are wide (EastAsianWidth='W')."""
    assert _is_wide_char("あ") is True
    assert _is_wide_char("日") is True
```

Similarly, Korean Hangul "가" (U+AC00) also has `East_Asian_Width=W` -- the test at line 131 asserting `False` is also wrong.

---

## Low Priority

### L1. `_back_buffer` initialized but never used

**File:** `terminal_view.py:70`

`self._back_buffer: object = None` is initialized and set to `None` in `setFrameSize_` but never read anywhere. Possibly leftover from a planned double-buffering feature.

**Recommendation:** Remove if not planned for Phase 01-10.

### L2. Bare `except Exception: pass` in draw helpers

**Files:** `cell_draw_helpers.py:55,102,141`

All three draw passes silently swallow exceptions. This makes debugging rendering issues very difficult.

**Recommendation:** At minimum, log to stderr in debug mode. Consider a module-level `DEBUG` flag.

### L3. `terminal_view.py` exceeds 200-line limit

At 264 lines, the file exceeds the project's 200-line guideline. The PyObjC forwarding boilerplate accounts for ~80 lines and is unavoidable.

**Recommendation:** Accept as-is. The forwarding methods are trivial one-liners required by PyObjC's runtime. Splitting would add complexity without benefit.

---

## Edge Cases Found by Scout

1. **Scroll during rapid output:** When PTY output is rapid (e.g., `cat large_file`), `feed()` runs on PTY thread setting `pyte.dirty`, while `refreshDisplay_` on main thread reads+clears it. No lock. The snapshot via `set(self._screen.dirty)` is safe for CPython GIL, but the time window between snapshot and `clear_dirty()` means dirty rows added mid-cycle get cleared. Mitigated by 60fps poll rate.

2. **Resize while scrolled back:** `resize()` resets `_scroll_offset` to 0 and sets `_force_full_redraw = True`. This is correct -- it snaps to bottom and forces full redraw.

3. **Empty terminal (no session):** `drawRect_` guards `getattr(self, "_session", None)` early. `refreshDisplay_` does the same. `blinkCursor_` guards with `getattr(self, "_session", None)`. All safe.

4. **Cursor at bottom of viewport:** `first_row <= cursor_row < last_row` guard in `drawRect_` correctly handles cursor outside the invalidated rect range.

5. **Wide char at last column:** If a wide char occupies the last column, `skip_next` would be True but `enumerate` ends the loop naturally. No index-out-of-bounds.

6. **`setWantsLayer_(True)` with partial invalidation:** Layer-backed views in macOS use a backing CALayer. `setNeedsDisplayInRect_` is compatible with layer-backed views and actually more efficient (CALayer can composite dirty tiles). No issues.

---

## Positive Observations

1. **Clean separation:** Dirty tracking in BufferManager, invalidation logic in DrawMixin -- good separation of concerns
2. **Cursor ghost handling:** Tracking `_prev_cursor_pos` to invalidate both old and new cursor positions is a thoughtful detail that prevents cursor ghost artifacts
3. **Background fill scoped to rect:** `NSBezierPath.fillRect_(rect)` instead of `fillRect_(bounds)` correctly limits background fill to the dirty region
4. **DEC 2026 synchronized output respected:** `refreshDisplay_` skips invalidation during synchronized mode, preventing tearing
5. **Comprehensive test coverage:** 35+ test cases in `test-phase00-performance-fixes.py` covering init, scroll, resize, wide chars, edge cases
6. **dealloc hardened:** Changed from bare attribute access to `getattr(..., None)` with try/except -- prevents crashes during teardown

---

## Recommended Actions (Priority Order)

1. **[HIGH] Fix IME regression** -- Restore `interpretKeyEvents_` in `keyDown_` fallback path (H3)
2. **[HIGH] Document threading invariant** for `_force_full_redraw` and dirty set access (H1, H2)
3. **[MED] Fix hiragana/Korean test assertions** -- They assert wrong values for East_Asian_Width (M5)
4. **[MED] Add `is_at_bottom` property** to BufferManager to avoid `_scroll_offset` private access (M2)
5. **[MED] Deprecate or remove `get_dirty_lines()`** -- Superseded by `get_dirty_rows()` (M1)
6. **[LOW] Remove unused `_back_buffer`** field (L1)

---

## Metrics

| Metric | Value |
|--------|-------|
| Files reviewed | 4 (+1 test file) |
| Net LOC added | ~65 |
| Type safety | Good (annotations present, NamedTuple for CellData) |
| Test coverage | 35+ test cases for Phase 00 features |
| Linting issues | 0 syntax errors (static analysis) |

---

## Unresolved Questions

1. **Was the `interpretKeyEvents_` removal intentional?** If so, how is Vietnamese/CJK IME supposed to work? The mixin's `insertText_replacementRange_` and `setMarkedText_selectedRange_replacementRange_` become dead code without it.
2. **Should `get_dirty_lines()` be kept for backward compat?** Only 2 test call sites. Easy to migrate.
3. **Are the hiragana/Korean test assertions intentionally testing against pyte's behavior** (which might normalize differently) **or against raw Unicode properties?** If the former, need to verify what pyte actually stores.
