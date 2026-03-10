# Debugger Report: Fix Termikita Runtime Errors

**Date:** 2026-03-10 13:52
**Status:** RESOLVED

---

## Executive Summary

Two runtime errors prevented Termikita from operating correctly after launch. Both were fixed. App now launches successfully, shows a working terminal window, and runs cleanly with no errors.

---

## Errors Found & Fixed

### 1. `AttributeError: 'TabBarView' object has no attribute 'setAcceptsMouseMovedEvents_'`

**File:** `src/termikita/tab_bar_view.py` — `initWithFrame_`
**Root cause:** `setAcceptsMouseMovedEvents_` is an `NSWindow` method; calling it on an `NSView` subclass raises `AttributeError`.
**Fix:** Removed the invalid call. Added `updateTrackingAreas()` override that creates an `NSTrackingArea` with `NSTrackingMouseMoved | NSTrackingActiveInKeyWindow | NSTrackingInVisibleRect`. This is the correct AppKit mechanism for receiving `mouseMoved_` events in a view.

### 2. `AttributeError: 'TermikitaScreen' object has no attribute 'scroll_region'`

**File:** `src/termikita/buffer_manager.py` — `TermikitaScreen.index()`
**Root cause:** Code referenced `self.scroll_region`, which doesn't exist in the installed pyte version. The correct attribute is `self.margins` (a `pyte.screens.Margins` namedtuple with `.top`/`.bottom`, or `None` when no margins set).
**Fix:** Replaced `self.scroll_region[0] == 0` with `top, _ = self.margins or _Margins(0, self.lines - 1)` / `if top == 0:`. This matches pyte's current API exactly.

---

## Verification

```
App running cleanly for 12s with zero errors or warnings
```

- Imports: all modules load without error
- Init flow: `ConfigManager → ThemeManager → MainWindow → TabController → add_tab()` completes
- PTY: shell spawned, read thread running
- Buffer: `feed()` processes output without crashes
- Window: appears and stays alive

---

## Files Modified

- `/Users/long-nguyen/Documents/Ca-nhan/terminal/src/termikita/tab_bar_view.py`
- `/Users/long-nguyen/Documents/Ca-nhan/terminal/src/termikita/buffer_manager.py`

---

## Unresolved Questions

None.
